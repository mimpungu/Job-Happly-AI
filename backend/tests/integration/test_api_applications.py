"""Tests d'intégration du cycle complet de suivi de candidatures (EPIC 014)."""

import httpx


async def _creer_offre(client: httpx.AsyncClient) -> str:
    offre_body = {
        "title": "Staff Backend Engineer",
        "company_name": "Datadog",
        "description": "Concevoir des systèmes distribués à très haute échelle.",
        "location": "Paris, France",
        "country_code": "FR",
        "application_url": "https://careers.datadoghq.com/jobs/staff-backend",
    }
    res = await client.post("/api/v1/manual-offers", json=offre_body)
    assert res.status_code == 201
    return str(res.json()["id"])


async def test_cycle_vie_complet_candidature(client: httpx.AsyncClient) -> None:
    offer_id = await _creer_offre(client)

    # 1. Créer une candidature
    create_res = await client.post(
        "/api/v1/applications",
        json={"offer_id": offer_id, "initial_status": "to_apply"},
    )
    assert create_res.status_code == 201
    app_data = create_res.json()
    app_id = app_data["id"]
    assert app_data["status"] == "to_apply"

    # 2. Vérifier le refus de doublon
    dup_res = await client.post(
        "/api/v1/applications",
        json={"offer_id": offer_id},
    )
    assert dup_res.status_code == 409

    # 3. Ajouter une note et un contact
    note_res = await client.post(
        f"/api/v1/applications/{app_id}/notes",
        json={"body": "Premier contact très positif avec le Hiring Manager"},
    )
    assert note_res.status_code == 201

    contact_res = await client.post(
        f"/api/v1/applications/{app_id}/contacts",
        json={"name": "Marc Lemoine", "email": "marc@datadoghq.com", "role": "Hiring Manager"},
    )
    assert contact_res.status_code == 201

    # 4. Confirmer l'envoi manuel
    sent_res = await client.post(
        f"/api/v1/applications/{app_id}/confirm-submission",
        json={"notes": "Candidature soumise sur le portail Datadog"},
    )
    assert sent_res.status_code == 200
    assert sent_res.json()["status"] == "sent"
    assert sent_res.json()["applied_at"] is not None

    # 5. Programmer une relance
    follow_up_res = await client.patch(
        f"/api/v1/applications/{app_id}/follow-up",
        json={"follow_up_at": "2026-11-15T10:00:00Z", "notes": "Relancer si pas de réponse"},
    )
    assert follow_up_res.status_code == 200

    # 6. Consulter le Kanban et la vue tableau
    kanban_res = await client.get("/api/v1/applications/kanban")
    assert kanban_res.status_code == 200

    list_res = await client.get("/api/v1/applications?status=sent")
    assert list_res.status_code == 200
    assert list_res.json()["total"] >= 1

    # 7. Consulter le dashboard
    dash_res = await client.get("/api/v1/dashboard")
    assert dash_res.status_code == 200
    assert dash_res.json()["applications_sent_count"] >= 1
