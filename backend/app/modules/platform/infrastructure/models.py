"""Utilisateur local (ADR-0008) et file de tâches de fond (ADR-0009)."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import Base, CreatedAtMixin, PrimaryKeyMixin, TimestampMixin, enum_check


class UserModel(PrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "users"

    display_name: Mapped[str | None] = mapped_column(nullable=True)


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEAD = "dead"


class JobModel(PrimaryKeyMixin, TimestampMixin, Base):
    """Tâche de fond. La clé d'idempotence empêche deux exécutions identiques simultanées."""

    __tablename__ = "jobs"
    __table_args__ = (
        enum_check("status_valid", "status", JobStatus),
        CheckConstraint("attempts >= 0 AND max_attempts >= 1", name="attempts_valid"),
        CheckConstraint("attempts <= max_attempts", name="attempts_within_max"),
        # Une seule tâche active (en attente ou en cours) par clé d'idempotence.
        Index(
            "uq_jobs_kind_idempotency_key_active",
            "kind",
            "idempotency_key",
            unique=True,
            postgresql_where=text("status IN ('queued','running')"),
        ),
        Index(
            "ix_jobs_status_run_at",
            "status",
            "run_at",
            postgresql_where=text("status = 'queued'"),
        ),
        Index("ix_jobs_locked_at", "locked_at", postgresql_where=text("status = 'running'")),
    )

    # Les tâches système (maintenance) n'ont pas de propriétaire.
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(80))
    idempotency_key: Mapped[str] = mapped_column(String(200))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    status: Mapped[str] = mapped_column(String(20), server_default=JobStatus.QUEUED.value)
    attempts: Mapped[int] = mapped_column(Integer, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, server_default="3")
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[str | None] = mapped_column(String(100))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
