"""Tableau de bord (TASK-014-21, 22) : indicateurs sur données réelles, `None` sinon."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.application_management.domain.entities import DashboardMetrics
    from app.modules.application_management.domain.ports import DashboardRepositoryPort


class DashboardService:
    def __init__(
        self,
        repository: DashboardRepositoryPort,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repository = repository
        self._clock = clock

    async def get_dashboard(self, *, owner_id: uuid.UUID) -> DashboardMetrics:
        return await self._repository.get_dashboard_metrics(owner_id, now=self._clock())
