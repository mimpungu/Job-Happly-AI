import httpx
import pytest

from app.modules.job_discovery.domain.connector import (
    AccessDeniedError,
    InvalidResponseError,
)
from app.modules.job_discovery.infrastructure.http import UnsafeUrlError, create_http_client
from app.modules.job_discovery.infrastructure.public_pages import PublicPageFetcher

HTML = "<html><body><h1>Offres</h1></body></html>"


async def _publique(_: str) -> list[str]:
    return ["93.184.216.34"]


def _fetcher(routes: dict[str, httpx.Response], vus: list[str] | None = None) -> PublicPageFetcher:
    def handler(requete: httpx.Request) -> httpx.Response:
        if vus is not None:
            vus.append(str(requete.url))
        return routes.get(str(requete.url), httpx.Response(404))

    client = create_http_client(transport=httpx.MockTransport(handler))
    return PublicPageFetcher(client, resolver=_publique)


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
