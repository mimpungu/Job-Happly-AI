import gzip
import json

import httpx
import pytest

from app.modules.job_discovery.domain.connector import (
    AccessDeniedError,
    InvalidResponseError,
    NotConfiguredError,
    RateLimitedError,
    SourceTimeoutError,
    SourceUnavailableError,
)
from app.modules.job_discovery.infrastructure.http import (
    USER_AGENT,
    UnsafeUrlError,
    create_http_client,
    ensure_public_url,
    fetch,
    get_json,
    raise_for_status,
)


def _client(handler: httpx.MockTransport | None = None) -> httpx.AsyncClient:
    return create_http_client(transport=handler)


def _reponse(code: int, **kw: object) -> httpx.Response:
    return httpx.Response(code, request=httpx.Request("GET", "https://exemple.test"), **kw)  # type: ignore[arg-type]


class TestStatuts:
    @pytest.mark.parametrize(
        ("code", "erreur"),
        [
            (404, NotConfiguredError),
            (401, AccessDeniedError),
            (403, AccessDeniedError),
            (429, RateLimitedError),
            (500, SourceUnavailableError),
            (503, SourceUnavailableError),
            (400, InvalidResponseError),
            (302, InvalidResponseError),
        ],
    )
    def test_traduit_les_statuts_en_erreurs_typees(
        self, code: int, erreur: type[Exception]
    ) -> None:
        with pytest.raises(erreur):
            raise_for_status(_reponse(code), source_key="s")

    def test_succes_ne_leve_rien(self) -> None:
        raise_for_status(_reponse(200), source_key="s")

    def test_retry_after_est_lu_quand_il_est_valide(self) -> None:
        with pytest.raises(RateLimitedError) as info:
            raise_for_status(_reponse(429, headers={"Retry-After": "7"}), source_key="s")
        assert info.value.retry_after == 7.0

        with pytest.raises(RateLimitedError) as info:
            raise_for_status(_reponse(429, headers={"Retry-After": "demain"}), source_key="s")
        assert info.value.retry_after is None

    def test_les_refus_ne_sont_pas_rejouables(self) -> None:
        with pytest.raises(AccessDeniedError) as info:
            raise_for_status(_reponse(403), source_key="s")
        assert info.value.retryable is False


class TestRequetes:
    async def test_envoie_un_user_agent_honnete_et_ne_suit_pas_les_redirections(self) -> None:
        vus: list[httpx.Request] = []

        def handler(requete: httpx.Request) -> httpx.Response:
            vus.append(requete)
            return httpx.Response(302, headers={"Location": "https://interne.test/"})

        async with _client(httpx.MockTransport(handler)) as client:
            with pytest.raises(InvalidResponseError):
                await get_json(client, "https://exemple.test/x", source_key="s")

        assert len(vus) == 1  # la redirection n'a pas été suivie
        assert vus[0].headers["User-Agent"] == USER_AGENT
        assert "@" not in USER_AGENT  # aucune coordonnée personnelle

    async def test_lit_une_reponse_compressee_en_gzip(self) -> None:
        # Régression : les serveurs réels compressent ; le contenu décodé ne doit pas être
        # décompressé une seconde fois quand la réponse est reconstruite.
        corps = gzip.compress(json.dumps({"jobs": [1, 2]}).encode())
        transport = httpx.MockTransport(
            lambda r: httpx.Response(
                200,
                content=corps,
                headers={"Content-Encoding": "gzip", "Content-Type": "application/json"},
            )
        )
        async with _client(transport) as client:
            donnees = await get_json(client, "https://exemple.test/x", source_key="s")

        assert donnees == {"jobs": [1, 2]}

    async def test_json_invalide_est_une_reponse_invalide(self) -> None:
        transport = httpx.MockTransport(lambda r: httpx.Response(200, content=b"<html>"))
        async with _client(transport) as client:
            with pytest.raises(InvalidResponseError):
                await get_json(client, "https://exemple.test/x", source_key="s")

    async def test_404_toleree_retourne_none(self) -> None:
        transport = httpx.MockTransport(lambda r: httpx.Response(404))
        async with _client(transport) as client:
            assert (
                await get_json(
                    client, "https://exemple.test/x", source_key="s", not_found_is_error=False
                )
                is None
            )

    async def test_refuse_une_reponse_trop_volumineuse(self) -> None:
        transport = httpx.MockTransport(lambda r: httpx.Response(200, content=b"x" * 2000))
        async with _client(transport) as client:
            with pytest.raises(InvalidResponseError):
                await fetch(client, "https://exemple.test/x", source_key="s", max_bytes=1000)

    async def test_traduit_delai_et_erreur_reseau(self) -> None:
        def delai(requete: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("lent", request=requete)

        def reseau(requete: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("coupé", request=requete)

        async with _client(httpx.MockTransport(delai)) as client:
            with pytest.raises(SourceTimeoutError):
                await fetch(client, "https://exemple.test/x", source_key="s")
        async with _client(httpx.MockTransport(reseau)) as client:
            with pytest.raises(SourceUnavailableError):
                await fetch(client, "https://exemple.test/x", source_key="s")


async def _publique(_: str) -> list[str]:
    return ["93.184.216.34"]


def _resolu(*adresses: str):  # type: ignore[no-untyped-def]
    async def resolveur(_: str) -> list[str]:
        return list(adresses)

    return resolveur


class TestSsrf:
    async def test_accepte_une_url_https_publique(self) -> None:
        url = "https://exemple.test/carrieres"

        assert await ensure_public_url(url, resolver=_publique) == url

    @pytest.mark.parametrize(
        "url",
        [
            "http://exemple.test/",
            "ftp://exemple.test/",
            "file:///etc/passwd",
            "https://user:mdp@exemple.test/",
            "https:///chemin",
            "https://127.0.0.1/",
            "https://[::1]/",
            "https://10.0.0.5/",
            "https://192.168.1.10/",
            "https://169.254.169.254/latest/meta-data/",
            "https://0.0.0.0/",
        ],
    )
    async def test_refuse_les_urls_dangereuses(self, url: str) -> None:
        with pytest.raises(UnsafeUrlError):
            await ensure_public_url(url, resolver=_publique)

    @pytest.mark.parametrize(
        "adresses",
        [["127.0.0.1"], ["10.1.2.3"], ["93.184.216.34", "192.168.0.1"], ["::1"], ["fe80::1"], []],
    )
    async def test_refuse_un_nom_qui_resout_vers_une_adresse_non_publique(
        self, adresses: list[str]
    ) -> None:
        with pytest.raises(UnsafeUrlError):
            await ensure_public_url("https://piege.test/", resolver=_resolu(*adresses))

    async def test_refuse_un_nom_non_resolu(self) -> None:
        async def echec(_: str) -> list[str]:
            raise OSError("introuvable")

        with pytest.raises(UnsafeUrlError):
            await ensure_public_url("https://inconnu.test/", resolver=echec)
