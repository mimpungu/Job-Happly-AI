"""Le service du tableau de bord délègue à son dépôt avec une horloge injectable."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from app.modules.application_management.application.dashboard_service import DashboardService
from app.modules.application_management.domain.entities import (
    AIBudgetSummary,
    DashboardMetrics,
    Funnel,
    MonthlyTrend,
)
from app.modules.application_management.domain.enums import ApplicationStatus
from app.modules.application_management.domain.ports import DashboardRepositoryPort

MAINTENANT = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)


class EspionDepot(DashboardRepositoryPort):
    def __init__(self) -> None:
        self.appels: list[tuple[uuid.UUID, datetime]] = []

    async def get_dashboard_metrics(
        self, owner_id: uuid.UUID, *, now: datetime
    ) -> DashboardMetrics:
        self.appels.append((owner_id, now))
        return DashboardMetrics(
            display_name=None,
            total_offers_found=0,
            active_offers_count=0,
            active_offers_trend=MonthlyTrend(current=0, previous=0),
            new_offers_count=0,
            relevant_offers_count=None,
            relevance_threshold=70,
            top_matches=(),
            active_applications_count=0,
            applications_trend=MonthlyTrend(current=0, previous=0),
            applications_sent_count=0,
            interviews_count=0,
            response_rate=None,
            funnel=Funnel(offers=0, tracked=0, sent=0, responses=0, offers_received=0),
            applications_by_status=dict.fromkeys(ApplicationStatus, 0),
            interviews=(),
            ai_budget=AIBudgetSummary(spent=Decimal(0), limit=None, currency=None),
        )


async def test_le_service_transmet_le_proprietaire_et_l_horloge() -> None:
    depot, owner = EspionDepot(), uuid.uuid4()

    metrics = await DashboardService(depot, clock=lambda: MAINTENANT).get_dashboard(owner_id=owner)

    assert depot.appels == [(owner, MAINTENANT)]
    assert metrics.relevant_offers_count is None  # « pas de donnée » reste distinct de zéro
    assert metrics.response_rate is None


def test_variation_mensuelle_n_existe_pas_sans_mois_precedent() -> None:
    """Pas de division par zéro ni de « +∞ % » : sans référence, pas de variation."""
    assert MonthlyTrend(current=5, previous=0).percent is None
    assert MonthlyTrend(current=0, previous=0).percent is None


def test_variation_mensuelle_sur_donnees_reelles() -> None:
    assert MonthlyTrend(current=103, previous=100).percent == 3.0
    assert MonthlyTrend(current=87, previous=100).percent == -13.0
    assert MonthlyTrend(current=0, previous=4).percent == -100.0
    assert MonthlyTrend(current=3, previous=3).percent == 0.0
