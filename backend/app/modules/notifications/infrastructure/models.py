from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import Base, CreatedAtMixin, OwnedMixin, PrimaryKeyMixin, TimestampMixin


class NotificationModel(PrimaryKeyMixin, CreatedAtMixin, OwnedMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_owner_id_read_at_created_at", "owner_id", "read_at", "created_at"),
    )

    kind: Mapped[str] = mapped_column(String(60))
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NotificationPreferenceModel(PrimaryKeyMixin, TimestampMixin, OwnedMixin, Base):
    """Préférences de notification pour un propriétaire."""

    __tablename__ = "notification_preferences"
    __table_args__ = (
        Index("uq_notification_preferences_owner_id", "owner_id", unique=True),
        CheckConstraint(
            "min_relevance_score >= 0 AND min_relevance_score <= 100",
            name="min_relevance_score_range",
        ),
    )

    in_app_enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    email_enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    email_recipient: Mapped[str | None] = mapped_column(String(320), nullable=True)
    email_consent_given: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    notify_new_offers: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    notify_relevant_matches: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    min_relevance_score: Mapped[int] = mapped_column(Integer, server_default="70")
    notify_search_errors: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    notify_follow_up_reminders: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    notify_ai_budget_alerts: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    daily_digest_enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    daily_digest_time: Mapped[str] = mapped_column(String(10), server_default="08:00")
    timezone: Mapped[str] = mapped_column(String(60), server_default="Europe/Paris")


class ScheduledTaskModel(PrimaryKeyMixin, TimestampMixin, Base):
    """Définition d'une tâche planifiée récurrente."""

    __tablename__ = "scheduled_tasks"
    __table_args__ = (
        Index("ix_scheduled_tasks_enabled_next_run_at", "enabled", "next_run_at"),
        Index("ix_scheduled_tasks_owner_id_task_type", "owner_id", "task_type"),
    )

    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    task_type: Mapped[str] = mapped_column(String(60))
    frequency: Mapped[str] = mapped_column(String(30))
    interval_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_hour: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timezone: Mapped[str] = mapped_column(String(60), server_default="Europe/Paris")
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
