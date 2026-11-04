"""Schémas de l'API de préparation aux entretiens (EPIC 016).

Le contenu généré (questions, trames, retours) réutilise les modèles immuables du domaine : ils
sont déjà le contrat, une copie ne ferait que dériver.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

from app.modules.interview_preparation.domain.enums import (
    AssistMode,
    InterviewFormat,
    InterviewOutcome,
    InterviewStage,
    SimulationStatus,
)
from app.modules.interview_preparation.domain.models import (
    FollowUpDraft,
    PreparationContent,
    Question,
    SimulationAnswer,
    SimulationSummary,
)

Language = Annotated[str, StringConstraints(pattern=r"^[a-z]{2,3}(-[A-Z]{2})?$")]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]


class GeneratePreparationRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    language: Language = "fr"
    mode: AssistMode = AssistMode.NONE
    """`none` (défaut) : sans IA ; `local` ou `ai` : questions en plus, à la demande."""


class PreparationResponse(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    content: PreparationContent
    meta: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class StartSimulationRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    question_count: int = Field(default=6, ge=1, le=15)


class AnswerRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: LongText
    mode: AssistMode = AssistMode.NONE
    language: Language = "fr"


class SimulationResponse(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    status: SimulationStatus
    questions: list[Question]
    answers: list[SimulationAnswer]
    summary: SimulationSummary
    created_at: datetime | None
    completed_at: datetime | None


class InterviewRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    stage: InterviewStage = InterviewStage.OTHER
    format: InterviewFormat = InterviewFormat.OTHER
    scheduled_at: AwareDatetime | None = None
    """Avec fuseau obligatoire : « 9 h » ne veut rien dire sans lui."""
    location: Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)] | None = None
    interviewers: list[
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    ] = Field(default_factory=list, max_length=10)
    notes: Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)] | None = None
    outcome: InterviewOutcome = InterviewOutcome.PENDING
    feedback_notes: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)] | None
    ) = None


class InterviewResponse(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    stage: InterviewStage
    format: InterviewFormat
    scheduled_at: datetime | None
    location: str | None
    interviewers: list[str]
    notes: str | None
    outcome: InterviewOutcome
    feedback_notes: str | None
    follow_up_draft: FollowUpDraft | None
    created_at: datetime
    updated_at: datetime


class FollowUpDraftRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    language: Language = "fr"


class ScheduleFollowUpRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    follow_up_at: AwareDatetime | None = None
    """Absente : la date proposée par le brouillon (deux jours après l'entretien)."""


class ScheduledFollowUpResponse(BaseModel):
    follow_up_at: datetime
