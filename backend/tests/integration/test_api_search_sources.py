"""Recherche multi-sources (EPIC 008) et état des sources (006-20) : réseau simulé, vraie base."""

import json
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from app.core.config import get_settings
from app.modules.job_discovery.infrastructure.http import create_http_client
from app.modules.job_discovery.presentation import search_router

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "ats"
GREENHOUSE = json.loads((FIXTURES / "greenhouse_jobs.json").read_text(encoding="utf-8"))
FRANCE_TRAVAIL = json.loads((FIXTURES / "france_travail_search.json").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def sans_identifiants(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.delenv("HAPPLY_FRANCE_TRAVAIL_CLIENT_ID", raising=False)
    monkeypatch.delenv("HAPPLY_FRANCE_TRAVAIL_CLIENT_SECRET", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _reseau(monkeypatch: pytest.MonkeyPatch, *, panne: bool = False) -> None:
    def handler(requete: httpx.Request) -> httpx.Response:
        chemin = requete.url.path
        if "/boards/bonne/" in chemin:
            return httpx.Response(200, json=GREENHOUSE)
        if "/boards/panne/" in chemin:
            return httpx.Response(503)
        if chemin.endswith("/access_token"):
            return httpx.Response(200, json={"access_token": "t", "expires_in": 1499})
        if "offresdemploi" in chemin:
            if panne:
                return httpx.Response(503)
            return httpx.Response(
                200, json=FRANCE_TRAVAIL, headers={"Content-Range": "offres 0-1/2"}
            )
        return httpx.Response(404)

    monkeypatch.setattr(
        search_router,
        "create_http_client",
        lambda: create_http_client(transport=httpx.MockTransport(handler)),
    )


async def _suivre(client: httpx.AsyncClient, nom: str, token: str) -> None:
    reponse = await client.post(
        "/api/v1/target-companies",
        json={
            "name": nom,
            "careers_url": f"https://boards.greenhouse.io/{token}",
            "enabled": True,
        },
    )
    assert reponse.status_code == 201


async def test_sans_source_activee_la_recherche_lit_la_base_locale(
    client: httpx.AsyncClient,
) -> None:
    reponse = await client.post("/api/v1/search", json={"filter": {"text": "python"}})

    corps = reponse.json()
    assert reponse.status_code == 200
    assert corps["queried"] is False and corps["status"] is None and corps["sources"] == []
    assert corps["results"]["total"] == 0


async def test_interroge_les_sources_en_parallele_et_agrege_sans_doublon(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _reseau(monkeypatch)
    await _suivre(client, "Bonne", "bonne")
    corps = {"filter": {"text": "data analyst"}}

    premiere = (await client.post("/api/v1/search", json=corps)).json()
    seconde = (await client.post("/api/v1/search", json=corps)).json()

    assert premiere["queried"] is True and premiere["status"] == "succeeded"
    assert premiere["sources"][0]["source_key"] == "greenhouse:bonne"
    assert premiere["sources"][0]["created"] == 2  # seules les offres « Data Analyst » sont gardées
    assert {o["title"] for o in premiere["results"]["items"]} == {
        "Data Analyst",
        "Responsable Data Analyst Junior",
    }
    # Relancer ne duplique rien : tout est déjà connu.
    assert seconde["sources"][0]["created"] == 0 and seconde["results"]["total"] == 2


async def test_une_source_en_panne_ne_bloque_pas_les_autres(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _reseau(monkeypatch)
    await _suivre(client, "Bonne", "bonne")
    await _suivre(client, "Panne", "panne")

    corps = (await client.post("/api/v1/search", json={"filter": {"text": "analyst"}})).json()

    assert corps["status"] == "partial"
    par_cle = {s["source_key"]: s for s in corps["sources"]}
    assert par_cle["greenhouse:bonne"]["status"] == "ok"
    assert par_cle["greenhouse:panne"]["status"] == "failed"
    assert par_cle["greenhouse:panne"]["error_type"] == "SourceUnavailableError"
    assert corps["results"]["total"] == 2


async def test_les_intitules_vises_filtrent_a_la_collecte(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _reseau(monkeypatch)
    await _suivre(client, "Bonne", "bonne")

    corps = (
        await client.post(
            "/api/v1/search", json={"filter": {"city": "Paris"}, "titles": ["analyst"]}
        )
    ).json()

    assert [o["title"] for o in corps["results"]["items"]] == ["Data Analyst"]


@pytest.mark.usefixtures("sans_identifiants")
async def test_refresh_faux_n_interroge_aucune_source(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _reseau(monkeypatch)
    await _suivre(client, "Bonne", "bonne")

    corps = (
        await client.post("/api/v1/search", json={"filter": {"text": "analyst"}, "refresh": False})
    ).json()

    assert corps["queried"] is False and corps["results"]["total"] == 0


async def test_france_travail_configure_est_interroge_avec_les_entreprises(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HAPPLY_FRANCE_TRAVAIL_CLIENT_ID", "id")
    monkeypatch.setenv("HAPPLY_FRANCE_TRAVAIL_CLIENT_SECRET", "secret")
    get_settings.cache_clear()
    _reseau(monkeypatch)
    await _suivre(client, "Bonne", "bonne")

    corps = (await client.post("/api/v1/search", json={"filter": {"text": "analyst"}})).json()

    cles = {s["source_key"] for s in corps["sources"]}
    assert cles == {"greenhouse:bonne", "france_travail"}


async def test_le_catalogue_des_sources_signale_les_sources_non_configurees(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _reseau(monkeypatch)
    await _suivre(client, "Bonne", "bonne")
    await client.post("/api/v1/search", json={"filter": {"text": "analyst"}})

    sources = {s["key"]: s for s in (await client.get("/api/v1/sources")).json()}

    assert sources["greenhouse:bonne"]["status"] == "ok"
    assert sources["greenhouse:bonne"]["offer_count"] == 2
    assert sources["greenhouse:bonne"]["last_success_at"] is not None
    ft = sources["france_travail"]
    assert ft["status"] == "not_configured" and ft["configured"] is False
    assert ft["requires_configuration"] is True and ft["offer_count"] == 0


async def test_une_source_hors_couverture_n_est_pas_interrogee(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HAPPLY_FRANCE_TRAVAIL_CLIENT_ID", "id")
    monkeypatch.setenv("HAPPLY_FRANCE_TRAVAIL_CLIENT_SECRET", "secret")
    get_settings.cache_clear()
    _reseau(monkeypatch)
    await _suivre(client, "Bonne", "bonne")

    # France Travail ne couvre que la France : une recherche aux États-Unis l'écarte.
    corps = (
        await client.post(
            "/api/v1/search", json={"filter": {"text": "analyst", "country_codes": ["US"]}}
        )
    ).json()

    assert {s["source_key"] for s in corps["sources"]} == {"greenhouse:bonne"}


async def test_la_couverture_geographique_est_affichee_sans_rien_affirmer_de_plus(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HAPPLY_FRANCE_TRAVAIL_CLIENT_ID", "id")
    monkeypatch.setenv("HAPPLY_FRANCE_TRAVAIL_CLIENT_SECRET", "secret")
    get_settings.cache_clear()
    _reseau(monkeypatch)
    await _suivre(client, "Bonne", "bonne")

    corps = (
        await client.post(
            "/api/v1/search",
            json={"filter": {"text": "analyst", "country_codes": ["FR", "CA"]}},
        )
    ).json()

    couverture = corps["coverage"]
    assert couverture["requested"] == ["FR", "CA"]
    # France Travail déclare la France ; aucune source interrogée ne déclare le Canada.
    assert couverture["declared"] == ["FR"] and couverture["undeclared"] == ["CA"]
    # Le job board d'entreprise ne déclare aucun pays : signalé, jamais compté comme couvrant.
    assert couverture["sources_without_declared_countries"] == ["greenhouse:bonne"]


async def test_sans_pays_demande_la_couverture_est_vide(
    client: httpx.AsyncClient,
) -> None:
    corps = (await client.post("/api/v1/search", json={"filter": {"text": "python"}})).json()

    assert corps["coverage"] == {
        "requested": [],
        "declared": [],
        "undeclared": [],
        "sources_without_declared_countries": [],
    }


async def test_le_catalogue_des_sources_se_filtre_par_pays(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _reseau(monkeypatch)
    await _suivre(client, "Bonne", "bonne")
    await client.post("/api/v1/search", json={"filter": {"text": "analyst"}})

    france = {s["key"]: s for s in (await client.get("/api/v1/sources?country=fr")).json()}
    canada = {s["key"]: s for s in (await client.get("/api/v1/sources?country=CA")).json()}

    assert france["france_travail"]["coverage_declared"] is True
    assert "france_travail" not in canada  # déclare la France seulement
    # Une source à couverture non déclarée reste listée, mais signalée comme telle.
    assert canada["greenhouse:bonne"]["coverage_declared"] is False
