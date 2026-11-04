"""Préparation, simulation et fiches entretien de bout en bout, sur PostgreSQL réel (EPIC 016)."""

import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from tests.integration.documents_support import (
    creer_offre,
    initialiser_profil_valide,
    stockage_isole,
)

__all__ = ["stockage_isole"]

DESCRIPTION = (
    "Nous construisons une plateforme de données.\n\nCompétences requises : Python, Docker"
)
BASE = "/api/v1/interview-preparation"

pytestmark = pytest.mark.usefixtures("stockage_isole")

REPONSE = (
    "Dans mon poste précédent, j'ai développé des services en Python. "
    "Ce qui a permis d'améliorer la fiabilité de la plateforme. "
    + "Nous avons itéré en équipe. "
    * 5
)


async def _candidature(client: httpx.AsyncClient, statut: str = "sent") -> str:
    offre_id = await creer_offre(
        client, titre="Ingénieur Backend", entreprise="Datadog", description=DESCRIPTION
    )
    reponse = await client.post(
        "/api/v1/applications", json={"offer_id": offre_id, "initial_status": "to_apply"}
    )
    assert reponse.status_code == 201, reponse.text
    return str(reponse.json()["id"])


async def test_sans_profil_valide_la_preparation_est_refusee(client: httpx.AsyncClient) -> None:
    app_id = await _candidature(client)

    res = await client.post(f"{BASE}/applications/{app_id}/preparation", json={})

    assert res.status_code == 409
    assert res.json()["error"]["code"] == "no_validated_profile"


async def test_candidature_inconnue(client: httpx.AsyncClient) -> None:
    res = await client.post(f"{BASE}/applications/{uuid.uuid4()}/preparation", json={})

    assert res.status_code == 404


async def test_preparation_complete_a_partir_du_vrai_profil(client: httpx.AsyncClient) -> None:
    await initialiser_profil_valide(client)
    app_id = await _candidature(client)

    res = await client.post(f"{BASE}/applications/{app_id}/preparation", json={})

    assert res.status_code == 201, res.text
    corps = res.json()
    contenu = corps["content"]
    categories = {q["category"] for q in contenu["questions"]}
    assert categories == {"hr", "behavioral", "technical"}
    assert any(
        "Ingénieur Backend" in q["text"] and "Datadog" in q["text"] for q in contenu["questions"]
    )
    assert contenu["recruiter_questions"]
    assert contenu["pitch"] and contenu["pitch_to_complete"]
    assert corps["meta"]["ai"]["status"] == "not_requested"
    assert contenu["answers"]
    assert all(a["result"] is None for a in contenu["answers"])

    relu = await client.get(f"{BASE}/applications/{app_id}/preparation")
    assert relu.status_code == 200
    assert relu.json()["content"] == contenu

    regeneree = await client.post(f"{BASE}/applications/{app_id}/preparation", json={})
    assert regeneree.json()["id"] == corps["id"]  # une seule préparation par candidature


async def test_ia_demandee_sans_ia_configuree_ne_bloque_pas(client: httpx.AsyncClient) -> None:
    await initialiser_profil_valide(client)
    app_id = await _candidature(client)

    res = await client.post(f"{BASE}/applications/{app_id}/preparation", json={"mode": "ai"})

    assert res.status_code == 201
    assert res.json()["meta"]["ai"]["status"] == "unavailable"
    assert res.json()["content"]["questions"]


async def test_preparation_inexistante_puis_simulation_impossible(
    client: httpx.AsyncClient,
) -> None:
    await initialiser_profil_valide(client)
    app_id = await _candidature(client)

    assert (await client.get(f"{BASE}/applications/{app_id}/preparation")).status_code == 404
    res = await client.post(f"{BASE}/applications/{app_id}/simulations", json={})
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "preparation_required"


