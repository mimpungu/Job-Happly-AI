"""Ports de la préparation aux entretiens : persistance, lecture des sources, IA, suivi CRM."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol

from app.modules.interview_preparation.domain.enums import AssistMode, SimulationStatus
from app.modules.interview_preparation.domain.models import (
    FollowUpDraft,
    InterviewData,
    OfferFacts,
    PreparationContent,
    Question,
    SimulationAnswer,
)

if TYPE_CHECKING:
    from app.modules.candidate_profile.domain.profile import ProfileDocument


@dataclass(frozen=True)
class ApplicationContext:
    application_id: uuid.UUID
    offer: OfferFacts
    status: str
    cv_version_id: uuid.UUID | None


@dataclass(frozen=True)
class PreparationRecord:
    id: uuid.UUID
    application_id: uuid.UUID
    content: PreparationContent
    meta: dict[str, Any]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class SimulationRecord:
    id: uuid.UUID
    application_id: uuid.UUID
    status: SimulationStatus
    questions: tuple[Question, ...]
    answers: dict[str, SimulationAnswer] = field(default_factory=dict)
    created_at: datetime | None = None
    completed_at: datetime | None = None


@dataclass(frozen=True)
class InterviewRecord:
    id: uuid.UUID
    application_id: uuid.UUID
    data: InterviewData
    follow_up_draft: FollowUpDraft | None
    created_at: datetime
    updated_at: datetime


class SourcesPort(Protocol):
    async def validated_profile(self, *, owner_id: uuid.UUID) -> ProfileDocument: ...

    async def application_context(
        self, *, owner_id: uuid.UUID, application_id: uuid.UUID
    ) -> ApplicationContext: ...


class PreparationRepositoryPort(Protocol):
    async def upsert_preparation(
        self,
        *,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        content: PreparationContent,
        meta: dict[str, Any],
    ) -> PreparationRecord: ...

    async def get_preparation(
        self, *, owner_id: uuid.UUID, application_id: uuid.UUID
    ) -> PreparationRecord | None: ...


class SimulationRepositoryPort(Protocol):
    async def create_simulation(
        self, *, owner_id: uuid.UUID, application_id: uuid.UUID, questions: Sequence[Question]
    ) -> SimulationRecord: ...

    async def get_simulation(
        self, *, owner_id: uuid.UUID, simulation_id: uuid.UUID, for_update: bool = False
    ) -> SimulationRecord | None: ...

    async def list_simulations(
        self, *, owner_id: uuid.UUID, application_id: uuid.UUID
    ) -> list[SimulationRecord]: ...

    async def update_simulation(self, *, owner_id: uuid.UUID, record: SimulationRecord) -> None: ...

    async def delete_simulation(self, *, owner_id: uuid.UUID, simulation_id: uuid.UUID) -> bool: ...


class InterviewRepositoryPort(Protocol):
    async def create_interview(
        self, *, owner_id: uuid.UUID, application_id: uuid.UUID, data: InterviewData
    ) -> InterviewRecord: ...

    async def get_interview(
        self, *, owner_id: uuid.UUID, interview_id: uuid.UUID
    ) -> InterviewRecord | None: ...

    async def list_interviews(
        self,
        *,
        owner_id: uuid.UUID,
        application_id: uuid.UUID | None = None,
        scheduled_after: datetime | None = None,
    ) -> list[InterviewRecord]: ...

    async def update_interview(
        self,
        *,
        owner_id: uuid.UUID,
        interview_id: uuid.UUID,
        data: InterviewData,
        follow_up_draft: FollowUpDraft | None,
    ) -> InterviewRecord: ...


class ApplicationTrackerPort(Protocol):
    """Écritures dans le suivi des candidatures : l'historique de la candidature reste unique."""

    async def record_interview(
        self,
        *,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        description: str,
        when: datetime | None,
    ) -> None: ...

    async def schedule_follow_up(
        self,
        *,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        follow_up_at: datetime,
        notes: str | None,
    ) -> None: ...


class CoachPort(Protocol):
    """IA facultative ; lève `CoachUnavailableError` si elle ne peut pas répondre."""

    async def extra_questions(
        self, *, owner_id: uuid.UUID, offer: OfferFacts, language: str, mode: AssistMode
    ) -> list[Question]: ...

    async def review_answer(
        self,
        *,
        owner_id: uuid.UUID,
        question: Question,
        answer: str,
        language: str,
        mode: AssistMode,
    ) -> tuple[str, ...]: ...
