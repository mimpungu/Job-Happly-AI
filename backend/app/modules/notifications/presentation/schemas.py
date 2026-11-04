"""Schémas Pydantic de présentation pour les notifications et le planificateur."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.modules.notifications.domain.enums import (
    NotificationKind,
    ScheduledTaskType,
    ScheduleFrequency,
)


class NotificationResponse(BaseModel):
    """Représentation d'une notification."""

    id: uuid.UUID
    owner_id: uuid.UUID
    kind: NotificationKind
    title: str
    body: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    read_at: datetime | None = None
    created_at: datetime
    is_read: bool


class NotificationListResponse(BaseModel):
    """Liste paginée de notifications avec compteurs."""

    items: list[NotificationResponse]
    total: int
    unread_count: int


class UnreadCountResponse(BaseModel):
    """Compteur des notifications non lues."""

    unread_count: int


class NotificationPreferencesRequest(BaseModel):
    """Mise à jour des préférences de notification."""

    in_app_enabled: bool | None = None
    email_enabled: bool | None = None
    email_recipient: str | None = Field(None, max_length=320)
    email_consent_given: bool | None = None
    notify_new_offers: bool | None = None
    notify_relevant_matches: bool | None = None
    min_relevance_score: int | None = Field(None, ge=0, le=100)
    notify_search_errors: bool | None = None
    notify_follow_up_reminders: bool | None = None
    notify_ai_budget_alerts: bool | None = None
    daily_digest_enabled: bool | None = None
    daily_digest_time: str | None = Field(None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    timezone: str | None = Field(None, max_length=60)


class NotificationPreferencesResponse(BaseModel):
    """Préférences actuelles de l'utilisateur."""

    id: uuid.UUID
    owner_id: uuid.UUID
    in_app_enabled: bool
    email_enabled: bool
    email_recipient: str | None = None
    email_consent_given: bool
    notify_new_offers: bool
    notify_relevant_matches: bool
    min_relevance_score: int
    notify_search_errors: bool
    notify_follow_up_reminders: bool
    notify_ai_budget_alerts: bool
    daily_digest_enabled: bool
    daily_digest_time: str
    timezone: str


_MAX_PAYLOAD_CHARS = 4096


def _payload_borne(valeur: dict[str, Any] | None) -> dict[str, Any] | None:
    """Une charge utile libre reste petite : elle est stockée telle quelle."""
    if valeur is not None and len(json.dumps(valeur, default=str)) > _MAX_PAYLOAD_CHARS:
        raise ValueError("La charge utile dépasse 4 Ko.")
    return valeur


class ScheduledTaskCreateRequest(BaseModel):
    """Création d'une tâche planifiée."""

    task_type: ScheduledTaskType
    frequency: ScheduleFrequency
    interval_minutes: int | None = Field(None, gt=0)
    target_hour: int | None = Field(None, ge=0, le=23)
    target_minute: int | None = Field(None, ge=0, le=59)
    timezone: str = Field("Europe/Paris", max_length=60)
    payload: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True

    _borne = field_validator("payload")(_payload_borne)


class ScheduledTaskUpdateRequest(BaseModel):
    """Modification d'une tâche planifiée existante."""

    frequency: ScheduleFrequency | None = None
    interval_minutes: int | None = Field(None, gt=0)
    target_hour: int | None = Field(None, ge=0, le=23)
    target_minute: int | None = Field(None, ge=0, le=59)
    timezone: str | None = Field(None, max_length=60)
    payload: dict[str, Any] | None = None
    enabled: bool | None = None

    _borne = field_validator("payload")(_payload_borne)


class ScheduledTaskResponse(BaseModel):
    """Représentation d'une tâche planifiée."""

    id: uuid.UUID
    owner_id: uuid.UUID | None = None
    task_type: ScheduledTaskType
    frequency: ScheduleFrequency
    interval_minutes: int | None = None
    target_hour: int | None = None
    target_minute: int | None = None
    timezone: str
    payload: dict[str, Any] = Field(default_factory=dict)
    enabled: bool
    last_run_at: datetime | None = None
    next_run_at: datetime
    created_at: datetime
    updated_at: datetime


class TriggerTaskResponse(BaseModel):
    """Résultat du déclenchement immédiat d'une tâche."""

    job_id: uuid.UUID
    status: str = "queued"


class DailyDigestResponse(BaseModel):
    """Données du résumé quotidien."""

    date: str
    new_offers_count: int
    top_offers_count: int
    follow_ups_due_count: int
    active_applications_count: int
    ai_spent_today: float
    sample_offers: list[dict[str, Any]] = Field(default_factory=list)


class JobAuditItem(BaseModel):
    """Entrée d'historique d'un job de fond."""

    id: str
    owner_id: str | None = None
    kind: str
    idempotency_key: str
    status: str
    attempts: int
    max_attempts: int
    run_at: str | None = None
    locked_at: str | None = None
    locked_by: str | None = None
    finished_at: str | None = None
    last_error: str | None = None
    created_at: str | None = None


class JobHistoryResponse(BaseModel):
    """Historique des exécutions de tâches de fond."""

    items: list[JobAuditItem]
    total: int
