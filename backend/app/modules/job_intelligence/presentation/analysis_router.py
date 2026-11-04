"""Routes d'analyse d'une offre (`/api/v1/offers/{id}/analysis`)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, ValidationError

from app.core.api.dependencies import SessionDep, get_owner_id
from app.modules.ai_management.domain.models import AIRequest
from app.modules.ai_management.presentation.dependencies import GatewayDep
from app.modules.job_intelligence.infrastructure.composition import build_analysis_service
from app.modules.job_intelligence.infrastructure.readers import SqlJobOfferReader

router = APIRouter(prefix="/api/v1", tags=["job-intelligence"])
Owner = Annotated[uuid.UUID, Depends(get_owner_id)]


class AnalysisResponse(BaseModel):
    analysis_id: uuid.UUID
    computed_at: datetime
    reused: bool
    """Vrai si l'annonce n'a pas changé depuis la dernière analyse (rien n'a été recalculé)."""
    analysis: dict[str, Any]


class AnalysisVersion(BaseModel):
    analysis_id: uuid.UUID
    computed_at: datetime
    version: str
    content_hash: str


@router.get("/offers/{offer_id}/analysis", response_model=AnalysisResponse)
async def get_analysis(
    session: SessionDep, owner_id: Owner, offer_id: uuid.UUID
) -> AnalysisResponse:
    """Analyse par règles (gratuite, sans IA), calculée au premier appel puis réutilisée."""
    stockee = await build_analysis_service(session).analyze(owner_id=owner_id, offer_id=offer_id)
    return AnalysisResponse(
        analysis_id=stockee.analysis_id,
        computed_at=stockee.created_at,
        reused=stockee.reused,
        analysis=stockee.result,
    )


@router.get("/offers/{offer_id}/analysis/history", response_model=list[AnalysisVersion])
async def get_analysis_history(
    session: SessionDep, owner_id: Owner, offer_id: uuid.UUID
) -> list[AnalysisVersion]:
    """Analyses successives de l'offre (une par version de l'annonce ou des règles)."""
    historique = await build_analysis_service(session).history(owner_id=owner_id, offer_id=offer_id)
    return [
        AnalysisVersion(
            analysis_id=h.analysis_id,
            computed_at=h.created_at,
            version=str(h.result.get("version")),
            content_hash=h.content_hash,
        )
        for h in historique
    ]


# ------------------------------------------------------------------ résumé par IA (facultatif)

_SCHEMA_RESUME = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "key_points": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "key_points"],
}
_INSTRUCTIONS_RESUME = (
    "Résume cette offre d'emploi en français, en trois phrases au maximum, puis donne au plus "
    "cinq points clés. N'utilise que des informations écrites dans l'offre : n'invente ni "
    "salaire, ni avantage, ni exigence. Réponds en JSON avec les clés summary et key_points."
)
_MAX_TEXTE = 6000


class _Resume(BaseModel):
    summary: str = Field(min_length=1, max_length=1200)
    key_points: list[str] = Field(max_length=8)


def _valider_resume(brut: object) -> _Resume:
    try:
        return _Resume.model_validate(brut)
    except ValidationError as erreur:
        raise ValueError(str(erreur)) from erreur


class AISummaryResponse(BaseModel):
    summary: str
    key_points: list[str]
    provider: str
    model: str
    cache_hit: bool
    """Vrai si ce résumé existait déjà pour ce texte : aucun appel, aucun coût."""
    cost: Decimal


@router.post("/offers/{offer_id}/analysis/ai-summary", response_model=AISummaryResponse)
async def ai_summary(
    session: SessionDep, owner_id: Owner, offer_id: uuid.UUID, gateway: GatewayDep
) -> AISummaryResponse:
    """Résumé par IA, via la passerelle : consentement, plafonds, cache et journal s'appliquent.

    Seul le texte public de l'offre est transmis (jamais le CV ni le profil). Le cache est indexé
    par le contenu : une annonce modifiée est résumée à nouveau, une inchangée ne coûte rien.
    """
    offre = await SqlJobOfferReader(session).get(owner_id=owner_id, offer_id=offer_id)
    requete = AIRequest(
        task_type="offer_summary",
        level=1,
        prompt_version="offer-summary-v1",
        instructions=_INSTRUCTIONS_RESUME,
        content=f"Intitulé : {offre.title}\n\n{offre.description[:_MAX_TEXTE]}",
        max_output_tokens=600,
        json_schema=_SCHEMA_RESUME,
        contains_personal_data=False,
    )
    resultat = await gateway.run(owner_id=owner_id, request=requete, validate=_valider_resume)
    return AISummaryResponse(
        summary=resultat.value.summary,
        key_points=resultat.value.key_points,
        provider=resultat.provider,
        model=resultat.model,
        cache_hit=resultat.cache_hit,
        cost=resultat.cost,
    )
