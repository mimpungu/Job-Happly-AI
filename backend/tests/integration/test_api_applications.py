"""Suivi de candidatures et tableau de bord sur PostgreSQL réel (EPIC 014)."""

import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import event, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.application_management.infrastructure.models import ApplicationModel
from app.modules.job_discovery.infrastructure.models import JobOfferModel
from tests.integration.documents_support import (
    creer_offre,
    initialiser_profil_valide,
    stockage_isole,
)

DESCRIPTION = (
    "Nous construisons une plateforme de données.\n\nCompétences requises : Python, Docker"
)

pytestmark = pytest.mark.usefixtures("stockage_isole")
__all__ = ["stockage_isole"]


def _dans(jours: int) -> str:
    return (datetime.now(UTC) + timedelta(days=jours)).isoformat()


async def _candidature(
    client: httpx.AsyncClient, *, statut: str = "to_apply", **offre: object
) -> dict[str, object]:
    offre_id = await creer_offre(client, description=DESCRIPTION, **offre)  # type: ignore[arg-type]
    reponse = await client.post(
        "/api/v1/applications", json={"offer_id": offre_id, "initial_status": statut}
    )
    assert reponse.status_code == 201, reponse.text
    return reponse.json()  # type: ignore[no-any-return]


async def _documents_reels(client: httpx.AsyncClient, offre_id: str) -> tuple[str, str]:
    """Versions réelles d'un CV et d'une lettre, générées puis compilées."""
    cv = await client.post("/api/v1/resumes/generate", json={"offer_id": offre_id})
    assert cv.status_code == 201, cv.text
    lettre = await client.post("/api/v1/cover-letters/generate", json={"offer_id": offre_id})
    assert lettre.status_code == 201, lettre.text
    return cv.json()["versions"][0]["id"], lettre.json()["versions"][0]["id"]


