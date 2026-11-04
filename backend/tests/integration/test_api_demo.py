"""Mode démonstration sur PostgreSQL réel : explicite, isolé du réel, entièrement réversible."""

import uuid
from pathlib import Path

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.demo.domain.catalogue import DEMO_OFFERS
from app.modules.job_discovery.infrastructure.models import JobOfferModel, JobSourceModel
from tests.integration.documents_support import (
    creer_offre,
    initialiser_profil_valide,
    stockage_isole,
)

__all__ = ["stockage_isole"]

pytestmark = pytest.mark.usefixtures("stockage_isole")
DEMO = "/api/v1/demo"
DESCRIPTION = "Une vraie offre.\n\nCompétences requises : Python, Docker"


async def test_par_defaut_la_demonstration_est_inactive_et_aucune_offre_fictive_n_existe(
    client: httpx.AsyncClient,
) -> None:
    etat = (await client.get(DEMO)).json()

    assert etat["enabled"] is False and etat["offers"] == 0
    assert (await client.get("/api/v1/offers")).json()["total"] == 0


async def test_l_activation_ajoute_des_offres_clairement_fictives(
    client: httpx.AsyncClient,
) -> None:
    etat = (await client.post(f"{DEMO}/enable")).json()

    assert etat["enabled"] is True and etat["offers"] == len(DEMO_OFFERS)
    assert "fictives" in etat["notice"]
    liste = (await client.get("/api/v1/offers?page_size=100")).json()["items"]
    assert len(liste) == len(DEMO_OFFERS)
    assert all(o["is_demo"] is True for o in liste)
    assert all(o["title"].startswith("[DÉMO]") for o in liste)
    detail = (await client.get(f"/api/v1/offers/{liste[0]['id']}")).json()
    assert detail["summary"]["is_demo"] is True
    assert ".invalid" in detail["application_url"]  # jamais une adresse joignable
    assert "offre fictive" in detail["description"]


async def test_l_activation_est_idempotente(client: httpx.AsyncClient) -> None:
    await client.post(f"{DEMO}/enable")
    seconde = (await client.post(f"{DEMO}/enable")).json()

    assert seconde["offers"] == len(DEMO_OFFERS)


async def test_refusee_quand_des_donnees_reelles_existent(client: httpx.AsyncClient) -> None:
    await creer_offre(client, description=DESCRIPTION)

    reponse = await client.post(f"{DEMO}/enable")

    assert reponse.status_code == 409
    assert reponse.json()["error"]["code"] == "demo_unavailable"
    assert (await client.get(DEMO)).json()["enabled"] is False


async def test_aucune_donnee_reelle_ne_peut_etre_ajoutee_pendant_la_demonstration(
    client: httpx.AsyncClient,
) -> None:
    await client.post(f"{DEMO}/enable")

    manuelle = await client.post(
        "/api/v1/offers/manual",
        json={
            "title": "Vraie offre",
            "description": DESCRIPTION,
            "application_url": "https://exemple.test/vraie",
        },
    )
    entreprise = await client.post("/api/v1/target-companies", json={"name": "Vraie SA"})
    collecte = await client.post("/api/v1/collection/run", json={})

    for reponse in (manuelle, entreprise, collecte):
        assert reponse.status_code == 409
        assert reponse.json()["error"]["code"] == "demo_mode_active"


async def test_la_desactivation_retire_tout_ce_qui_derive_de_la_demonstration(
    client: httpx.AsyncClient, session: AsyncSession, tmp_path: Path
) -> None:
    await initialiser_profil_valide(client)
    await client.post(f"{DEMO}/enable")
    offre = (await client.get("/api/v1/offers?page_size=1")).json()["items"][0]
    candidature = await client.post(
        "/api/v1/applications", json={"offer_id": offre["id"], "initial_status": "to_apply"}
    )
    cv = await client.post("/api/v1/resumes/generate", json={"offer_id": offre["id"]})
    assert candidature.status_code == 201 and cv.status_code == 201
    assert list((tmp_path / "documents").glob("*.pdf"))
    assert (await client.get(DEMO)).json()["applications"] == 1

    etat = (await client.post(f"{DEMO}/disable")).json()

    assert etat == {**etat, "enabled": False, "offers": 0, "applications": 0}
    assert (await client.get("/api/v1/offers")).json()["total"] == 0
    assert (await client.get("/api/v1/applications")).json()["total"] == 0
    assert (await client.get("/api/v1/resumes")).json() == []
    assert list((tmp_path / "documents").glob("*.pdf")) == []  # les fichiers dérivés partent aussi
    sources = await session.scalar(
        select(func.count()).select_from(JobSourceModel).where(JobSourceModel.key == "demo")
    )
    assert sources == 0


async def test_la_desactivation_ne_touche_jamais_aux_donnees_reelles(
    client: httpx.AsyncClient, session: AsyncSession, user_id: uuid.UUID
) -> None:
    """Une offre réelle insérée directement (la route est verrouillée pendant la démo) survit."""
    await client.post(f"{DEMO}/enable")
    reelle = JobOfferModel(
        owner_id=user_id,
        title="Vraie offre",
        description="d",
        application_url="https://exemple.test/vraie",
        content_hash="r" * 64,
    )
    session.add(reelle)
    await session.flush()

    await client.post(f"{DEMO}/disable")

    restantes = (await client.get("/api/v1/offers")).json()
    assert [o["title"] for o in restantes["items"]] == ["Vraie offre"]
    assert restantes["items"][0]["is_demo"] is False


async def test_apres_desactivation_le_reel_peut_etre_ajoute_a_nouveau(
    client: httpx.AsyncClient,
) -> None:
    await client.post(f"{DEMO}/enable")
    await client.post(f"{DEMO}/disable")

    offre_id = await creer_offre(client, description=DESCRIPTION)

    assert offre_id
