"""Tests unitaires du service DashboardService (TASK-014-21, 22)."""

import uuid

from app.modules.application_management.application.dashboard_service import (
    DashboardService,
)
from app.modules.application_management.domain.entities import DashboardMetrics
from app.modules.application_management.domain.ports import DashboardRepositoryPort


class InMemoryDashboardRepository(DashboardRepositoryPort):
    async def get_dashboard_metrics(self, owner_id: uuid.UUID) -> DashboardMetrics:
        return DashboardMetrics(
            total_offers_found=142,
            new_offers_count=18,
            relevant_offers_count=35,
            applications_sent_count=10,
            interviews_count=3,
            response_rate=30.0,
            ai_budget_consumed_cents=450,
            ai_budget_limit_cents=1000,
        )


async def test_recuperation_dashboard_metrics() -> None:
    repo = InMemoryDashboardRepository()
    service = DashboardService(repo)
    owner = uuid.uuid4()

    metrics = await service.get_dashboard(owner_id=owner)
    assert metrics.total_offers_found == 142
    assert metrics.new_offers_count == 18
    assert metrics.applications_sent_count == 10
    assert metrics.interviews_count == 3
    assert metrics.response_rate == 30.0
    assert metrics.ai_budget_consumed_cents == 450
    assert metrics.ai_budget_limit_cents == 1000
