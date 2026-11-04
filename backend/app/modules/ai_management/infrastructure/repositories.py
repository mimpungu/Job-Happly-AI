"""Repositories SQL du contexte ai_management."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai_management.domain.enums import BudgetPeriod, CallOutcome
from app.modules.ai_management.domain.models import (
    AIMode,
    BackendPreference,
    BudgetLimits,
    PersonalDataPolicy,
)
from app.modules.ai_management.infrastructure.models import (
    AIBudgetModel,
    AICacheEntryModel,
    AISettingsModel,
    AITaskBudgetModel,
    AIUsageModel,
)

# Un appel refusé par le budget ou servi par le cache ne coûte rien.
_RESULTATS_NON_FACTURES = (CallOutcome.BLOCKED_BUDGET.value, CallOutcome.CACHE_HIT.value)


class SqlAIUsageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, usage: AIUsageModel) -> None:
        self._session.add(usage)
        await self._session.flush()

    async def total_cost(
        self,
        *,
        owner_id: uuid.UUID,
        since: datetime,
        until: datetime,
        provider: str | None = None,
        task_type: str | None = None,
    ) -> Decimal:
        """Dépense sur [since, until[ : coût réel s'il est connu, sinon estimé."""
        cout = func.coalesce(AIUsageModel.actual_cost, AIUsageModel.estimated_cost)
        requete = select(func.coalesce(func.sum(cout), 0)).where(
            AIUsageModel.owner_id == owner_id,
            AIUsageModel.created_at >= since,
            AIUsageModel.created_at < until,
            AIUsageModel.outcome.not_in(_RESULTATS_NON_FACTURES),
        )
        if provider is not None:
            requete = requete.where(AIUsageModel.provider == provider)
        if task_type is not None:
            requete = requete.where(AIUsageModel.task_type == task_type)
        return Decimal(await self._session.scalar(requete) or 0)


# ------------------------------------------------------------------ réglages et plafonds

_DEFAUT_NIVEAU1 = Decimal("0.02")
_DEFAUT_NIVEAU2 = Decimal("0.30")
_SEUILS_PAR_DEFAUT = (50, 80, 100)


@dataclass(frozen=True, slots=True)
class AIConfig:
    """Réglages effectifs d'un propriétaire (valeurs par défaut si rien n'est enregistré)."""

    mode: AIMode
    preference: BackendPreference
    limits: BudgetLimits
    api_consent_at: datetime | None
    personal_data_policy: PersonalDataPolicy = PersonalDataPolicy.ALLOWED
    provider_daily_caps: Mapping[str, Decimal] = field(default_factory=dict)
    """Plafond journalier propre à un fournisseur (en plus des plafonds globaux)."""
    task_daily_caps: Mapping[str, Decimal] = field(default_factory=dict)
    """Plafond journalier propre à un type de tâche (en plus des plafonds globaux)."""


class SqlAIConfigRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, owner_id: uuid.UUID) -> AIConfig:
        reglages = await self._settings(owner_id)
        budgets = {
            b.period: b
            for b in (
                await self._session.execute(
                    select(AIBudgetModel).where(
                        AIBudgetModel.owner_id == owner_id, AIBudgetModel.provider.is_(None)
                    )
                )
            ).scalars()
        }
        quotidien = budgets.get(BudgetPeriod.DAILY.value)
        mensuel = budgets.get(BudgetPeriod.MONTHLY.value)
        reference = mensuel or quotidien
        return AIConfig(
            mode=AIMode(reglages.mode) if reglages else AIMode.ECONOMY,
            preference=BackendPreference(reglages.backend_preference)
            if reglages
            else BackendPreference.HYBRID,
            limits=BudgetLimits(
                daily=quotidien.amount if quotidien else None,
                monthly=mensuel.amount if mensuel else None,
                per_operation_level1=reglages.per_operation_level1 if reglages else _DEFAUT_NIVEAU1,
                per_operation_level2=reglages.per_operation_level2 if reglages else _DEFAUT_NIVEAU2,
                currency=reglages.currency if reglages else "EUR",
                alert_thresholds=tuple(sorted(reference.alert_thresholds))
                if reference
                else _SEUILS_PAR_DEFAUT,
            ),
            api_consent_at=reglages.api_consent_at if reglages else None,
            personal_data_policy=PersonalDataPolicy(reglages.personal_data_policy)
            if reglages
            else PersonalDataPolicy.ALLOWED,
            provider_daily_caps=await self._plafonds_fournisseurs(owner_id),
            task_daily_caps=await self._plafonds_taches(owner_id),
        )

    async def _plafonds_taches(self, owner_id: uuid.UUID) -> dict[str, Decimal]:
        lignes = await self._session.execute(
            select(AITaskBudgetModel.task_type, AITaskBudgetModel.daily_amount).where(
                AITaskBudgetModel.owner_id == owner_id
            )
        )
        return {tache: montant for tache, montant in lignes}  # noqa: C416 - Row, pas un tuple

    async def set_task_cap(
        self, owner_id: uuid.UUID, task_type: str, *, daily: Decimal | None, currency: str
    ) -> None:
        """Pose (ou retire, avec `None`) le plafond journalier d'un type de tâche."""
        existant = (
            await self._session.execute(
                select(AITaskBudgetModel).where(
                    AITaskBudgetModel.owner_id == owner_id,
                    AITaskBudgetModel.task_type == task_type,
                )
            )
        ).scalar_one_or_none()
        if daily is None:
            if existant is not None:
                await self._session.delete(existant)
        elif existant is None:
            self._session.add(
                AITaskBudgetModel(
                    owner_id=owner_id, task_type=task_type, daily_amount=daily, currency=currency
                )
            )
        else:
            existant.daily_amount = daily
            existant.currency = currency
        await self._session.flush()

    async def _plafonds_fournisseurs(self, owner_id: uuid.UUID) -> dict[str, Decimal]:
        lignes = await self._session.execute(
            select(AIBudgetModel.provider, AIBudgetModel.amount).where(
                AIBudgetModel.owner_id == owner_id,
                AIBudgetModel.provider.is_not(None),
                AIBudgetModel.period == BudgetPeriod.DAILY.value,
            )
        )
        return {fournisseur: montant for fournisseur, montant in lignes if fournisseur}

    async def set_provider_cap(
        self, owner_id: uuid.UUID, provider: str, *, daily: Decimal | None, currency: str
    ) -> None:
        """Pose (ou retire, avec `None`) le plafond journalier d'un fournisseur."""
        existant = (
            await self._session.execute(
                select(AIBudgetModel).where(
                    AIBudgetModel.owner_id == owner_id,
                    AIBudgetModel.period == BudgetPeriod.DAILY.value,
                    AIBudgetModel.provider == provider,
                )
            )
        ).scalar_one_or_none()
        if daily is None:
            if existant is not None:
                await self._session.delete(existant)
        elif existant is None:
            self._session.add(
                AIBudgetModel(
                    owner_id=owner_id,
                    period=BudgetPeriod.DAILY.value,
                    provider=provider,
                    amount=daily,
                    currency=currency,
                )
            )
        else:
            existant.amount = daily
            existant.currency = currency
        await self._session.flush()

    async def update_settings(
        self,
        owner_id: uuid.UUID,
        *,
        mode: AIMode | None = None,
        preference: BackendPreference | None = None,
        per_operation_level1: Decimal | None = None,
        per_operation_level2: Decimal | None = None,
    ) -> None:
        reglages = await self._settings_ou_creer(owner_id)
        if mode is not None:
            reglages.mode = mode.value
        if preference is not None:
            reglages.backend_preference = preference.value
        if per_operation_level1 is not None:
            reglages.per_operation_level1 = per_operation_level1
        if per_operation_level2 is not None:
            reglages.per_operation_level2 = per_operation_level2
        await self._session.flush()

    async def set_personal_data_policy(
        self, owner_id: uuid.UUID, policy: PersonalDataPolicy
    ) -> None:
        reglages = await self._settings_ou_creer(owner_id)
        reglages.personal_data_policy = policy.value
        await self._session.flush()

    async def set_consent(self, owner_id: uuid.UUID, at: datetime | None) -> None:
        reglages = await self._settings_ou_creer(owner_id)
        reglages.api_consent_at = at
        await self._session.flush()

    async def set_budget(
        self,
        owner_id: uuid.UUID,
        *,
        daily: Decimal,
        monthly: Decimal,
        currency: str,
        alert_thresholds: tuple[int, ...],
    ) -> None:
        for periode, montant in ((BudgetPeriod.DAILY, daily), (BudgetPeriod.MONTHLY, monthly)):
            existant = (
                await self._session.execute(
                    select(AIBudgetModel).where(
                        AIBudgetModel.owner_id == owner_id,
                        AIBudgetModel.period == periode.value,
                        AIBudgetModel.provider.is_(None),
                    )
                )
            ).scalar_one_or_none()
            if existant is None:
                self._session.add(
                    AIBudgetModel(
                        owner_id=owner_id,
                        period=periode.value,
                        provider=None,
                        amount=montant,
                        currency=currency,
                        alert_thresholds=list(alert_thresholds),
                    )
                )
            else:
                existant.amount = montant
                existant.currency = currency
                existant.alert_thresholds = list(alert_thresholds)
        reglages = await self._settings_ou_creer(owner_id)
        reglages.currency = currency
        await self._session.flush()

    async def _settings(self, owner_id: uuid.UUID) -> AISettingsModel | None:
        return (
            await self._session.execute(
                select(AISettingsModel).where(AISettingsModel.owner_id == owner_id)
            )
        ).scalar_one_or_none()

    async def _settings_ou_creer(self, owner_id: uuid.UUID) -> AISettingsModel:
        reglages = await self._settings(owner_id)
        if reglages is None:
            reglages = AISettingsModel(owner_id=owner_id)
            self._session.add(reglages)
            await self._session.flush()
            await self._session.refresh(reglages)
        return reglages


# ------------------------------------------------------------------ cache


class SqlAICacheRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, owner_id: uuid.UUID, key: str, now: datetime) -> dict[str, Any] | None:
        entree = (
            await self._session.execute(
                select(AICacheEntryModel).where(
                    AICacheEntryModel.owner_id == owner_id, AICacheEntryModel.cache_key == key
                )
            )
        ).scalar_one_or_none()
        if entree is None or (entree.expires_at is not None and entree.expires_at <= now):
            return None
        entree.hit_count += 1
        await self._session.flush()
        return entree.result

    async def put(
        self,
        owner_id: uuid.UUID,
        *,
        key: str,
        task_type: str,
        prompt_version: str,
        model: str,
        result: dict[str, Any],
        expires_at: datetime | None,
    ) -> None:
        # Upsert : une réponse expirée est remplacée, jamais dupliquée.
        requete = pg_insert(AICacheEntryModel).values(
            owner_id=owner_id,
            cache_key=key,
            task_type=task_type,
            prompt_version=prompt_version,
            model=model,
            result=result,
            expires_at=expires_at,
            hit_count=0,
        )
        await self._session.execute(
            requete.on_conflict_do_update(
                index_elements=["owner_id", "cache_key"],
                set_={"result": result, "expires_at": expires_at, "hit_count": 0},
            )
        )

    async def purge_expired(self, now: datetime) -> int:
        resultat = await self._session.execute(
            delete(AICacheEntryModel).where(
                AICacheEntryModel.expires_at.is_not(None), AICacheEntryModel.expires_at <= now
            )
        )
        return int(getattr(resultat, "rowcount", 0) or 0)


class SqlAIUsageReader:
    """Lectures du journal pour le tableau de bord (jamais le contenu des requêtes)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def recent(self, owner_id: uuid.UUID, limit: int) -> list[AIUsageModel]:
        requete = (
            select(AIUsageModel)
            .where(AIUsageModel.owner_id == owner_id)
            .order_by(AIUsageModel.created_at.desc(), AIUsageModel.id)
            .limit(limit)
        )
        return list((await self._session.execute(requete)).scalars())

    async def by_provider(
        self, owner_id: uuid.UUID, since: datetime, until: datetime
    ) -> dict[str, Decimal]:
        cout = func.coalesce(AIUsageModel.actual_cost, AIUsageModel.estimated_cost)
        requete = (
            select(AIUsageModel.provider, func.coalesce(func.sum(cout), 0))
            .where(
                AIUsageModel.owner_id == owner_id,
                AIUsageModel.created_at >= since,
                AIUsageModel.created_at < until,
                AIUsageModel.outcome.not_in(_RESULTATS_NON_FACTURES),
            )
            .group_by(AIUsageModel.provider)
        )
        return {p: Decimal(c) for p, c in (await self._session.execute(requete)).all()}