async def test_cycle_complet_de_la_candidature_a_l_envoi_confirme(
    client: httpx.AsyncClient,
) -> None:
    await initialiser_profil_valide(client)
    offre_id = await creer_offre(
        client, titre="Staff Backend Engineer", entreprise="Datadog", description=DESCRIPTION
    )

    # 1. Création, liée à l'offre ; un doublon est refusé
    creation = await client.post(
        "/api/v1/applications", json={"offer_id": offre_id, "initial_status": "to_apply"}
    )
    assert creation.status_code == 201
    app_id = creation.json()["id"]
    assert creation.json()["offer"]["title"] == "Staff Backend Engineer"
    assert creation.json()["offer"]["company_name"] == "Datadog"
    doublon = await client.post("/api/v1/applications", json={"offer_id": offre_id})
    assert (doublon.status_code, doublon.json()["error"]["code"]) == (409, "duplicate_application")

    # 2. Notes et contact du recruteur
    note = await client.post(
        f"/api/v1/applications/{app_id}/notes", json={"body": "Premier contact positif"}
    )
    contact = await client.post(
        f"/api/v1/applications/{app_id}/contacts",
        json={"name": "Marc Lemoine", "email": "marc@datadoghq.com", "role": "Hiring Manager"},
    )
    assert (note.status_code, contact.status_code) == (201, 201)

    # 3. Le dossier est incomplet tant que CV et lettre ne sont pas associés
    dossier = (await client.get(f"/api/v1/applications/{app_id}/dossier")).json()
    assert dossier["is_ready_to_send"] is False
    assert dossier["missing_elements"] == [
        "CV personnalisé manquant",
        "Lettre de motivation manquante",
    ]
    refus = await client.patch(
        f"/api/v1/applications/{app_id}/status", json={"target_status": "ready_to_send"}
    )
    assert (refus.status_code, refus.json()["error"]["code"]) == (409, "incomplete_dossier")

    # 4. Association des versions exactes, réellement générées
    cv_id, lettre_id = await _documents_reels(client, offre_id)
    association = await client.put(
        f"/api/v1/applications/{app_id}/documents",
        json={"cv_version_id": cv_id, "letter_version_id": lettre_id},
    )
    assert association.status_code == 200, association.text
    docs = association.json()["documents"]  # avant : toujours []
    assert {d["kind"] for d in docs} == {"cv", "cover_letter"}
    assert all(d["is_current"] for d in docs)
    assert {d["document_version_id"] for d in docs} == {cv_id, lettre_id}
    assert all(d["title"] and d["version"] == 1 for d in docs)

    dossier = (await client.get(f"/api/v1/applications/{app_id}/dossier")).json()
    assert dossier["is_ready_to_send"] is True
    prete = await client.patch(
        f"/api/v1/applications/{app_id}/status", json={"target_status": "ready_to_send"}
    )
    assert prete.status_code == 200
    assert prete.json()["can_confirm_submission"] is True
    assert "sent" not in prete.json()["allowed_transitions"]

    # 5. L'envoi ne se déduit pas d'un changement de statut : il se confirme
    interdit = await client.patch(
        f"/api/v1/applications/{app_id}/status", json={"target_status": "sent"}
    )
    assert (interdit.status_code, interdit.json()["error"]["code"]) == (
        409,
        "invalid_status_transition",
    )
    envoyee = await client.post(
        f"/api/v1/applications/{app_id}/confirm-submission",
        json={"notes": "Envoyée sur le portail Datadog"},
    )
    assert envoyee.status_code == 200, envoyee.text
    assert envoyee.json()["status"] == "sent"
    assert envoyee.json()["applied_at"] is not None
    assert envoyee.json()["can_confirm_submission"] is False
    premiere_date = envoyee.json()["applied_at"]

    deuxieme = await client.post(f"/api/v1/applications/{app_id}/confirm-submission", json={})
    assert (deuxieme.status_code, deuxieme.json()["error"]["code"]) == (409, "already_submitted")
    detail = (await client.get(f"/api/v1/applications/{app_id}")).json()
    assert detail["applied_at"] == premiere_date  # jamais écrasée

    # 6. Les documents envoyés ne peuvent plus être remplacés
    autre_cv = (await client.post("/api/v1/resumes/generate", json={"title": "Autre CV"})).json()
    remplacement = await client.put(
        f"/api/v1/applications/{app_id}/documents",
        json={"cv_version_id": autre_cv["versions"][0]["id"]},
    )
    assert (remplacement.status_code, remplacement.json()["error"]["code"]) == (
        409,
        "document_locked",
    )

    # 7. Relance planifiée puis annulée
    relance = await client.patch(
        f"/api/v1/applications/{app_id}/follow-up",
        json={"follow_up_at": _dans(7), "notes": "Relancer RH"},
    )
    assert relance.status_code == 200 and relance.json()["follow_up_at"] is not None
    annulee = await client.patch(f"/api/v1/applications/{app_id}/follow-up", json={})
    assert annulee.json()["follow_up_at"] is None

    # 8. L'historique est complet et ordonné
    detail = (await client.get(f"/api/v1/applications/{app_id}")).json()
    assert [e["kind"] for e in detail["events"]] == [
        "status_change",  # création
        "note",
        "other",  # documents
        "status_change",  # prête à envoyer
        "status_change",  # envoi confirmé
        "follow_up",
        "follow_up",
    ]
    assert detail["contacts"][0]["name"] == "Marc Lemoine"


async def test_creation_directement_envoyee_refusee(client: httpx.AsyncClient) -> None:
    offre_id = await creer_offre(client, description=DESCRIPTION)
    for statut in ("sent", "interview", "offer_received"):
        reponse = await client.post(
            "/api/v1/applications", json={"offer_id": offre_id, "initial_status": statut}
        )
        assert reponse.status_code == 409
    assert (await client.get("/api/v1/applications")).json()["total"] == 0


