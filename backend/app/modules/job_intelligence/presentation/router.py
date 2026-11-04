"""Routes du score de correspondance (`/api/v1`) : pondérations, score d'une offre, recalcul."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt
from starlette.types import ExceptionHandler

from app.core.api.dependencies import SessionDep, get_owner_id
from app.core.api.errors import error_response
from app.modules.job_discovery.domain.search import ScoringUnavailableError
from app.modules.job_intelligence.application.matching_service import (
    RecomputeReport,
    WeightsView,
)
from app.modules.job_intelligence.application.ports import NoValidatedProfileError
from app.modules.job_intelligence.domain.matching.models import (
    CRITERION_LABELS,
    Criterion,
    MatchResult,
)
from app.modules.job_intelligence.domain.matching.weights import InvalidWeightsError
from app.modules.job_intelligence.infrastructure.composition import build_matching_service

router = APIRouter(prefix="/api/v1", tags=["job-intelligence"])
Owner = Annotated[uuid.UUID, Depends(get_owner_id)]


class CriterionInfo(BaseModel):
    key: str
    label: str
    weight: Decimal
    default_weight: Decimal


class WeightsResponse(BaseModel):
    criteria: list[CriterionInfo]
    version: str
    is_default: bool

    @classmethod
    def of(cls, vue: WeightsView) -> WeightsResponse:
        return cls(
            criteria=[
                CriterionInfo(
                    key=c.value,
                    label=CRITERION_LABELS[c],
                    weight=vue.weights.get(c),
                    default_weight=vue.defaults.get(c),
                )
                for c in Criterion
            ],
            version=vue.version,
            is_default=vue.is_default,
        )


class WeightsBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Nombres stricts : « beaucoup » ou `true` ne sont pas des poids.
    weights: dict[str, StrictInt | StrictFloat] = Field(max_length=50)


class MatchResponse(BaseModel):
    result: MatchResult
    profile_version: int
    computed_at: datetime


@router.get("/matching/weights", response_model=WeightsResponse)
async def get_weights(session: SessionDep, owner_id: Owner) -> WeightsResponse:
    return WeightsResponse.of(await build_matching_service(session).weights(owner_id=owner_id))


@router.put("/matching/weights", response_model=WeightsResponse)
async def put_weights(session: SessionDep, owner_id: Owner, body: WeightsBody) -> WeightsResponse:
    """Enregistre des pondérations personnalisées ; les scores seront recalculés à la demande."""
    vue = await build_matching_service(session).set_weights(
        owner_id=owner_id, brutes=dict(body.weights)
    )
    return WeightsResponse.of(vue)


@router.delete("/matching/weights", response_model=WeightsResponse)
async def reset_weights(session: SessionDep, owner_id: Owner) -> WeightsResponse:
    return WeightsResponse.of(
        await build_matching_service(session).reset_weights(owner_id=owner_id)
    )


@router.get("/offers/{offer_id}/match", response_model=MatchResponse)
async def get_offer_match(
    session: SessionDep, owner_id: Owner, offer_id: uuid.UUID
) -> MatchResponse:
    """Score détaillé et explicable d'une offre (indicatif, pas une prédiction d'embauche)."""
    sortie = await build_matching_service(session).match_offer(owner_id=owner_id, offer_id=offer_id)
    return MatchResponse(
        result=sortie.result, profile_version=sortie.profile_version, computed_at=sortie.computed_at
    )


@router.post("/matching/recompute", response_model=RecomputeReport)
async def recompute(session: SessionDep, owner_id: Owner) -> RecomputeReport:
    """Recalcule le score de toutes les offres actives (profil validé, pondérations courantes)."""
    return await build_matching_service(session).recompute(owner_id=owner_id)


def _simple(statut: int, code: str) -> ExceptionHandler:
    async def _repondre(_: Request, erreur: Exception) -> JSONResponse:
        # Messages de ces erreurs : rédigés pour l'utilisateur, sans détail interne.
        return error_response(statut, code, str(erreur))

    return _repondre


def register_matching_errors(application: FastAPI) -> None:
    application.add_exception_handler(NoValidatedProfileError, _simple(409, "no_validated_profile"))
    application.add_exception_handler(ScoringUnavailableError, _simple(409, "scoring_unavailable"))
    application.add_exception_handler(InvalidWeightsError, _simple(422, "invalid_weights"))
