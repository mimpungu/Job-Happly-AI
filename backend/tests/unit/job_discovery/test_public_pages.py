import httpx
import pytest

from app.modules.job_discovery.domain.connector import (
    AccessDeniedError,
    InvalidResponseError,
)
from app.modules.job_discovery.infrastructure.http import UnsafeUrlError, create_http_client
from app.modules.job_discovery.infrastructure.public_pages import PageCache, PublicPageFetcher

HTML = "<html><body><h1>Offres</h1></body></html>"


async def _publique(_: str) -> list[str]:
    return ["93.184.216.34"]


class Horloge:
    """Temps simulé : `dormir` avance l'horloge et garde la trace des attentes demandées."""

    def __init__(self) -> None:
        self.maintenant = 1000.0
        self.attentes: list[float] = []

    def __call__(self) -> float:
        return self.maintenant

    async def dormir(self, secondes: float) -> None:
        self.attentes.append(secondes)
        self.maintenant += secondes


def _fetcher(routes: dict[str, httpx.Response], vus: list[str] | None = None) -> PublicPageFetcher:
    def handler(requete: httpx.Request) -> httpx.Response:
        if vus is not None:
            vus.append(str(requete.url))
        return routes.get(str(requete.url), httpx.Response(404))

    client = create_http_client(transport=httpx.MockTransport(handler))
    horloge = Horloge()
    return PublicPageFetcher(
        client, resolver=_publique, clock=horloge, sleep=horloge.dormir, min_interval=0.0
    )


def _html(contenu: str = HTML) -> httpx.Response:
    return httpx.Response(200, content=contenu.encode(), headers={"Content-Type": "text/html"})


URL = "https://carrieres.exemple.test/offres"
ROBOTS = "https://carrieres.exemple.test/robots.txt"


async def test_lit_une_page_autorisee_sans_robots_txt() -> None:
    fetcher = _fetcher({URL: _html()})  # robots.txt absent (404) = aucune restriction

    assert "Offres" in await fetcher.fetch_html(URL, source_key="s")


async def test_respecte_un_robots_txt_restrictif() -> None:
    vus: list[str] = []
    robots = httpx.Response(200, text="User-agent: *\nDisallow: /offres\n")
    fetcher = _fetcher({ROBOTS: robots, URL: _html()}, vus)

    with pytest.raises(AccessDeniedError):
        await fetcher.fetch_html(URL, source_key="s")
    assert URL not in vus  # la page elle-même n'a jamais été demandée


async def test_un_robots_txt_cible_sur_notre_agent_est_respecte() -> None:
    robots = httpx.Response(200, text="User-agent: HapplyAI\nDisallow: /\n")
    fetcher = _fetcher({ROBOTS: robots, URL: _html()})

    with pytest.raises(AccessDeniedError):
        await fetcher.fetch_html(URL, source_key="s")


async def test_autorise_un_chemin_non_interdit() -> None:
    robots = httpx.Response(200, text="User-agent: *\nDisallow: /prive\n")
    fetcher = _fetcher({ROBOTS: robots, URL: _html()})

    assert await fetcher.fetch_html(URL, source_key="s")


@pytest.mark.parametrize("code", [401, 403, 500, 503])
async def test_un_robots_txt_inaccessible_n_est_pas_une_autorisation(code: int) -> None:
    fetcher = _fetcher({ROBOTS: httpx.Response(code), URL: _html()})

    with pytest.raises(AccessDeniedError):
        await fetcher.fetch_html(URL, source_key="s")


async def test_robots_txt_demande_une_seule_fois_par_origine() -> None:
    vus: list[str] = []
    fetcher = _fetcher({URL: _html(), URL + "2": _html()}, vus)

    await fetcher.fetch_html(URL, source_key="s")
    await fetcher.fetch_html(URL + "2", source_key="s")

    assert vus.count(ROBOTS) == 1


@pytest.mark.parametrize("code", [401, 403])
async def test_un_refus_de_la_page_n_est_jamais_contourne(code: int) -> None:
    vus: list[str] = []
    fetcher = _fetcher({URL: httpx.Response(code)}, vus)

    with pytest.raises(AccessDeniedError):
        await fetcher.fetch_html(URL, source_key="s")
    assert vus.count(URL) == 1  # aucune nouvelle tentative


@pytest.mark.parametrize(
    "contenu",
    [
        "<html><title>Just a moment...</title></html>",
        "<html><div class='g-recaptcha'>captcha</div></html>",
        "<html>Please verify you are human</html>",
    ],
)
async def test_un_defi_anti_robot_arrete_la_lecture(contenu: str) -> None:
    fetcher = _fetcher({URL: _html(contenu)})

    with pytest.raises(AccessDeniedError):
        await fetcher.fetch_html(URL, source_key="s")


async def test_refuse_un_contenu_qui_n_est_pas_du_html() -> None:
    fetcher = _fetcher(
        {URL: httpx.Response(200, content=b"%PDF", headers={"Content-Type": "application/pdf"})}
    )

    with pytest.raises(InvalidResponseError):
        await fetcher.fetch_html(URL, source_key="s")


