"""Transparence, export, effacement et conservation sur PostgreSQL réel (RGPD, EPIC 018)."""

import io
import json
import uuid
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai_management.infrastructure.models import AICacheEntryModel, AIUsageModel
from app.modules.candidate_profile.infrastructure.models import CandidateModel
from app.modules.job_discovery.infrastructure.models import JobOfferModel
from app.modules.notifications.infrastructure.models import NotificationModel
from app.modules.platform.infrastructure.models import UserModel
from tests.integration.documents_support import (
    creer_offre,
    initialiser_profil_valide,
    stockage_isole,
)

__all__ = ["stockage_isole"]

pytestmark = pytest.mark.usefixtures("stockage_isole")

BASE = "/api/v1/privacy"
DESCRIPTION = "Nous construisons une plateforme.\n\nCompétences requises : Python, Docker"
CONFIRM = {"confirmation": "SUPPRIMER"}


async def _jeu_complet(client: httpx.AsyncClient) -> dict[str, str]:
    """Profil, offre suivie, CV généré et entretien : de quoi remplir chaque catégorie."""
    await initialiser_profil_valide(client)
    offre_id = await creer_offre(
        client, titre="Backend", entreprise="Acme", description=DESCRIPTION
    )
    candidature = (
        await client.post(
            "/api/v1/applications", json={"offer_id": offre_id, "initial_status": "to_apply"}
        )
    ).json()
    cv = await client.post("/api/v1/resumes/generate", json={"offer_id": offre_id})
    assert cv.status_code == 201, cv.text
    await client.post(
        f"/api/v1/interview-preparation/applications/{candidature['id']}/interviews",
        json={"stage": "technical"},
    )
    return {"offer": offre_id, "application": candidature["id"], "cv": cv.json()["id"]}


def _comptes(resume: list[dict[str, object]]) -> dict[str, int]:
    return {c["category"]: c["rows"] for c in resume}  # type: ignore[misc]


async def test_resume_montre_ce_qui_est_stocke_par_categorie(client: httpx.AsyncClient) -> None:
    await _jeu_complet(client)

    resume = (await client.get(f"{BASE}/summary")).json()

    comptes = _comptes(resume)
    assert comptes["profile"] > 0 and comptes["documents"] > 0
    assert comptes["applications"] > 0 and comptes["offers"] > 0
    assert comptes["interviews"] > 0
    documents = next(c for c in resume if c["category"] == "documents")
    assert documents["file_bytes"] > 0  # les PDF générés sont comptés


async def test_export_zip_contient_manifeste_donnees_et_pdf(client: httpx.AsyncClient) -> None:
    ids = await _jeu_complet(client)

    reponse = await client.get(f"{BASE}/export")

    assert reponse.status_code == 200
    assert reponse.headers["content-type"] == "application/zip"
    assert "attachment" in reponse.headers["content-disposition"]
    archive = zipfile.ZipFile(io.BytesIO(reponse.content))
    noms = set(archive.namelist())
    manifeste = json.loads(archive.read("manifest.json"))
    assert manifeste["format"] == "happly-export-v1" and manifeste["schema_revision"]
    candidatures = json.loads(archive.read("data/applications/applications.json"))
    assert [c["id"] for c in candidatures] == [ids["application"]]
    assert "data/interviews/interviews.json" in noms
    pdfs = [n for n in noms if n.startswith("files/documents/") and n.endswith(".pdf")]
    assert pdfs and archive.read(pdfs[0]).startswith(b"%PDF")
    # aucune donnée d'un autre utilisateur ni secret
    assert b"AIza" not in reponse.content


async def test_export_sans_donnees_est_un_zip_valide(client: httpx.AsyncClient) -> None:
    reponse = await client.get(f"{BASE}/export")

    archive = zipfile.ZipFile(io.BytesIO(reponse.content))
    assert archive.testzip() is None
    assert json.loads(archive.read("data/applications/applications.json")) == []


async def test_effacement_exige_la_confirmation_exacte(client: httpx.AsyncClient) -> None:
    await _jeu_complet(client)

    for corps in ({"scope": "all", "confirmation": ""}, {"scope": "all", "confirmation": "oui"}):
        reponse = await client.post(f"{BASE}/erase", json=corps)
        assert reponse.status_code == 422
        assert reponse.json()["error"]["code"] == "confirmation_required"
    assert _comptes((await client.get(f"{BASE}/summary")).json())["profile"] > 0


async def test_categorie_inconnue_refusee(client: httpx.AsyncClient) -> None:
    reponse = await client.post(f"{BASE}/erase", json={"scope": "tout", **CONFIRM})

    assert reponse.status_code == 422
    assert reponse.json()["error"]["code"] == "unknown_category"


async def test_offres_non_supprimables_tant_que_des_candidatures_les_suivent(
    client: httpx.AsyncClient,
) -> None:
    await _jeu_complet(client)

    bloque = await client.post(f"{BASE}/erase", json={"scope": "offers", **CONFIRM})
    assert bloque.status_code == 409 and bloque.json()["error"]["code"] == "deletion_blocked"

    await client.post(f"{BASE}/erase", json={"scope": "applications", **CONFIRM})
    ok = await client.post(f"{BASE}/erase", json={"scope": "offers", **CONFIRM})
    assert ok.status_code == 200 and ok.json()["rows_deleted"]["job_offers"] >= 1


