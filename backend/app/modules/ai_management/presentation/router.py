"""Routes de réglage et de suivi de l'IA (`/api/v1/ai`). Aucun appel de modèle ici."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.api.dependencies import SessionDep as Session
from app.core.api.dependencies import get_owner_id
from app.modules.ai_management.application.providers import get_providers
from app.modules.ai_management.domain.models import AIMode, BackendPreference
from app.modules.ai_management.domain.provider import AIProvider
from app.modules.ai_management.infrastructure.repositories import (
    SqlAIConfigRepository,
    SqlAIUsageReader,
    SqlAIUsageRepository,
)

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])

Owner = Annotated[uuid.UUID, Depends(get_owner_id)]
Providers = Annotated[list[AIProvider], Depends(get_providers)]

_MONTANT_MAX = Decimal(1000)


class ProviderView(BaseModel):
    name: str
    kind: str
    models: list[str]


class SettingsResponse(BaseModel):
    mode: AIMode
    backend_preference: BackendPreference
    per_operation_level1: Decimal
    per_operation_level2: Decimal
    currency: str
    daily_budget: Decimal | None
    monthly_budget: Decimal | None
    alert_thresholds: list[int]
    budget_defined: bool
    api_consent: bool
    api_consent_at: datetime | None
    providers: list[ProviderView]
    paid_calls_possible: bool
    """Vrai seulement si une API est configurée, un plafond défini et le consentement donné."""


class SettingsBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: AIMode | None = None
    backend_preference: BackendPreference | None = None
    per_operation_level1: Decimal | None = Field(default=None, gt=0, le=_MONTANT_MAX)
    per_operation_level2: Decimal | None = Field(default=None, gt=0, le=_MONTANT_MAX)


class BudgetBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    daily: Decimal = Field(gt=0, le=_MONTANT_MAX, decimal_places=2)
    monthly: Decimal = Field(gt=0, le=_MONTANT_MAX, decimal_places=2)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    alert_thresholds: list[int] = Field(default_factory=lambda: [50, 80, 100], max_length=6)

    @field_validator("alert_thresholds")
    @classmethod
    def _seuils(cls, valeurs: list[int]) -> list[int]:
        if any(not 1 <= v <= 100 for v in valeurs):
            raise ValueError("Les seuils d'alerte sont des pourcentages entre 1 et 100.")
        return sorted(set(valeurs))


class ConsentBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool


class UsageRow(BaseModel):
    at: datetime
    provider: str
    model: str
    task_type: str
    level: int
    outcome: str
    cache_hit: bool
    input_tokens: int
    output_tokens: int
    cost: Decimal
    currency: str


class UsageResponse(BaseModel):
    currency: str
    spent_today: Decimal
    spent_month: Decimal
    daily_budget: Decimal | None
    monthly_budget: Decimal | None
    percent_today: Decimal | None
    percent_month: Decimal | None
    by_provider_month: dict[str, Decimal]
    recent: list[UsageRow]


def _debut_du_jour(maintenant: datetime) -> datetime:
    return maintenant.replace(hour=0, minute=0, second=0, microsecond=0)


async def _reglages(
    session: Session, owner_id: uuid.UUID, providers: list[AIProvider]
) -> SettingsResponse:
    config = await SqlAIConfigRepository(session).get(owner_id)
    limites = config.limits
    api_configuree = any(p.kind.value == "api" for p in providers)
    return SettingsResponse(
        mode=config.mode,
        backend_preference=config.preference,
        per_operation_level1=limites.per_operation_level1,
        per_operation_level2=limites.per_operation_level2,
        currency=limites.currency,
        daily_budget=limites.daily,
        monthly_budget=limites.monthly,
        alert_thresholds=list(limites.alert_thresholds),
        budget_defined=limites.is_defined,
        api_consent=config.api_consent_at is not None,
        api_consent_at=config.api_consent_at,
        providers=[
            ProviderView(name=p.name, kind=p.kind.value, models=sorted(p.pricing))
            for p in providers
        ],
        paid_calls_possible=(
            api_configuree and limites.is_defined and config.api_consent_at is not None
        ),
    )


@router.get("/settings", response_model=SettingsResponse)
async def get_settings(session: Session, owner_id: Owner, providers: Providers) -> SettingsResponse:
    return await _reglages(session, owner_id, providers)


@router.put("/settings", response_model=SettingsResponse)
async def put_settings(
    session: Session, owner_id: Owner, providers: Providers, body: SettingsBody
) -> SettingsResponse:
    await SqlAIConfigRepository(session).update_settings(
        owner_id,
        mode=body.mode,
        preference=body.backend_preference,
        per_operation_level1=body.per_operation_level1,
        per_operation_level2=body.per_operation_level2,
    )
    return await _reglages(session, owner_id, providers)


@router.put("/budget", response_model=SettingsResponse)
async def put_budget(
    session: Session, owner_id: Owner, providers: Providers, body: BudgetBody
) -> SettingsResponse:
    """Définit les plafonds. Seul l'utilisateur les modifie ; l'application ne les relève jamais."""
    await SqlAIConfigRepository(session).set_budget(
        owner_id,
        daily=body.daily,
        monthly=body.monthly,
        currency=body.currency,
        alert_thresholds=tuple(body.alert_thresholds),
    )
    return await _reglages(session, owner_id, providers)


@router.put("/consent", response_model=SettingsResponse)
async def put_consent(
    session: Session, owner_id: Owner, providers: Providers, body: ConsentBody
) -> SettingsResponse:
    await SqlAIConfigRepository(session).set_consent(
        owner_id, datetime.now(UTC) if body.accepted else None
    )
    return await _reglages(session, owner_id, providers)


@router.get("/usage", response_model=UsageResponse)
async def get_usage(session: Session, owner_id: Owner, limit: int = 25) -> UsageResponse:
    limit = max(1, min(limit, 100))
    maintenant = datetime.now(UTC)
    jusque = maintenant + timedelta(seconds=1)
    debut_jour = _debut_du_jour(maintenant)
    debut_mois = debut_jour.replace(day=1)
    config = await SqlAIConfigRepository(session).get(owner_id)
    depenses = SqlAIUsageRepository(session)
    aujourdhui = await depenses.total_cost(owner_id=owner_id, since=debut_jour, until=jusque)
    ce_mois = await depenses.total_cost(owner_id=owner_id, since=debut_mois, until=jusque)
    lecteur = SqlAIUsageReader(session)
    lignes = await lecteur.recent(owner_id, limit)
    limites = config.limits

    def pourcent(depense: Decimal, plafond: Decimal | None) -> Decimal | None:
        return None if plafond is None else (depense / plafond * 100).quantize(Decimal("0.1"))

    return UsageResponse(
        currency=limites.currency,
        spent_today=aujourdhui,
        spent_month=ce_mois,
        daily_budget=limites.daily,
        monthly_budget=limites.monthly,
        percent_today=pourcent(aujourdhui, limites.daily),
        percent_month=pourcent(ce_mois, limites.monthly),
        by_provider_month=await lecteur.by_provider(owner_id, debut_mois, jusque),
        recent=[
            UsageRow(
                at=ligne.created_at,
                provider=ligne.provider,
                model=ligne.model,
                task_type=ligne.task_type,
                level=ligne.level,
                outcome=ligne.outcome,
                cache_hit=ligne.cache_hit,
                input_tokens=ligne.input_tokens,
                output_tokens=ligne.output_tokens,
                cost=ligne.actual_cost if ligne.actual_cost is not None else ligne.estimated_cost,
                currency=ligne.currency,
            )
            for ligne in lignes
        ],
    )