async def test_suit_une_redirection_sur_le_meme_hote() -> None:
    destination = "https://carrieres.exemple.test/jobs"
    fetcher = _fetcher(
        {URL: httpx.Response(301, headers={"Location": "/jobs"}), destination: _html()}
    )

    assert "Offres" in await fetcher.fetch_html(URL, source_key="s")


async def test_refuse_une_redirection_vers_un_autre_hote() -> None:
    fetcher = _fetcher({URL: httpx.Response(302, headers={"Location": "https://autre.test/x"})})

    with pytest.raises(AccessDeniedError):
        await fetcher.fetch_html(URL, source_key="s")


async def test_limite_les_redirections_en_boucle() -> None:
    fetcher = _fetcher({URL: httpx.Response(302, headers={"Location": URL})})

    with pytest.raises(InvalidResponseError):
        await fetcher.fetch_html(URL, source_key="s")


@pytest.mark.parametrize(
    "url",
    [
        "http://carrieres.exemple.test/offres",
        "https://127.0.0.1/offres",
        "https://localhost/offres",
    ],
)
async def test_la_protection_ssrf_s_applique_avant_toute_requete(url: str) -> None:
    vus: list[str] = []

    async def locale(_: str) -> list[str]:
        return ["127.0.0.1"]

    def handler(requete: httpx.Request) -> httpx.Response:
        vus.append(str(requete.url))
        return _html()

    client = create_http_client(transport=httpx.MockTransport(handler))
    fetcher = PublicPageFetcher(client, resolver=locale)

    with pytest.raises(UnsafeUrlError):
        await fetcher.fetch_html(url, source_key="s")
    assert vus == []


def _avec_horloge(
    routes: dict[str, httpx.Response], vus: list[str], **options: object
) -> tuple[PublicPageFetcher, Horloge]:
    def handler(requete: httpx.Request) -> httpx.Response:
        vus.append(str(requete.url))
        return routes.get(str(requete.url), httpx.Response(404))

    horloge = Horloge()
    fetcher = PublicPageFetcher(
        create_http_client(transport=httpx.MockTransport(handler)),
        resolver=_publique,
        clock=horloge,
        sleep=horloge.dormir,
        **options,  # type: ignore[arg-type]
    )
    return fetcher, horloge


async def test_une_page_deja_lue_n_est_pas_redemandee_avant_l_expiration() -> None:
    vus: list[str] = []
    fetcher, horloge = _avec_horloge({URL: _html()}, vus)

    await fetcher.fetch_html(URL, source_key="s")
    await fetcher.fetch_html(URL, source_key="s")
    appels_apres_deux_lectures = len(vus)
    horloge.maintenant += 10_000  # bien au-delà de la durée de validité du cache
    await fetcher.fetch_html(URL, source_key="s")

    assert appels_apres_deux_lectures == 2  # robots.txt + la page, une seule fois
    assert vus.count(URL) == 2  # relue après expiration


async def test_un_refus_n_est_jamais_mis_en_cache() -> None:
    vus: list[str] = []
    page = httpx.Response(
        200, content=b"<html>Just a moment...</html>", headers={"Content-Type": "text/html"}
    )
    fetcher, _ = _avec_horloge({URL: page}, vus)

    for _ in range(2):
        with pytest.raises(AccessDeniedError):
            await fetcher.fetch_html(URL, source_key="s")

    assert vus.count(URL) == 2  # redemandée : un défi anti-robot n'est pas une réponse valide


async def test_le_cache_est_borne() -> None:
    cache = PageCache(ttl=100, max_entries=2, clock=lambda: 0.0)

    cache.put("a", "1")
    cache.put("b", "2")
    cache.put("c", "3")

    assert cache.get("a") is None and cache.get("b") == "2" and cache.get("c") == "3"


async def test_les_requetes_vers_un_meme_hote_sont_espacees() -> None:
    vus: list[str] = []
    autre = URL + "-2"
    fetcher, horloge = _avec_horloge({URL: _html(), autre: _html()}, vus, min_interval=1.0)

    await fetcher.fetch_html(URL, source_key="s")
    await fetcher.fetch_html(autre, source_key="s")

    # robots.txt, page 1, page 2 : trois requêtes, donc deux attentes d'une seconde.
    assert len(vus) == 3
    assert horloge.attentes == [1.0, 1.0]


async def test_le_crawl_delay_du_site_est_respecte() -> None:
    vus: list[str] = []
    robots = httpx.Response(200, text="User-agent: *\nCrawl-delay: 5\n")
    autre = URL + "-2"
    fetcher, horloge = _avec_horloge(
        {ROBOTS: robots, URL: _html(), autre: _html()}, vus, min_interval=1.0
    )

    await fetcher.fetch_html(URL, source_key="s")
    await fetcher.fetch_html(autre, source_key="s")

    assert 5.0 in horloge.attentes
    assert max(horloge.attentes) == 5.0


async def test_un_delai_exige_trop_long_vaut_refus() -> None:
    robots = httpx.Response(200, text="User-agent: *\nCrawl-delay: 120\n")
    fetcher, _ = _avec_horloge({ROBOTS: robots, URL: _html()}, [])

    with pytest.raises(AccessDeniedError, match="délai"):
        await fetcher.fetch_html(URL, source_key="s")
