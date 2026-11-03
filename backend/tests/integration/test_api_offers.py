import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api.dependencies import get_session
from app.main import create_app
from app.modules.job_discovery.infrastructure import offer_queries
from app.modules.job_discovery.infrastructure.models import JobOfferModel
from app.modules.platform.infrastructure.models import UserModel

T0 = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
async def client(session: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    application = create_app()

    async def _session_de_test() -> AsyncIterator[AsyncSession]:
        yield session

    application.dependency_overrides[get_session] = _session_de_test
    transport = httpx.ASGITransport(app=application, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as c:
        yield c


async def _creer_offre(client: httpx.AsyncClient, session: AsyncSession, **champs: object) -> str:
    # Le premier appel crée l'utilisateur local ; les offres lui sont rattachées.
    await client.get("/api/v1/offers")
    owner_id = await session.scalar(select(UserModel.id).order_by(UserModel.created_at).limit(1))
    valeurs: dict[str, object] = {
        "owner_id": owner_id,
        "title": "Data Analyst",
        "description": "SQL",
        "application_url": "https://a.test/" + uuid.uuid4().hex,
        "content_hash": uuid.uuid4().hex * 2,
        "published_at": T0,
        "country_code": "FR",
    }
    valeurs.update(champs)
    offre = JobOfferModel(**valeurs)
    session.add(offre)
    await session.flush()
    return str(offre.id)


async def test_liste_vide_par_defaut_et_utilisateur_local_cree_une_seule_fois(
    client: httpx.AsyncClient,
) -> None:
    premiere = await client.get("/api/v1/offers")
    seconde = await client.get("/api/v1/offers")

    assert premiere.status_code == 200
    assert premiere.json() == {"items": [], "total": 0, "page": 1, "page_size": 25, "page_count": 1}
    assert seconde.status_code == 200


async def test_filtres_en_parametres_de_requete(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    voulue = await _creer_offre(
        client, session, title="Ingénieur Python", employment_type="permanent"
    )
    await _creer_offre(client, session, title="Comptable", country_code="BE")

    reponse = await client.get(
        "/api/v1/offers",
        params=[("text", "python"), ("country_codes", "FR"), ("employment_types", "permanent")],
    )

    assert [o["id"] for o in reponse.json()["items"]] == [voulue]


async def test_pagination_et_tri_par_l_api(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    for titre in ("c", "a", "b"):
        await _creer_offre(client, session, title=titre)

    reponse = await client.get(
        "/api/v1/offers", params={"sort": "title_asc", "page": 2, "page_size": 2}
    )

    corps = reponse.json()
    assert [o["title"] for o in corps["items"]] == ["c"]
    assert (corps["total"], corps["page_count"]) == (3, 2)


async def test_parametre_invalide_donne_une_erreur_normalisee_sans_echo_de_la_valeur(
    client: httpx.AsyncClient,
) -> None:
    reponse = await client.get("/api/v1/offers", params={"page_size": 5000, "sort": "<script>"})

    assert reponse.status_code == 422
    erreur = reponse.json()["error"]
    assert erreur["code"] == "validation_error"
    assert {d["field"] for d in erreur["details"]} >= {"page_size", "sort"}
    assert "<script>" not in reponse.text


async def test_filtre_de_salaire_sans_devise_est_refuse(client: httpx.AsyncClient) -> None:
    reponse = await client.get("/api/v1/offers", params={"salary_min": 40000})

    assert reponse.status_code == 422


async def test_fiche_detaillee_et_offre_inconnue(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    identifiant = await _creer_offre(client, session)

    trouvee = await client.get(f"/api/v1/offers/{identifiant}")
    absente = await client.get(f"/api/v1/offers/{uuid.uuid4()}")
    mal_forme = await client.get("/api/v1/offers/pas-un-uuid")

    assert trouvee.status_code == 200
    assert trouvee.json()["description"] == "SQL"
    assert (absente.status_code, absente.json()["error"]["code"]) == (404, "offer_not_found")
    assert mal_forme.status_code == 422


async def test_sauvegarder_puis_ignorer_une_offre(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    identifiant = await _creer_offre(client, session)

    sauvee = await client.put(f"/api/v1/offers/{identifiant}/state", json={"state": "saved"})
    visibles = await client.get("/api/v1/offers", params={"state": "saved"})
    ignoree = await client.put(f"/api/v1/offers/{identifiant}/state", json={"state": "ignored"})
    masquee = await client.get("/api/v1/offers")
    invalide = await client.put(f"/api/v1/offers/{identifiant}/state", json={"state": "autre"})

    assert sauvee.status_code == 204
    assert [o["state"] for o in visibles.json()["items"]] == ["saved"]
    assert ignoree.status_code == 204
    assert masquee.json()["items"] == []
    assert invalide.status_code == 422


async def test_cycle_complet_d_une_recherche_sauvegardee(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    await _creer_offre(client, session, title="Ingénieur Python")
    await _creer_offre(client, session, title="Comptable")

    creee = await client.post(
        "/api/v1/saved-searches", json={"name": "Python", "filter": {"text": "python"}}
    )
    identifiant = creee.json()["id"]
    doublon = await client.post("/api/v1/saved-searches", json={"name": "PYTHON"})
    renommee = await client.patch(f"/api/v1/saved-searches/{identifiant}", json={"name": "Dev"})
    relancee = await client.post(f"/api/v1/saved-searches/{identifiant}/run")
    historique = await client.get("/api/v1/search-runs")
    liste = await client.get("/api/v1/saved-searches")
    supprimee = await client.delete(f"/api/v1/saved-searches/{identifiant}")
    inconnue = await client.post(f"/api/v1/saved-searches/{identifiant}/run")

    assert creee.status_code == 201
    assert (doublon.status_code, doublon.json()["error"]["code"]) == (409, "saved_search_duplicate")
    assert renommee.json()["name"] == "Dev"
    assert relancee.json()["results"]["total"] == 1
    assert relancee.json()["run"]["result_count"] == 1
    assert len(historique.json()) == 1
    assert [s["name"] for s in liste.json()] == ["Dev"]
    assert supprimee.status_code == 204
    assert inconnue.status_code == 404


async def test_corps_inconnu_ou_vide_refuse(client: httpx.AsyncClient) -> None:
    inconnu = await client.post("/api/v1/saved-searches", json={"name": "x", "owner_id": "y"})
    vide = await client.post("/api/v1/saved-searches", json={"name": "  "})

    assert inconnu.status_code == 422  # un client ne peut pas imposer le propriétaire
    assert vide.status_code == 422


async def test_une_erreur_inattendue_ne_fuite_aucune_trace(
    client: httpx.AsyncClient, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _boom(*_: object, **__: object) -> None:
        raise RuntimeError("secret interne postgresql://user:motdepasse@h/db")

    monkeypatch.setattr(offer_queries.SqlOfferQueryRepository, "search", _boom)

    reponse = await client.get("/api/v1/offers")

    assert reponse.status_code == 500
    assert reponse.json() == {"error": {"code": "internal_error", "message": "Erreur interne."}}
    assert "motdepasse" not in reponse.text


async def test_sans_base_configuree_l_api_repond_503_mais_la_sante_fonctionne() -> None:
    application = create_app()
    transport = httpx.ASGITransport(app=application, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as c:
        sante = await c.get("/api/v1/health")
        offres = await c.get("/api/v1/offers")

    assert sante.status_code == 200
    assert offres.status_code == 503
