"""Assemblage des services de préparation aux entretiens (utilisé par les routes)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai_management.application.gateway import AIGateway
from app.modules.interview_preparation.application.interview_service import InterviewService
from app.modules.interview_preparation.application.preparation_service import PreparationService
from app.modules.interview_preparation.application.simulation_service import SimulationService
from app.modules.interview_preparation.infrastructure.ai_coach import GatewayInterviewCoach
from app.modules.interview_preparation.infrastructure.repository import SqlInterviewRepository
from app.modules.interview_preparation.infrastructure.sources import SqlInterviewSources
from app.modules.interview_preparation.infrastructure.tracker import ApplicationTracker


def build_preparation_service(
    session: AsyncSession, gateway: AIGateway | None = None
) -> PreparationService:
    return PreparationService(
        SqlInterviewSources(session),
        SqlInterviewRepository(session),
        GatewayInterviewCoach(gateway) if gateway else None,
    )


def build_simulation_service(
    session: AsyncSession, gateway: AIGateway | None = None
) -> SimulationService:
    depot = SqlInterviewRepository(session)
    return SimulationService(
        SqlInterviewSources(session),
        depot,
        depot,
        GatewayInterviewCoach(gateway) if gateway else None,
    )


def build_interview_service(session: AsyncSession) -> InterviewService:
    return InterviewService(
        SqlInterviewSources(session), SqlInterviewRepository(session), ApplicationTracker(session)
    )