async def test_ressources_inconnues_et_dates_sans_fuseau(client: httpx.AsyncClient) -> None:
    inconnue = uuid.uuid4()
    creation = await client.post("/api/v1/applications", json={"offer_id": str(inconnue)})
    assert (creation.status_code, creation.json()["error"]["code"]) == (404, "offer_not_found")
    for requete in (
        client.get(f"/api/v1/applications/{inconnue}"),
        client.get(f"/api/v1/applications/{inconnue}/dossier"),
        client.get(f"/api/v1/applications/{inconnue}/open-url"),
        client.patch(
            f"/api/v1/applications/{inconnue}/status", json={"target_status": "abandoned"}
        ),
        client.post(f"/api/v1/applications/{inconnue}/confirm-submission", json={}),
    ):
        reponse = await requete
        assert (reponse.status_code, reponse.json()["error"]["code"]) == (
            404,
            "application_not_found",
        )

    app = await _candidature(client)
    naive = await client.patch(
        f"/api/v1/applications/{app['id']}/follow-up", json={"follow_up_at": "2030-01-01T09:00:00"}
    )
    assert naive.status_code == 422


async def test_relance_exige_une_candidature_envoyee_et_une_date_future(
    client: httpx.AsyncClient,
) -> None:
    app = await _candidature(client)
    avant_envoi = await client.patch(
        f"/api/v1/applications/{app['id']}/follow-up", json={"follow_up_at": _dans(3)}
    )
    assert (avant_envoi.status_code, avant_envoi.json()["error"]["code"]) == (422, "invalid_date")

    assert (
        await client.post(f"/api/v1/applications/{app['id']}/confirm-submission", json={})
    ).status_code == 200
    passee = await client.patch(
        f"/api/v1/applications/{app['id']}/follow-up", json={"follow_up_at": _dans(-2)}
    )
    assert passee.status_code == 422


async def test_date_d_envoi_saisie_et_refus_du_futur(client: httpx.AsyncClient) -> None:
    app = await _candidature(client)
    futur = await client.post(
        f"/api/v1/applications/{app['id']}/confirm-submission", json={"applied_at": _dans(2)}
    )
    assert (futur.status_code, futur.json()["error"]["code"]) == (422, "invalid_date")

    hier = (datetime.now(UTC) - timedelta(days=1)).replace(microsecond=0)
    reponse = await client.post(
        f"/api/v1/applications/{app['id']}/confirm-submission",
        json={"applied_at": hier.isoformat()},
    )
    assert reponse.status_code == 200
    assert datetime.fromisoformat(reponse.json()["applied_at"]) == hier


async def test_documents_type_et_existence_verifies(client: httpx.AsyncClient) -> None:
    await initialiser_profil_valide(client)
    offre_id = await creer_offre(client, description=DESCRIPTION)
    app_id = (await client.post("/api/v1/applications", json={"offer_id": offre_id})).json()["id"]
    cv_id, lettre_id = await _documents_reels(client, offre_id)
    url = f"/api/v1/applications/{app_id}/documents"

    inconnue = await client.put(url, json={"cv_version_id": str(uuid.uuid4())})
    assert (inconnue.status_code, inconnue.json()["error"]["code"]) == (
        404,
        "document_version_not_found",
    )
    cv_en_lettre = await client.put(url, json={"letter_version_id": cv_id})
    assert (cv_en_lettre.status_code, cv_en_lettre.json()["error"]["code"]) == (
        422,
        "document_kind_mismatch",
    )
    lettre_en_cv = await client.put(url, json={"cv_version_id": lettre_id})
    assert lettre_en_cv.status_code == 422
    vide = await client.put(url, json={})
    assert (vide.status_code, vide.json()["error"]["code"]) == (422, "nothing_to_attach")

    # rien n'a été associé par ces refus
    assert (await client.get(f"/api/v1/applications/{app_id}")).json()["documents"] == []

    # Réassocier la même version, ou revenir à une version précédente, ne casse rien
    for _ in range(2):
        assert (await client.put(url, json={"cv_version_id": cv_id})).status_code == 200


