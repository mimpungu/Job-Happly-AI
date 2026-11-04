from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import Base, OwnedMixin, PrimaryKeyMixin, TimestampMixin, enum_check
from app.modules.interview_preparation.domain.enums import (
    InterviewFormat,
    InterviewOutcome,
    InterviewStage,
    SimulationStatus,
)


class InterviewPreparationModel(PrimaryKeyMixin, TimestampMixin, OwnedMixin, Base):
    """Préparation d'une candidature : une seule, régénérable à la demande."""

    __tablename__ = "interview_preparations"
    __table_args__ = (
        Index(
            "uq_interview_preparations_owner_id_application_id",
            "owner_id",
            "application_id",
            unique=True,
        ),
    )

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE")
    )
    content: Mapped[dict[str, Any]] = mapped_column(JSONB)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))


class InterviewSimulationModel(PrimaryKeyMixin, TimestampMixin, OwnedMixin, Base):
    """Simulation : questions copiées, la régénération de la préparation ne les change pas."""

    __tablename__ = "interview_simulations"
    __table_args__ = (
        enum_check("status_valid", "status", SimulationStatus),
        Index("ix_interview_simulations_owner_id_application_id", "owner_id", "application_id"),
    )

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(
        String(20), server_default=SimulationStatus.IN_PROGRESS.value
    )
    questions: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    answers: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class InterviewModel(PrimaryKeyMixin, TimestampMixin, OwnedMixin, Base):
    """Fiche d'un entretien réel (planifié, passé ou annulé)."""

    __tablename__ = "interviews"
    __table_args__ = (
        enum_check("stage_valid", "stage", InterviewStage),
        enum_check("format_valid", "format", InterviewFormat),
        enum_check("outcome_valid", "outcome", InterviewOutcome),
        Index("ix_interviews_owner_id_application_id", "owner_id", "application_id"),
        Index(
            "ix_interviews_owner_id_scheduled_at",
            "owner_id",
            "scheduled_at",
            postgresql_where=text("scheduled_at IS NOT NULL"),
        ),
    )

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE")
    )
    stage: Mapped[str] = mapped_column(String(20), server_default=InterviewStage.OTHER.value)
    format: Mapped[str] = mapped_column(String(20), server_default=InterviewFormat.OTHER.value)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    location: Mapped[str | None] = mapped_column(String(300))
    interviewers: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    notes: Mapped[str | None] = mapped_column(Text)
    outcome: Mapped[str] = mapped_column(String(20), server_default=InterviewOutcome.PENDING.value)
    feedback_notes: Mapped[str | None] = mapped_column(Text)
    follow_up_draft: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
