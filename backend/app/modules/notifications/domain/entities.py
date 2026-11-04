"""Entités et objets-valeurs du module notifications et planification."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.modules.notifications.domain.enums import (
    NotificationKind,
    ScheduledTaskType,
    ScheduleFrequency,
)


@dataclass(frozen=True, slots=True)
class Notification:
    """Notification utilisateur."""

    id: uuid.UUID
    owner_id: uuid.UUID
    kind: NotificationKind
    title: str
    body: str | None
    payload: dict[str, Any]
    read_at: datetime | None
    created_at: datetime

    @property
    def is_read(self) -> bool:
        """Indique si la notification a déjà été consultée."""
        return self.read_at is not None


@dataclass(frozen=True, slots=True)
class NotificationPreferences:
    """Préférences de réception des notifications et des alertes."""

    id: uuid.UUID
    owner_id: uuid.UUID
    in_app_enabled: bool = True
    email_enabled: bool = False
    email_recipient: str | None = None
    email_consent_given: bool = False
    notify_new_offers: bool = True
    notify_relevant_matches: bool = True
    min_relevance_score: int = 70
    notify_search_errors: bool = True
    notify_follow_up_reminders: bool = True
    notify_ai_budget_alerts: bool = True
    daily_digest_enabled: bool = True
    daily_digest_time: str = "08:00"
    timezone: str = "Europe/Paris"
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ScheduledTask:
    """Tâche automatisée planifiée selon une règle de récurrence."""

    id: uuid.UUID
    owner_id: uuid.UUID | None
    task_type: ScheduledTaskType
    frequency: ScheduleFrequency
    interval_minutes: int | None
    target_hour: int | None
    target_minute: int | None
    timezone: str
    payload: dict[str, Any]
    enabled: bool
    last_run_at: datetime | None
    next_run_at: datetime
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class DailyDigestSummary:
    """Synthèse consolidée des activités et métriques pour le résumé quotidien."""

    date: str
    new_offers_count: int
    top_offers_count: int
    follow_ups_due_count: int
    active_applications_count: int
    ai_spent_today: Decimal = field(default_factory=lambda: Decimal("0.0000"))
    ai_daily_cap: Decimal | None = None
    ai_currency: str = "EUR"
    sample_offers: tuple[dict[str, Any], ...] = ()
