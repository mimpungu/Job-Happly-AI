"""API des entreprises suivies : découverte par nom, suivi, activation (réseau simulé)."""

import httpx
import pytest

from app.modules.job_discovery.infrastructure.http import create_http_client
from app.modules.job_discovery.presentation import companies_router


@pytest.fixture(autouse=True)
def reseau_simule(monkeypatch: pytest.MonkeyPatch) -> None:
    """Aucun test n'appelle le vrai réseau : seul le board « acme » existe."""

    def handler(requete: httpx.Request) -> httpx.Response:
        if requete.url.path == "/v1/boards/acme":
            return httpx.Response(200, json={"name": "Acme Corp"})
        if requete.url.path == "/v1/boards/acme/jobs":
            return httpx.Response(200, json={"jobs": [{"id": 1}]})
        return httpx.Response(404)

    monkeypatch.setattr(
        companies_router,
        "create_http_client",
        lambda: create_http_client(transport=httpx.MockTransport(handler)),
    )


async def test_decouvre_puis_suit_une_entreprise_par_son_nom(client: httpx.AsyncClient) -> None:
    trouves = await client.post("/api/v1/target-companies/discover", json={"name": "Acme"})
    assert trouves.status_code == 200
    board = trouves.json()[0]
    assert board["token"] == "acme" and board["offer_count"] == 1

    ajout = await client.post(
        "/api/v1/target-companies",
        json={"name": "Acme", "careers_url": board["careers_url"], "enabled": True},
    )
    assert ajout.status_code == 201
    assert ajout.json()["enabled"] is True
    assert ajout.json()["ats_kind"] == "greenhouse"

    liste = await client.get("/api/v1/target-companies")
    assert [e["name"] for e in liste.json()] == ["Acme"]


async def test_une_entreprise_inconnue_ne_donne_aucun_resultat(client: httpx.AsyncClient) -> None:
    reponse = await client.post("/api/v1/target-companies/discover", json={"name": "Introuvable"})
    assert reponse.status_code == 200
    assert reponse.json() == []


async def test_refuse_un_doublon_et_une_activation_sans_source_reconnue(
    client: httpx.AsyncClient,
) -> None:
    corps = {"name": "Acme", "careers_url": "https://boards.greenhouse.io/acme"}
    assert (await client.post("/api/v1/target-companies", json=corps)).status_code == 201
    doublon = await client.post("/api/v1/target-companies", json={**corps, "name": "ACME"})
    assert doublon.status_code == 422
    assert doublon.json()["error"]["code"] == "company_invalid"

    inconnue = await client.post("/api/v1/target-companies", json={"name": "Sans source"})
    assert inconnue.status_code == 201
    refus = await client.patch(
        f"/api/v1/target-companies/{inconnue.json()['id']}", json={"enabled": True}
    )
    assert refus.status_code == 422


async def test_entreprise_introuvable_et_collecte_sans_entreprise(
    client: httpx.AsyncClient,
) -> None:
    absente = await client.patch(
        "/api/v1/target-companies/00000000-0000-0000-0000-000000000000", json={"enabled": False}
    )
    assert absente.status_code == 404
    assert absente.json()["error"]["code"] == "company_not_found"


async def test_collecte_sans_entreprise_activee_renvoie_409(client: httpx.AsyncClient) -> None:
    reponse = await client.post("/api/v1/collection/run")
    assert reponse.status_code == 409
    assert reponse.json()["error"]["code"] == "no_company_enabled"
