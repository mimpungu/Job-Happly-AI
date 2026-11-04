"""Isolation entre propriétaires (TASK-018-04) : un autre utilisateur ne voit ni ne modifie rien.

Même sans authentification (ADR-0008), chaque donnée porte un `owner_id`. Ce test le vérifie
sur les ressources sensibles en changeant l'utilisateur courant de l'application.
"""

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api.dependencies import get_owner_id, get_session, get_unit_of_work
from app.main import create_app
from app.modules.platform.infrastructure.models import UserModel
from tests.integration.conftest import SessionPartagee
from tests.integration.documents_support import (
    creer_offre,
    initialiser_profil_valide,
    stockage_isole,
)

__all__ = ["stockage_isole"]

pytestmark = pytest.mark.usefixtures("stockage_isole")
DESCRIPTION = "Plateforme de données.\n\nCompétences requises : Python, Docker"


@pytest.fixture
async def autre_client(
    session: AsyncSession, user_id: uuid.UUID
) -> AsyncIterator[httpx.AsyncClient]:
    """Même base, autre utilisateur courant (`user_id` : l'utilisateur local, créé d'abord).

    Dans une transaction de test, `now()` est identique pour toutes les lignes : l'ordre de
    création est donc fixé explicitement pour que l'utilisateur local reste le premier.
    """
    autre = UserModel(display_name="Intrus", created_at=datetime.now(UTC) + timedelta(hours=1))
    session.add(autre)
    await session.flush()
    application = create_app()
    application.dependency_overrides[get_unit_of_work] = lambda: SessionPartagee(session)

    async def _session() -> AsyncIterator[AsyncSession]:
        yield session

    async def _owner() -> uuid.UUID:
        return autre.id

    application.dependency_overrides[get_session] = _session
    application.dependency_overrides[get_owner_id] = _owner
    transport = httpx.ASGITransport(app=application, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as c:
        yield c


async def test_un_autre_utilisateur_ne_voit_aucune_donnee_et_ne_peut_rien_modifier(
    client: httpx.AsyncClient, autre_client: httpx.AsyncClient
) -> None:
    await initialiser_profil_valide(client)
    offre_id = await creer_offre(client, description=DESCRIPTION)
    candidature = (
        await client.post(
            "/api/v1/applications", json={"offer_id": offre_id, "initial_status": "to_apply"}
        )
    ).json()
    cv = (await client.post("/api/v1/resumes/generate", json={"offer_id": offre_id})).json()
    app_id, cv_id = candidature["id"], cv["id"]
    prep = f"/api/v1/interview-preparation/applications/{app_id}"
    await client.post(f"{prep}/preparation", json={})
    simulation = (await client.post(f"{prep}/simulations", json={})).json()
    entretien = (await client.post(f"{prep}/interviews", json={})).json()

    # Lectures : tout est introuvable pour l'intrus (404, jamais 403 qui confirmerait l'existence)
    for chemin in (
        f"/api/v1/applications/{app_id}",
        f"/api/v1/resumes/{cv_id}",
        f"/api/v1/resumes/{cv_id}/pdf",
        f"/api/v1/interview-preparation/applications/{app_id}/preparation",
        f"/api/v1/interview-preparation/simulations/{simulation['id']}",
        f"/api/v1/interview-preparation/interviews/{entretien['id']}",
    ):
        reponse = await autre_client.get(chemin)
        assert reponse.status_code == 404, f"{chemin} accessible : {reponse.status_code}"

    # Écritures : refusées de la même façon, et sans effet
    ecritures = [
        ("post", f"/api/v1/applications/{app_id}/notes", {"body": "intrusion"}),
        ("patch", f"/api/v1/applications/{app_id}/status", {"target_status": "abandoned"}),
        ("post", f"{prep}/simulations", {}),
        ("post", f"{prep}/interviews", {}),
        (
            "put",
            f"/api/v1/interview-preparation/interviews/{entretien['id']}",
            {"outcome": "negative"},
        ),
        ("delete", f"/api/v1/interview-preparation/simulations/{simulation['id']}", None),
    ]
    for methode, chemin, corps in ecritures:
        reponse = await getattr(autre_client, methode)(
            chemin, **({"json": corps} if corps is not None else {})
        )
        assert reponse.status_code == 404, f"{methode} {chemin} : {reponse.status_code}"

    # Listes vides et confidentialité : l'intrus n'a rien, et ne peut rien exporter d'autrui
    assert (await autre_client.get("/api/v1/applications")).json()["total"] == 0
    assert (await autre_client.get("/api/v1/resumes")).json() == []
    resume = (await autre_client.get("/api/v1/privacy/summary")).json()
    assert sum(c["rows"] for c in resume) == 0

    # Les données du propriétaire sont intactes
    intacte = await client.get(f"/api/v1/applications/{app_id}")
    assert intacte.json()["status"] == "to_apply"
    assert (
        await client.get(f"/api/v1/interview-preparation/simulations/{simulation['id']}")
    ).status_code == 200