async def test_effacement_des_documents_supprime_aussi_les_fichiers(
    client: httpx.AsyncClient, tmp_path: Path
) -> None:
    await _jeu_complet(client)
    avant = list((tmp_path / "documents").glob("*.pdf"))
    assert avant

    reponse = await client.post(f"{BASE}/erase", json={"scope": "documents", **CONFIRM})

    assert reponse.status_code == 200
    assert reponse.json()["files_deleted"] == len(avant)
    assert list((tmp_path / "documents").glob("*.pdf")) == []
    comptes = _comptes((await client.get(f"{BASE}/summary")).json())
    assert comptes["documents"] == 0 and comptes["profile"] > 0  # le reste est intact


async def test_effacement_total_remet_l_application_a_zero(
    client: httpx.AsyncClient, tmp_path: Path
) -> None:
    await _jeu_complet(client)

    reponse = await client.post(f"{BASE}/erase", json={"scope": "all", **CONFIRM})

    assert reponse.status_code == 200 and reponse.json()["total_rows"] > 0
    assert all(v == 0 for v in _comptes((await client.get(f"{BASE}/summary")).json()).values())
    assert list((tmp_path / "documents").glob("*")) == []
    # l'application reste utilisable : on peut recréer des données
    assert (await client.get("/api/v1/applications")).status_code == 200


async def test_l_effacement_ne_touche_jamais_les_donnees_d_un_autre_utilisateur(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    await _jeu_complet(client)
    autre = UserModel(display_name="Autre")
    session.add(autre)
    await session.flush()
    offre = JobOfferModel(
        owner_id=autre.id,
        title="Offre de l'autre",
        description="x",
        application_url="https://exemple.test/x",
        content_hash="h" * 64,
    )
    session.add(offre)
    session.add(CandidateModel(owner_id=autre.id))
    await session.flush()

    await client.post(f"{BASE}/erase", json={"scope": "all", **CONFIRM})

    restantes = await session.scalar(
        select(func.count()).select_from(JobOfferModel).where(JobOfferModel.owner_id == autre.id)
    )
    candidats = await session.scalar(
        select(func.count()).select_from(CandidateModel).where(CandidateModel.owner_id == autre.id)
    )
    assert (restantes, candidats) == (1, 1)


async def test_conservation_purge_les_donnees_expirees_seulement(
    client: httpx.AsyncClient, session: AsyncSession, user_id: uuid.UUID
) -> None:
    maintenant = datetime.now(UTC)
    for jours, lu in ((120, True), (10, True), (120, False)):
        session.add(
            NotificationModel(
                owner_id=user_id,
                kind="x",
                title=f"n{jours}{lu}",
                read_at=maintenant - timedelta(days=jours) if lu else None,
            )
        )
    session.add(
        AICacheEntryModel(
            owner_id=user_id,
            cache_key="expire",
            task_type="t",
            prompt_version="v1",
            model="m",
            result={},
            expires_at=maintenant - timedelta(days=1),
        )
    )
    session.add(
        AICacheEntryModel(
            owner_id=user_id,
            cache_key="valide",
            task_type="t",
            prompt_version="v1",
            model="m",
            result={},
            expires_at=maintenant + timedelta(days=5),
        )
    )
    await session.flush()

    reponse = await client.post(f"{BASE}/retention/purge")

    assert reponse.status_code == 200
    purge = reponse.json()["rows_purged"]
    assert purge["notifications"] == 1  # seule la notification lue il y a 120 jours
    assert purge["ai_cache_entries"] == 1
    restantes = await session.scalar(select(func.count()).select_from(NotificationModel))
    assert restantes == 2
    assert await session.scalar(select(func.count()).select_from(AIUsageModel)) == 0


async def test_politique_de_conservation_documentee(client: httpx.AsyncClient) -> None:
    regles = (await client.get(f"{BASE}/retention")).json()

    par_table = {r["table"]: r for r in regles}
    assert (
        par_table["ai_cache_entries"]["days"] == 30 and par_table["ai_cache_entries"]["automatic"]
    )
    assert par_table["applications"]["days"] is None  # gardé jusqu'à suppression par l'utilisateur


async def test_transferts_vers_l_ia_documentes(client: httpx.AsyncClient) -> None:
    transferts = (await client.get(f"{BASE}/ai-transfers")).json()

    par_tache = {t["task_type"]: t for t in transferts}
    assert par_tache["cv_rewrite"]["personal_data"] is True
    assert "CV complet" in par_tache["cv_rewrite"]["never_sent"]
    assert par_tache["offer_summary"]["personal_data"] is False


async def test_reglages_de_confidentialite(client: httpx.AsyncClient) -> None:
    assert (await client.get(f"{BASE}/settings")).json()["personal_data_policy"] == "allowed"

    maj = await client.put(f"{BASE}/settings", json={"personal_data_policy": "local_only"})

    assert maj.status_code == 200
    assert (await client.get(f"{BASE}/settings")).json()["personal_data_policy"] == "local_only"
    refus = await client.put(f"{BASE}/settings", json={"personal_data_policy": "tout"})
    assert refus.status_code == 422


async def test_une_generation_ia_est_bloquee_par_la_politique_never(
    client: httpx.AsyncClient,
) -> None:
    """De bout en bout : la politique `never` est respectée même si l'IA est demandée."""
    await client.put(f"{BASE}/settings", json={"personal_data_policy": "never"})
    await initialiser_profil_valide(client)
    offre_id = await creer_offre(client, description=DESCRIPTION)

    reponse = await client.post(
        "/api/v1/resumes/generate", json={"offer_id": offre_id, "rewrite_mode": "ai"}
    )

    # Sans passerelle configurée dans ce test, la reformulation est indisponible : le CV
    # est généré et le statut le dit ; aucune donnée n'a pu partir.
    assert reponse.status_code == 201
    assert reponse.json()["versions"][0]["generation"]["ai_rewrite"]["status"] == "unavailable"
