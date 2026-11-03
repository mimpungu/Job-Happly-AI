"""Route France Travail : identifiants simulés, réseau simulé, base PostgreSQL réelle."""

import json
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from app.core.config import get_settings
from app.modules.job_discovery.infrastructure.http import create_http_client
from app.modules.job_discovery.presentation import france_travail_router

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "ats" / "france_travail_search.json"
SECRET = "secret-integration-ne-doit-pas-fuiter"


@pytest.fixture
def configure(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("HAPPLY_FRANCE_TRAVAIL_CLIENT_ID", "id-integration")
    monkeypatch.setenv("HAPPLY_FRANCE_TRAVAIL_CLIENT_SECRET", SECRET)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _reseau(monkeypatch: pytest.MonkeyPatch, *, jeton_status: int = 200) -> None:
    def handler(requete: httpx.Request) -> httpx.Response:
        if requete.url.path.endswith("/access_token"):
            if jeton_status != 200:
                return httpx.Response(jeton_status, text=SECRET)
            return httpx.Response(200, json={"access_token": "t", "expires_in": 1499})
        return httpx.Response(
            200,
            json=json.loads(FIXTURE.read_text(encoding="utf-8")),
            headers={"Content-Range": "offres 0-1/2"},
        )

    monkeypatch.setattr(
        france_travail_router,
        "create_http_client",
        lambda: create_http_client(transport=httpx.MockTransport(handler)),
    )


async def test_sans_identifiants_la_source_est_non_configuree(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("HAPPLY_FRANCE_TRAVAIL_CLIENT_ID", raising=False)
    monkeypatch.delenv("HAPPLY_FRANCE_TRAVAIL_CLIENT_SECRET", raising=False)
    get_settings.cache_clear()

    statut = await client.get("/api/v1/france-travail/status")
    recherche = await client.post("/api/v1/france-travail/search", json={"keywords": ["python"]})

    assert statut.json() == {"configured": False}
    assert recherche.status_code == 409
    assert recherche.json()["error"]["code"] == "source_not_configured"


@pytest.mark.usefixtures("configure")
async def test_recherche_enregistre_les_offres_sans_doublon(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _reseau(monkeypatch)
    corps = {"company": "Exemple Banque", "city": "Paris", "department": "75"}

    premiere = await client.post("/api/v1/france-travail/search", json=corps)
    seconde = await client.post("/api/v1/france-travail/search", json=corps)

    assert premiere.status_code == 200
    assert premiere.json()["succeeded"] is True
    assert premiere.json()["created"] == 1  # seule l'offre parisienne passe le filtre local
    assert seconde.json()["created"] == 0 and seconde.json()["unchanged"] == 1
    offres = await client.get("/api/v1/offers", params={"company": "Exemple Banque"})
    assert [o["title"] for o in offres.json()["items"]] == ["Développeur Python"]
    assert offres.json()["items"][0]["source_keys"] == ["france_travail"]


@pytest.mark.usefixtures("configure")
async def test_identifiants_refuses_sont_signales_sans_fuite(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _reseau(monkeypatch, jeton_status=401)

    reponse = await client.post("/api/v1/france-travail/search", json={"keywords": ["python"]})

    assert reponse.status_code == 200
    assert reponse.json()["succeeded"] is False
    assert reponse.json()["error_type"] == "AuthenticationFailedError"
    assert SECRET not in reponse.text


@pytest.mark.usefixtures("configure")
async def test_refuse_une_recherche_sans_critere_et_un_departement_invalide(
    client: httpx.AsyncClient,
) -> None:
    vide = await client.post("/api/v1/france-travail/search", json={})
    mauvais = await client.post(
        "/api/v1/france-travail/search", json={"keywords": ["a"], "department": "75;x"}
    )

    assert vide.status_code == 422 and mauvais.status_code == 422
