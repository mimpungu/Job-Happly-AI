"""Service applicatif pour la gestion des notifications et des alertes utilisateur."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from app.modules.notifications.domain.entities import (
    Notification,
    NotificationPreferences,
)
from app.modules.notifications.domain.enums import NotificationKind
from app.modules.notifications.domain.ports import (
    EmailSenderPort,
    NotificationPreferencesRepositoryPort,
    NotificationRepositoryPort,
)
from app.modules.notifications.domain.rules import should_notify

logger = logging.getLogger("happly.notifications.service")


def _now() -> datetime:
    return datetime.now(UTC)


class NotificationService:
    """Orchestre la création, consultation et diffusion des notifications."""

    def __init__(
        self,
        notification_repo: NotificationRepositoryPort,
        preferences_repo: NotificationPreferencesRepositoryPort,
        email_sender: EmailSenderPort,
        *,
        clock: Callable[[], datetime] = _now,
    ) -> None:
        self._notification_repo = notification_repo
        self._preferences_repo = preferences_repo
        self._email_sender = email_sender
        self._clock = clock

    async def notify(
        self,
        *,
        owner_id: uuid.UUID,
        kind: NotificationKind,
        title: str,
        body: str | None = None,
        payload: dict[str, Any] | None = None,
        match_score: int | None = None,
    ) -> Notification | None:
        """Émet une notification si les préférences de l'utilisateur l'autorisent.

        Retourne l'entité Notification si créée in-app, sinon None.
        """
        preferences = await self._preferences_repo.get(owner_id=owner_id)
        if not should_notify(preferences, kind, match_score=match_score):
            logger.debug(
                "Notification filtrée par les préférences",
                extra={"owner_id": str(owner_id), "kind": kind.value},
            )
            return None

        creee: Notification | None = None
        if preferences.in_app_enabled:
            creee = await self._notification_repo.create(
                owner_id=owner_id,
                kind=kind,
                title=title,
                body=body,
                payload=payload,
            )

        if (
            preferences.email_enabled
            and preferences.email_consent_given
            and preferences.email_recipient
        ):
            corps = body or title
            sujet = f"[Happly AI] {title}"
            try:
                await self._email_sender.send_email(
                    recipient=preferences.email_recipient,
                    subject=sujet,
                    body=corps,
                    consent_verified=True,
                )
            except Exception as err:
                logger.error(
                    "Échec d'envoi de la notification e-mail",
                    extra={"error": str(err), "owner_id": str(owner_id)},
                )

        return creee

    async def list_notifications(
        self,
        *,
        owner_id: uuid.UUID,
        unread_only: bool = False,
        kind: NotificationKind | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Notification], int]:
        return await self._notification_repo.list(
            owner_id=owner_id,
            unread_only=unread_only,
            kind=kind,
            limit=limit,
            offset=offset,
        )

    async def count_unread(self, *, owner_id: uuid.UUID) -> int:
        return await self._notification_repo.count_unread(owner_id=owner_id)

    async def mark_as_read(
        self,
        *,
        owner_id: uuid.UUID,
        notification_id: uuid.UUID,
    ) -> Notification:
        return await self._notification_repo.mark_as_read(
            owner_id=owner_id,
            notification_id=notification_id,
            read_at=self._clock(),
        )

    async def mark_all_as_read(self, *, owner_id: uuid.UUID) -> int:
        return await self._notification_repo.mark_all_as_read(
            owner_id=owner_id,
            read_at=self._clock(),
        )

    async def delete_notification(
        self,
        *,
        owner_id: uuid.UUID,
        notification_id: uuid.UUID,
    ) -> bool:
        return await self._notification_repo.delete(
            owner_id=owner_id,
            notification_id=notification_id,
        )

    async def get_preferences(self, *, owner_id: uuid.UUID) -> NotificationPreferences:
        return await self._preferences_repo.get(owner_id=owner_id)

    async def update_preferences(
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
        return await self._preferences_repo.update(
            owner_id=owner_id,
            in_app_enabled=in_app_enabled,
            email_enabled=email_enabled,
            email_recipient=email_recipient,
            email_consent_given=email_consent_given,
            notify_new_offers=notify_new_offers,
            notify_relevant_matches=notify_relevant_matches,
            min_relevance_score=min_relevance_score,
            notify_search_errors=notify_search_errors,
            notify_follow_up_reminders=notify_follow_up_reminders,
            notify_ai_budget_alerts=notify_ai_budget_alerts,
            daily_digest_enabled=daily_digest_enabled,
            daily_digest_time=daily_digest_time,
            timezone=timezone,
        )
