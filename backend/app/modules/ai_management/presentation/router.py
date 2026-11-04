"""Routes de réglage et de suivi de l'IA (`/api/v1/ai`). Aucun appel de modèle ici."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.core.api.dependencies import SessionDep as Session
from app.core.api.dependencies import get_owner_id
from app.core.api.errors import error_response
from app.modules.ai_management.domain.errors import (
    AIDisabledError,
    AIError,
    AINotConfiguredError,
    BudgetExceededError,
    BudgetNotDefinedError,
    ConsentRequiredError,
    IncompleteOutputError,
    InvalidOutputError,
    PersonalDataBlockedError,
    ProviderFailureError,
)
from app.modules.ai_management.domain.models import AIMode, AIRequest, BackendPreference
from app.modules.ai_management.domain.provider import AIProvider
from app.modules.ai_management.infrastructure.repositories import (
    SqlAIConfigRepository,
    SqlAIUsageReader,
    SqlAIUsageRepository,
)
from app.modules.ai_management.presentation.dependencies import GatewayDep, Providers

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])

Owner = Annotated[uuid.UUID, Depends(get_owner_id)]


_MONTANT_MAX = Decimal(1000)


class ProviderView(BaseModel):
    name: str
    kind: str
    models: list[str]
    key_hint: str | None = None
    """Fin masquée de la clé d'API (jamais la clé) : permet de vérifier une rotation."""
    uses_data_for_training: bool
    """Palier gratuit : le fournisseur peut réutiliser et faire relire les contenus."""


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
            ProviderView(
                name=p.name,
                kind=p.kind.value,
                models=sorted(p.pricing),
                key_hint=getattr(p, "key_hint", None),
                uses_data_for_training=p.uses_data_for_training,
            )
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


# ------------------------------------------------------------------ test de bout en bout

_SCHEMA_TEST = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "skills": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "skills"],
}
# Texte public et fictif : le test n'envoie jamais de donnée personnelle.
_OFFRE_TEST = (
    "Développeur Python (H/F) - Paris. Au sein de l'équipe données, vous concevez des API "
    "FastAPI, écrivez des requêtes SQL sur PostgreSQL et déployez avec Docker. Une première "
    "expérience de 2 ans est attendue. CDI, télétravail partiel."
)


class _SortieTest(BaseModel):
    summary: str = Field(min_length=1)
    skills: list[str]


class TestRequest(BaseModel):
    __test__ = False  # Pydantic, pas une classe de test pytest
    model_config = ConfigDict(extra="forbid")

    level: int = Field(default=1, ge=1, le=2)


class TestResponse(BaseModel):
    __test__ = False
    provider: str
    model: str
    cache_hit: bool
    cost: Decimal
    input_tokens: int
    output_tokens: int
    summary: str
    skills: list[str]
    crossed_thresholds: list[int]


def _valider_test(brut: object) -> _SortieTest:
    try:
        return _SortieTest.model_validate(brut)
    except ValidationError as erreur:
        raise ValueError(str(erreur)) from erreur


@router.post("/test", response_model=TestResponse)
async def run_test(gateway: GatewayDep, owner_id: Owner, body: TestRequest) -> TestResponse:
    """Passe un petit texte d'offre fictif par la passerelle : valide la chaîne complète
    (routage, consentement, plafonds, appel, validation, journal, cache)."""
    requete = AIRequest(
        task_type="platform_test",
        level=body.level,
        prompt_version="test-v1",
        instructions=(
            "Résume l'offre en une phrase et liste ses compétences techniques. "
            "Réponds en JSON avec les clés summary et skills."
        ),
        content=_OFFRE_TEST,
        max_output_tokens=400,
        json_schema=_SCHEMA_TEST,
        contains_personal_data=False,
    )
    resultat = await gateway.run(owner_id=owner_id, request=requete, validate=_valider_test)
    return TestResponse(
        provider=resultat.provider,
        model=resultat.model,
        cache_hit=resultat.cache_hit,
        cost=resultat.cost,
        input_tokens=resultat.input_tokens,
        output_tokens=resultat.output_tokens,
        summary=resultat.value.summary,
        skills=resultat.value.skills,
        crossed_thresholds=list(resultat.crossed_thresholds),
    )


_ERREURS_HTTP: dict[type[AIError], int] = {
    AIDisabledError: 409,
    AINotConfiguredError: 409,
    PersonalDataBlockedError: 409,
    ConsentRequiredError: 409,
    BudgetNotDefinedError: 409,
    BudgetExceededError: 409,
    ProviderFailureError: 502,
    InvalidOutputError: 502,
    IncompleteOutputError: 502,
}


def register_ai_errors(application: FastAPI) -> None:
    """Chaque erreur IA devient une réponse normalisée avec un code stable (message fixe)."""

    async def _repondre(_: Request, erreur: Exception) -> JSONResponse:
        assert isinstance(erreur, AIError)  # noqa: S101 - garanti par l'enregistrement ci-dessous
        statut = next((s for t, s in _ERREURS_HTTP.items() if isinstance(erreur, t)), 500)
        return error_response(statut, erreur.code, str(erreur))

    for type_erreur in _ERREURS_HTTP:
        application.add_exception_handler(type_erreur, _repondre)