async def test_lien_externe_verifie_avant_ouverture(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    app = await _candidature(client)
    ok = await client.get(f"/api/v1/applications/{app['id']}/open-url")
    assert ok.status_code == 200
    assert ok.json()["application_url"].startswith("https://exemple.test/offre/")

    for dangereuse in ("javascript:alert(1)", "https://user:secret@exemple.test/apply"):
        await session.execute(
            update(JobOfferModel)
            .where(JobOfferModel.id == uuid.UUID(str(app["offer_id"])))
            .values(application_url=dangereuse)
        )
        refus = await client.get(f"/api/v1/applications/{app['id']}/open-url")
        assert (refus.status_code, refus.json()["error"]["code"]) == (
            422,
            "application_url_unavailable",
        )


async def test_filtres_pagination_et_motifs_litteraux(client: httpx.AsyncClient) -> None:
    await _candidature(client, titre="Dev Python", entreprise="Acme_Corp")
    await _candidature(client, titre="Dev Rust", entreprise="Acme Corp")
    await _candidature(client, titre="Data 100% Remote", entreprise="Zeta", statut="to_analyze")

    def total(requete: str) -> int:
        return reponse_total[requete]

    reponse_total: dict[str, int] = {}
    for requete in (
        "",
        "status=to_analyze",
        "company=acme",
        "company=Acme_",  # « _ » est littéral : ne doit pas valoir « n'importe quel caractère »
        "company=%25",  # « % » littéral : ne correspond à aucune entreprise
        "title=100%25",
        "title=rust",
        "limit=2",
    ):
        reponse = await client.get(f"/api/v1/applications?{requete}")
        assert reponse.status_code == 200, requete
        reponse_total[requete] = reponse.json()["total"]

    assert total("") == 3
    assert total("status=to_analyze") == 1
    assert total("company=acme") == 2
    assert total("company=Acme_") == 1  # seule « Acme_Corp », pas « Acme Corp »
    assert total("company=%25") == 0
    assert total("title=100%25") == 1
    assert total("title=rust") == 1

    page = (await client.get("/api/v1/applications?limit=2&offset=0")).json()
    suite = (await client.get("/api/v1/applications?limit=2&offset=2")).json()
    assert (len(page["items"]), page["total"], len(suite["items"])) == (2, 3, 1)
    assert not {i["id"] for i in page["items"]} & {i["id"] for i in suite["items"]}


async def test_filtre_relances_echues_distinct_des_relances_planifiees(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    """Avant : « relance échue » renvoyait toute candidature ayant une date de relance."""
    echue = await _candidature(client, titre="Relance échue")
    future = await _candidature(client, titre="Relance future")
    for app in (echue, future):
        await client.post(f"/api/v1/applications/{app['id']}/confirm-submission", json={})
    await client.patch(
        f"/api/v1/applications/{future['id']}/follow-up", json={"follow_up_at": _dans(5)}
    )
    await client.patch(
        f"/api/v1/applications/{echue['id']}/follow-up", json={"follow_up_at": _dans(1)}
    )
    await session.execute(
        update(ApplicationModel)
        .where(ApplicationModel.id == uuid.UUID(str(echue["id"])))
        .values(follow_up_at=datetime.now(UTC) - timedelta(days=1))
    )

    planifiees = (await client.get("/api/v1/applications?has_follow_up=true")).json()
    echues = (await client.get("/api/v1/applications?follow_up_due=true")).json()

    assert planifiees["total"] == 2
    assert [i["offer"]["title"] for i in echues["items"]] == ["Relance échue"]
    stats = (await client.get("/api/v1/applications/stats")).json()
    assert (stats["pending_follow_ups_count"], stats["due_follow_ups_count"]) == (2, 1)


async def test_kanban_total_reel_et_cartes_limitees(client: httpx.AsyncClient) -> None:
    for i in range(3):
        await _candidature(client, titre=f"Offre {i}")
    await _candidature(client, titre="Autre", statut="to_analyze")

    kanban = (await client.get("/api/v1/applications/kanban?per_column_limit=2")).json()
    colonnes = {c["status"]: c for c in kanban["columns"]}

    assert len(colonnes) == 12  # toutes les colonnes de statut, même vides
    assert colonnes["to_apply"]["count"] == 3
    assert len(colonnes["to_apply"]["items"]) == 2
    assert colonnes["to_apply"]["has_more"] is True
    assert colonnes["to_analyze"]["has_more"] is False
    assert colonnes["to_apply"]["items"][0]["offer"]["title"].startswith("Offre")
    assert colonnes["sent"]["count"] == 0


async def test_les_listes_ne_font_pas_une_requete_par_candidature(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    """Avant : 3 requêtes par candidature (contacts, historique, documents)."""
    for i in range(12):
        await _candidature(client, titre=f"Offre {i}")
    requetes: list[str] = []
    moteur = session.bind.sync_engine  # type: ignore[union-attr]
    ecoute = lambda *args: requetes.append(args[2])  # noqa: E731
    event.listen(moteur, "before_cursor_execute", ecoute)
    try:
        liste = await client.get("/api/v1/applications?limit=25")
        nombre_liste = len(requetes)
        requetes.clear()
        await client.get("/api/v1/applications/kanban")
        nombre_kanban = len(requetes)
    finally:
        event.remove(moteur, "before_cursor_execute", ecoute)

    assert liste.json()["total"] == 12
    assert nombre_liste <= 4  # propriétaire, comptage, page ; indépendant du nombre de lignes
    assert nombre_kanban <= 4


async def test_statistiques_sans_donnee_puis_reelles(client: httpx.AsyncClient) -> None:
    vides = (await client.get("/api/v1/applications/stats")).json()
    assert vides["total_applications"] == 0
    assert vides["response_rate"] is None  # pas de 0 % sans candidature envoyée

    app = await _candidature(client, titre="Offre A")
    await _candidature(client, titre="Offre B")  # titre distinct : sinon l'import la fusionne
    await client.post(f"/api/v1/applications/{app['id']}/confirm-submission", json={})
    assert (await client.get("/api/v1/applications/stats")).json()["response_rate"] == 0.0

    await client.patch(
        f"/api/v1/applications/{app['id']}/status", json={"target_status": "interview"}
    )
    stats = (await client.get("/api/v1/applications/stats")).json()
    assert (stats["total_applications"], stats["sent_applications"]) == (2, 1)
    assert (stats["interviews_count"], stats["response_rate"]) == (1, 100.0)


async def test_tableau_de_bord_sans_donnee_n_invente_aucun_chiffre(
    client: httpx.AsyncClient,
) -> None:
    vide = (await client.get("/api/v1/dashboard")).json()

    assert vide["total_offers_found"] == 0
    assert vide["new_offers_count"] == 0
    assert vide["relevant_offers_count"] is None
    assert vide["response_rate"] is None
    assert vide["ai_budget"] == {"spent": "0", "limit": None, "currency": None, "period": "monthly"}
    assert vide["recent_searches"] == []
    assert vide["recent_activities"] == []
    assert vide["display_name"] is None
    assert vide["top_matches"] == []
    assert vide["interviews"] == []
    assert vide["active_offers_trend"] == {"current": 0, "previous": 0, "percent": None}
    assert vide["funnel"] == {
        "offers": 0,
        "tracked": 0,
        "sent": 0,
        "responses": 0,
        "offers_received": 0,
    }
    assert set(vide["applications_by_status"].values()) == {0}
    assert len(vide["applications_by_status"]) == 12


async def test_tableau_de_bord_sur_donnees_reelles(client: httpx.AsyncClient) -> None:
    await initialiser_profil_valide(client)
    suivie = await _candidature(client, titre="Suivie")
    await creer_offre(client, titre="Nouvelle 1", description=DESCRIPTION)
    await creer_offre(client, titre="Nouvelle 2", description=DESCRIPTION)

    dashboard = (await client.get("/api/v1/dashboard")).json()
    assert dashboard["total_offers_found"] == 3
    # avant : « new_offers_count » valait toujours 0 (statut « new » inexistant)
    assert dashboard["new_offers_count"] == 2  # l'offre suivie n'est plus « nouvelle »
    assert dashboard["relevant_offers_count"] is None  # aucun score calculé
    assert dashboard["relevance_threshold"] == 70

    await client.post("/api/v1/matching/recompute")
    scores = (await client.get("/api/v1/dashboard")).json()
    assert scores["relevant_offers_count"] is not None
    assert 0 <= scores["relevant_offers_count"] <= scores["total_offers_found"]  # plus « = total »

    await client.post(f"/api/v1/applications/{suivie['id']}/confirm-submission", json={})
    dashboard = (await client.get("/api/v1/dashboard")).json()
    assert dashboard["applications_sent_count"] == 1
    assert dashboard["response_rate"] == 0.0  # 1 envoi sans réponse : un vrai zéro
    activite = dashboard["recent_activities"]
    assert [a["job_title"] for a in activite] == ["Suivie", "Suivie"]
    assert activite[0]["kind"] == "status_change"
    assert activite[0]["application_id"] == suivie["id"]


async def test_tableau_de_bord_budget_ia_et_recherches(
    client: httpx.AsyncClient, session: AsyncSession, user_id: uuid.UUID
) -> None:
    from decimal import Decimal

    from app.core.api.dependencies import get_owner_id  # noqa: F401
    from app.modules.ai_management.infrastructure.models import AIBudgetModel, AIUsageModel
    from app.modules.job_discovery.infrastructure.models import SearchRunModel

    # L'utilisateur local est créé à la première requête : on le fait exister d'abord.
    await client.get("/api/v1/dashboard")
    from sqlalchemy import select

    from app.modules.platform.infrastructure.models import UserModel

    owner = await session.scalar(select(UserModel.id).order_by(UserModel.created_at).limit(1))
    assert owner is not None

    session.add(
        AIBudgetModel(
            owner_id=owner, period="monthly", provider=None, amount=Decimal("10"), currency="EUR"
        )
    )
    session.add_all(
        [
            AIUsageModel(
                owner_id=owner,
                provider="gemini",
                model="m",
                task_type="t",
                level=1,
                estimated_cost=Decimal("0.5"),
                actual_cost=Decimal("0.4"),
                currency="EUR",
                operation_id=uuid.uuid4(),
                outcome="success",
            ),
            AIUsageModel(  # refusé par le budget : ne coûte rien
                owner_id=owner,
                provider="gemini",
                model="m",
                task_type="t",
                level=1,
                estimated_cost=Decimal("5"),
                currency="EUR",
                operation_id=uuid.uuid4(),
                outcome="blocked_budget",
            ),
        ]
    )
    session.add(
        SearchRunModel(
            owner_id=owner,
            criteria={"keywords": ["python", "fastapi"], "city": "Lyon"},
            status="succeeded",
            result_count=12,
        )
    )
    await session.flush()

    budget = (await client.get("/api/v1/dashboard")).json()
    assert budget["ai_budget"]["spent"] == "0.400000"
    assert Decimal(budget["ai_budget"]["limit"]) == Decimal("10")
    assert budget["ai_budget"]["currency"] == "EUR"
    assert budget["recent_searches"][0]["label"] == "python, fastapi · Lyon"
    assert budget["recent_searches"][0]["result_count"] == 12
    assert user_id is not None


async def test_tableau_de_bord_maquette_tendances_entonnoir_et_entretiens(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    """Données de la page d'accueil : tendances mensuelles, entonnoir, meilleures offres, agenda."""
    await initialiser_profil_valide(client)
    app_a = await _candidature(client, titre="Offre A", entreprise="Acme")
    app_b = await _candidature(client, titre="Offre B", entreprise="Beta")
    await _candidature(client, titre="Offre C", entreprise="Gamma")
    for app in (app_a, app_b):
        await client.post(f"/api/v1/applications/{app['id']}/confirm-submission", json={})
    await client.patch(
        f"/api/v1/applications/{app_a['id']}/status", json={"target_status": "interview"}
    )
    await client.patch(
        f"/api/v1/applications/{app_a['id']}/status", json={"target_status": "offer_received"}
    )
    demain = _dans(1)
    await client.post(
        f"/api/v1/applications/{app_b['id']}/interviews",
        json={"description": "Entretien technique", "interview_time": demain},
    )
    # Un entretien trop ancien ne fait pas partie de la fenêtre renvoyée.
    await client.post(
        f"/api/v1/applications/{app_b['id']}/interviews",
        json={"description": "Très ancien", "interview_time": _dans(-60)},
    )
    # Offre non suivie, puis calcul des scores de toutes les offres.
    libre = await creer_offre(
        client, titre="Offre libre", entreprise="Delta", description=DESCRIPTION
    )
    await client.post("/api/v1/matching/recompute")

    dashboard = (await client.get("/api/v1/dashboard")).json()

    assert dashboard["display_name"]  # prénom du profil validé
    assert dashboard["funnel"] == {
        "offers": 4,
        "tracked": 3,
        "sent": 2,
        "responses": 1,
        "offers_received": 1,
    }
    statuts = dashboard["applications_by_status"]
    assert (statuts["offer_received"], statuts["sent"], statuts["to_apply"]) == (1, 1, 1)
    # Offres créées ce mois-ci, aucune le mois précédent : pas de variation en %.
    assert dashboard["active_offers_trend"]["current"] == 4
    assert dashboard["active_offers_trend"]["percent"] is None
    assert dashboard["applications_trend"]["current"] == 3
    assert dashboard["active_applications_count"] == 3  # aucune rejetée ni abandonnée

    # Seules les offres ni suivies ni ignorées sont proposées comme meilleures correspondances
    assert [m["title"] for m in dashboard["top_matches"]] == ["Offre libre"]
    meilleure = dashboard["top_matches"][0]
    assert (meilleure["offer_id"], meilleure["company_name"]) == (libre, "Delta")
    assert 0 <= meilleure["score"] <= 100

    entretiens = dashboard["interviews"]
    assert [i["description"] for i in entretiens] == ["Entretien technique"]
    assert entretiens[0]["job_title"] == "Offre B"
    assert entretiens[0]["application_id"] == app_b["id"]


async def test_tendance_mensuelle_avec_mois_precedent(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    for i in range(4):
        await _candidature(client, titre=f"Offre {i}")
    mois_precedent = datetime.now(UTC).replace(day=1, hour=12, minute=0) - timedelta(days=5)
    await session.execute(
        update(JobOfferModel).values(first_seen_at=mois_precedent, last_seen_at=mois_precedent)
    )
    await _candidature(client, titre="Offre récente")

    tendance = (await client.get("/api/v1/dashboard")).json()["active_offers_trend"]

    assert tendance == {"current": 1, "previous": 4, "percent": -75.0}


async def test_supprimer_une_candidature_ajoutee_par_erreur_garde_l_offre(
    client: httpx.AsyncClient,
) -> None:
    candidature = await _candidature(client)
    identifiant = candidature["id"]
    await client.post(f"/api/v1/applications/{identifiant}/notes", json={"body": "Une note"})

    suppression = await client.delete(f"/api/v1/applications/{identifiant}")
    relue = await client.get(f"/api/v1/applications/{identifiant}")
    liste = (await client.get("/api/v1/applications")).json()
    offre = await client.get(f"/api/v1/offers/{candidature['offer_id']}")
    nouvelle = await client.post("/api/v1/applications", json={"offer_id": candidature["offer_id"]})

    assert suppression.status_code == 204
    assert relue.status_code == 404 and relue.json()["error"]["code"] == "application_not_found"
    assert liste["total"] == 0
    assert offre.status_code == 200  # l'offre reste dans la recherche
    assert nouvelle.status_code == 201  # et peut être suivie à nouveau


async def test_supprimer_une_candidature_inconnue_renvoie_404(client: httpx.AsyncClient) -> None:
    reponse = await client.delete(f"/api/v1/applications/{uuid.uuid4()}")

    assert reponse.status_code == 404
