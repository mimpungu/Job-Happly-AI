"""Repositories SQL du contexte ai_management."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai_management.domain.enums import CallOutcome
from app.modules.ai_management.infrastructure.models import AIUsageModel

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
        return Decimal(await self._session.scalar(requete) or 0)
