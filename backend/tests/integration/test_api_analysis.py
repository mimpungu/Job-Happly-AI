"""Analyse d'offre : persistance versionnée, réutilisation, invalidation, résumé IA."""

import uuid
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai_management.application.gateway import AIGateway
from app.modules.ai_management.application.providers import get_providers
from app.modules.ai_management.domain.models import ProviderKind
from app.modules.ai_management.presentation.dependencies import get_gateway
from app.modules.job_discovery.infrastructure.models import JobOfferModel
from app.modules.job_intelligence.infrastructure.models import JobAnalysisModel
from tests.integration.conftest import SessionPartagee
from tests.unit.ai_management.fakes import FakeProvider

DESCRIPTION = """Nous construisons une plateforme de données utilisée par des milliers de sociétés.

Vos missions
- Concevoir des API FastAPI
- Écrire des requêtes SQL sur PostgreSQL

Compétences requises
- 3 ans d'expérience minimum en Python
- Maîtrise de Docker
- Anglais courant exigé
"""


async def _ajouter_offre(client: httpx.AsyncClient, description: str = DESCRIPTION) -> str:
    reponse = await client.post(
        "/api/v1/offers/manual",
        json={
            "title": "Développeur Python",
            "description": description,
            "application_url": f"https://exemple.test/offre/{uuid.uuid4()}",
            "location": "Paris, France",
        },
    )
    return str(reponse.json()["offer_id"])


async def test_analyse_une_offre_puis_la_reutilise(client: httpx.AsyncClient) -> None:
    offre = await _ajouter_offre(client)

    premiere = (await client.get(f"/api/v1/offers/{offre}/analysis")).json()
    seconde = (await client.get(f"/api/v1/offers/{offre}/analysis")).json()

    analyse = premiere["analysis"]
    assert premiere["reused"] is False and seconde["reused"] is True
    assert seconde["analysis_id"] == premiere["analysis_id"]
    assert analyse["missions"] == [
        "Concevoir des API FastAPI",
        "Écrire des requêtes SQL sur PostgreSQL",
    ]
    assert "Docker" in analyse["mandatory_skills"] and analyse["years_experience"] == 3
    assert {"FastAPI", "PostgreSQL", "Python", "Docker"} <= set(analyse["technologies"])
    assert analyse["languages"][0]["language"] == "en"
    assert "salary" in [m["code"] for m in analyse["missing"]]


