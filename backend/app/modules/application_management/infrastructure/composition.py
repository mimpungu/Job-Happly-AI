"""Fabriques d'injection de dépendances pour le suivi des candidatures (EPIC 014)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.modules.application_management.application.dashboard_service import (
    DashboardService,
)
from app.modules.application_management.application.service import (
    ApplicationTrackingService,
)
from app.modules.application_management.infrastructure.repository import (
    SQLAlchemyApplicationRepository,
    SQLAlchemyDashboardRepository,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def build_application_tracking_service(session: AsyncSession) -> ApplicationTrackingService:
    """Construit une instance de ApplicationTrackingService branchée sur la session SQLAlchemy."""
    repository = SQLAlchemyApplicationRepository(session)
    return ApplicationTrackingService(repository=repository)


def build_dashboard_service(session: AsyncSession) -> DashboardService:
    """Construit une instance de DashboardService branchée sur la session SQLAlchemy."""
    repository = SQLAlchemyDashboardRepository(session)
    return DashboardService(repository=repository)

