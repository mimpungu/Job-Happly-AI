"""Interfaces de persistance et services externes (ports) du module notifications."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from app.modules.notifications.domain.entities import (
    Notification,
    NotificationPreferences,
    ScheduledTask,
)
from app.modules.notifications.domain.enums import (
    NotificationKind,
    ScheduledTaskType,
    ScheduleFrequency,
)


class NotificationRepositoryPort(ABC):
    """Port de persistance pour les notifications utilisateur."""

    @abstractmethod
    async def create(
        self,
        *,
        owner_id: uuid.UUID,
        kind: NotificationKind,
        title: str,
        body: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> Notification:
        """Enregistre une nouvelle notification."""

    @abstractmethod
    async def get_by_id(
        self,
        *,
        owner_id: uuid.UUID,
        notification_id: uuid.UUID,
    ) -> Notification | None:
        """Récupère une notification par son identifiant et son propriétaire."""

    @abstractmethod
    async def list(
        self,
        *,
        owner_id: uuid.UUID,
        unread_only: bool = False,
        kind: NotificationKind | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Notification], int]:
        """Liste les notifications filtrées avec pagination et total."""

    @abstractmethod
    async def count_unread(self, *, owner_id: uuid.UUID) -> int:
        """Compte le nombre de notifications non lues."""

    @abstractmethod
    async def mark_as_read(
        self,
        *,
        owner_id: uuid.UUID,
        notification_id: uuid.UUID,
        read_at: datetime | None = None,
    ) -> Notification:
        """Marque une notification comme lue."""

    @abstractmethod
    async def mark_all_as_read(
        self,
        *,
        owner_id: uuid.UUID,
        read_at: datetime | None = None,
    ) -> int:
        """Marque toutes les notifications non lues comme lues. Retourne le nombre modifié."""

    @abstractmethod
    async def delete(
        self,
        *,
        owner_id: uuid.UUID,
        notification_id: uuid.UUID,
    ) -> bool:
        """Supprime une notification. Retourne True si elle a été supprimée."""


class NotificationPreferencesRepositoryPort(ABC):
    """Port de persistance pour les préférences de notification."""

    @abstractmethod
    async def get(self, *, owner_id: uuid.UUID) -> NotificationPreferences:
        """Récupère les préférences de l'utilisateur, ou les crée par défaut si absentes."""

    @abstractmethod
    async def update(
        self,
        *,
        owner_id: uuid.UUID,
        in_app_enabled: bool | None = None,
        email_enabled: bool | None = None,
        email_recipient: str | None = None,
        email_consent_given: bool | None = None,
        notify_new_offers: bool | None = None,
        notify_relevant_matches: bool | None = None,
        min_relevance_score: int | None = None,
        notify_search_errors: bool | None = None,
        notify_follow_up_reminders: bool | None = None,
        notify_ai_budget_alerts: bool | None = None,
        daily_digest_enabled: bool | None = None,
        daily_digest_time: str | None = None,
        timezone: str | None = None,
    ) -> NotificationPreferences:
        """Met à jour les préférences de notification."""


class ScheduledTaskRepositoryPort(ABC):
    """Port de persistance pour les tâches planifiées du scheduler."""

    @abstractmethod
    async def create(
        self,
        *,
        owner_id: uuid.UUID | None,
        task_type: ScheduledTaskType,
        frequency: ScheduleFrequency,
        interval_minutes: int | None = None,
        target_hour: int | None = None,
        target_minute: int | None = None,
        timezone: str = "Europe/Paris",
        payload: dict[str, Any] | None = None,
        enabled: bool = True,
        next_run_at: datetime,
    ) -> ScheduledTask:
        """Crée une nouvelle définition de tâche planifiée."""

    @abstractmethod
    async def get_by_id(
        self,
        *,
        task_id: uuid.UUID,
        owner_id: uuid.UUID | None = None,
    ) -> ScheduledTask | None:
        """Récupère une tâche planifiée par identifiant."""

    @abstractmethod
    async def list_by_owner(
        self,
        *,
        owner_id: uuid.UUID | None,
        enabled_only: bool = False,
    ) -> list[ScheduledTask]:
        """Liste les tâches planifiées de l'utilisateur ou du système."""

    @abstractmethod
    async def list_due_tasks(
        self,
        *,
        as_of: datetime,
    ) -> list[ScheduledTask]:
        """Récupère les tâches actives dont l'échéance `next_run_at` est échue."""

    @abstractmethod
    async def update_run_status(
        self,
        *,
        task_id: uuid.UUID,
        last_run_at: datetime,
        next_run_at: datetime,
    ) -> ScheduledTask:
        """Met à jour les horodatages après exécution d'une tâche."""

    @abstractmethod
    async def update(
        self,
        *,
        task_id: uuid.UUID,
        owner_id: uuid.UUID | None = None,
        frequency: ScheduleFrequency | None = None,
        interval_minutes: int | None = None,
        target_hour: int | None = None,
        target_minute: int | None = None,
        timezone: str | None = None,
        payload: dict[str, Any] | None = None,
        enabled: bool | None = None,
        next_run_at: datetime | None = None,
    ) -> ScheduledTask:
        """Met à jour la configuration d'une tâche planifiée."""

    @abstractmethod
    async def delete(
        self,
        *,
        task_id: uuid.UUID,
        owner_id: uuid.UUID | None = None,
    ) -> bool:
        """Supprime une tâche planifiée."""


class EmailSenderPort(ABC):
    """Port d'expédition d'e-mails (soumis au consentement explicite)."""

    @abstractmethod
    async def send_email(
        self,
        *,
        recipient: str,
        subject: str,
        body: str,
        consent_verified: bool,
    ) -> bool:
        """Envoie un message e-mail si et seulement si le consentement est vérifié."""