async def test_une_annonce_modifiee_cree_une_nouvelle_analyse_et_garde_l_historique(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    offre = await _ajouter_offre(client)
    avant = (await client.get(f"/api/v1/offers/{offre}/analysis")).json()

    await session.execute(
        update(JobOfferModel)
        .where(JobOfferModel.id == uuid.UUID(offre))
        .values(description=DESCRIPTION + "\nAvantages\n- Visa sponsorship is available\n")
    )
    apres = (await client.get(f"/api/v1/offers/{offre}/analysis")).json()
    historique = (await client.get(f"/api/v1/offers/{offre}/analysis/history")).json()

    assert apres["analysis_id"] != avant["analysis_id"] and apres["reused"] is False
    assert apres["analysis"]["mobility"]["visa"] == "sponsorship_offered"
    assert avant["analysis"]["mobility"]["visa"] is None  # l'ancienne analyse n'est pas réécrite
    assert historique[0]["analysis_id"] == apres["analysis_id"]
    assert len(historique) == 2
    assert await session.scalar(select(func.count()).select_from(JobAnalysisModel)) == 2


async def test_un_champ_structure_ajoute_invalide_l_analyse(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    offre = await _ajouter_offre(client)
    avant = (await client.get(f"/api/v1/offers/{offre}/analysis")).json()
    assert "salary" in [m["code"] for m in avant["analysis"]["missing"]]

    await session.execute(
        update(JobOfferModel)
        .where(JobOfferModel.id == uuid.UUID(offre))
        .values(salary_min=Decimal(45000), salary_currency="EUR")
    )
    apres = (await client.get(f"/api/v1/offers/{offre}/analysis")).json()

    assert "salary" not in [m["code"] for m in apres["analysis"]["missing"]]


async def test_offre_introuvable_est_un_404(client: httpx.AsyncClient) -> None:
    reponse = await client.get(f"/api/v1/offers/{uuid.uuid4()}/analysis")

    assert reponse.status_code == 404 and reponse.json()["error"]["code"] == "offer_not_found"


def _brancher(client: httpx.AsyncClient, session: AsyncSession, fournisseur: FakeProvider) -> None:
    application = client._transport.app  # type: ignore[attr-defined]
    application.dependency_overrides[get_providers] = lambda: [fournisseur]
    application.dependency_overrides[get_gateway] = lambda: AIGateway(
        SessionPartagee(session), [fournisseur]
    )


async def test_resume_ia_via_la_passerelle_puis_cache(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    local = FakeProvider(
        "ollama-test",
        ProviderKind.LOCAL,
        reponses=['{"summary": "Poste Python data.", "key_points": ["API", "SQL"]}'],
    )
    _brancher(client, session, local)
    await client.put("/api/v1/ai/settings", json={"backend_preference": "local_only"})
    offre = await _ajouter_offre(client)

    premier = (await client.post(f"/api/v1/offers/{offre}/analysis/ai-summary")).json()
    second = (await client.post(f"/api/v1/offers/{offre}/analysis/ai-summary")).json()

    assert premier["summary"] == "Poste Python data." and premier["cache_hit"] is False
    assert second["cache_hit"] is True and Decimal(second["cost"]) == 0
    assert local.appels == 1


async def test_resume_ia_sans_ia_configuree_explique_quoi_faire(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    application = client._transport.app  # type: ignore[attr-defined]
    application.dependency_overrides[get_providers] = list
    application.dependency_overrides[get_gateway] = lambda: AIGateway(SessionPartagee(session), [])
    offre = await _ajouter_offre(client)

    reponse = await client.post(f"/api/v1/offers/{offre}/analysis/ai-summary")

    assert reponse.status_code == 409 and reponse.json()["error"]["code"] == "ai_not_configured"


async def test_le_resume_ia_n_envoie_pas_de_donnee_personnelle_a_un_palier_gratuit(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    gratuit = FakeProvider(
        "gemini-gratuit", reponses=['{"summary": "s", "key_points": []}'], entraine=True
    )
    _brancher(client, session, gratuit)
    await client.put("/api/v1/ai/settings", json={"backend_preference": "api_only"})
    await client.put("/api/v1/ai/budget", json={"daily": "1", "monthly": "10", "currency": "EUR"})
    await client.put("/api/v1/ai/consent", json={"accepted": True})
    offre = await _ajouter_offre(client)

    # Texte public d'une offre : le palier gratuit est autorisé (contains_personal_data=False).
    reponse = await client.post(f"/api/v1/offers/{offre}/analysis/ai-summary")

    assert reponse.status_code == 200 and reponse.json()["provider"] == "gemini-gratuit"
    assert gratuit.appels == 1


@pytest.mark.parametrize("sortie", ['{"summary": ""}', '{"autre": 1}', "pas du json"])
async def test_resume_ia_invalide_est_refuse(
    client: httpx.AsyncClient, session: AsyncSession, sortie: str
) -> None:
    _brancher(client, session, FakeProvider("ollama-test", ProviderKind.LOCAL, reponses=[sortie]))
    await client.put("/api/v1/ai/settings", json={"backend_preference": "local_only"})
    offre = await _ajouter_offre(client)

    reponse = await client.post(f"/api/v1/offers/{offre}/analysis/ai-summary")

    assert reponse.status_code == 502 and reponse.json()["error"]["code"] == "ai_invalid_output"