async def test_cycle_de_simulation_et_historique(client: httpx.AsyncClient) -> None:
    await initialiser_profil_valide(client)
    app_id = await _candidature(client)
    await client.post(f"{BASE}/applications/{app_id}/preparation", json={})

    demarrage = await client.post(
        f"{BASE}/applications/{app_id}/simulations", json={"question_count": 3}
    )
    assert demarrage.status_code == 201, demarrage.text
    sim = demarrage.json()
    assert len(sim["questions"]) == 3 and sim["status"] == "in_progress"
    assert sim["summary"]["average_score"] is None

    qid = sim["questions"][0]["id"]
    rep = await client.put(f"{BASE}/simulations/{sim['id']}/answers/{qid}", json={"text": REPONSE})
    assert rep.status_code == 200, rep.text
    assert rep.json()["feedback"]["score"] > 0
    assert rep.json()["feedback"]["ai_status"] is None

    inconnue = await client.put(
        f"{BASE}/simulations/{sim['id']}/answers/nope", json={"text": REPONSE}
    )
    assert inconnue.status_code == 422

    fin = await client.post(f"{BASE}/simulations/{sim['id']}/complete")
    assert fin.status_code == 200
    assert fin.json()["status"] == "completed"
    assert fin.json()["summary"]["answered"] == 1

    ferme = await client.put(
        f"{BASE}/simulations/{sim['id']}/answers/{qid}", json={"text": REPONSE}
    )
    assert ferme.status_code == 409

    historique = await client.get(f"{BASE}/applications/{app_id}/simulations")
    assert [s["id"] for s in historique.json()] == [sim["id"]]
    assert historique.json()[0]["answers"][0]["text"] == REPONSE.strip()

    assert (await client.delete(f"{BASE}/simulations/{sim['id']}")).status_code == 204
    assert (await client.get(f"{BASE}/simulations/{sim['id']}")).status_code == 404


async def test_simulation_figee_malgre_la_regeneration_de_la_preparation(
    client: httpx.AsyncClient,
) -> None:
    await initialiser_profil_valide(client)
    app_id = await _candidature(client)
    await client.post(f"{BASE}/applications/{app_id}/preparation", json={})
    sim = (await client.post(f"{BASE}/applications/{app_id}/simulations", json={})).json()

    await client.post(f"{BASE}/applications/{app_id}/preparation", json={"language": "en"})
    relue = (await client.get(f"{BASE}/simulations/{sim['id']}")).json()

    assert relue["questions"] == sim["questions"]


async def test_fiche_entretien_dates_retours_et_relance(client: httpx.AsyncClient) -> None:
    await initialiser_profil_valide(client)
    app_id = await _candidature(client)
    quand = (datetime.now(UTC) + timedelta(days=3)).replace(microsecond=0)

    sans_fuseau = await client.post(
        f"{BASE}/applications/{app_id}/interviews", json={"scheduled_at": "2030-01-10T09:00:00"}
    )
    assert sans_fuseau.status_code == 422

    creation = await client.post(
        f"{BASE}/applications/{app_id}/interviews",
        json={
            "stage": "technical",
            "format": "video",
            "scheduled_at": quand.isoformat(),
            "interviewers": ["Marie Martin"],
        },
    )
    assert creation.status_code == 201, creation.text
    fiche = creation.json()
    assert fiche["outcome"] == "pending"

    # la candidature voit l'entretien dans son historique (même date)
    detail = (await client.get(f"/api/v1/applications/{app_id}")).json()
    entretiens = [e for e in detail["events"] if e["kind"] == "interview"]
    assert entretiens and "technique planifié" in entretiens[0]["body"]
    assert datetime.fromisoformat(entretiens[0]["occurred_at"]) == quand

    maj = await client.put(
        f"{BASE}/interviews/{fiche['id']}",
        json={
            "stage": "technical",
            "format": "video",
            "scheduled_at": quand.isoformat(),
            "interviewers": ["Marie Martin"],
            "outcome": "positive",
            "feedback_notes": "Bon échange sur l'architecture.",
        },
    )
    assert maj.status_code == 200
    assert maj.json()["feedback_notes"] == "Bon échange sur l'architecture."

    brouillon = await client.post(
        f"{BASE}/interviews/{fiche['id']}/follow-up-draft", json={"language": "fr"}
    )
    assert brouillon.status_code == 200
    assert brouillon.json()["follow_up_draft"]["body"].startswith("Bonjour Marie Martin,")

    liste = await client.get(f"{BASE}/interviews", params={"application_id": app_id})
    assert [i["id"] for i in liste.json()] == [fiche["id"]]
    a_venir = await client.get(f"{BASE}/interviews", params={"upcoming": "true"})
    assert len(a_venir.json()) == 1

    inconnue = await client.get(f"{BASE}/interviews/{uuid.uuid4()}")
    assert inconnue.status_code == 404


async def test_relance_refusee_pour_une_candidature_non_envoyee(client: httpx.AsyncClient) -> None:
    await initialiser_profil_valide(client)
    app_id = await _candidature(client)
    fiche = (await client.post(f"{BASE}/applications/{app_id}/interviews", json={})).json()

    res = await client.post(f"{BASE}/interviews/{fiche['id']}/follow-up", json={})

    assert res.status_code == 422  # le suivi n'accepte une relance que pour une candidature envoyée
