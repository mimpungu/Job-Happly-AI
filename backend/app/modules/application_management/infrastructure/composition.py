"""Assemblage des services du suivi de candidatures (utilisé par les routes)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.modules.application_management.application.dashboard_service import DashboardService
from app.modules.application_management.application.service import ApplicationTrackingService
from app.modules.application_management.infrastructure.dashboard_repository import (
    SQLAlchemyDashboardRepository,
)
from app.modules.application_management.infrastructure.readers import (
    SqlDocumentVersionReader,
    SqlOfferReader,
)
from app.modules.application_management.infrastructure.repository import (
    SQLAlchemyApplicationRepository,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def build_application_tracking_service(session: AsyncSession) -> ApplicationTrackingService:
    return ApplicationTrackingService(
        repository=SQLAlchemyApplicationRepository(session),
        offers=SqlOfferReader(session),
        documents=SqlDocumentVersionReader(session),
    )


def build_dashboard_service(session: AsyncSession) -> DashboardService:
    return DashboardService(SQLAlchemyDashboardRepository(session))
