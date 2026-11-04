"""Implémentation SQLAlchemy du repository des préférences de notification."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.domain.entities import NotificationPreferences
from app.modules.notifications.domain.ports import NotificationPreferencesRepositoryPort
from app.modules.notifications.infrastructure.models import NotificationPreferenceModel


def _to_entity(model: NotificationPreferenceModel) -> NotificationPreferences:
    return NotificationPreferences(
        id=model.id,
        owner_id=model.owner_id,
        in_app_enabled=model.in_app_enabled,
        email_enabled=model.email_enabled,
        email_recipient=model.email_recipient,
        email_consent_given=model.email_consent_given,
        notify_new_offers=model.notify_new_offers,
        notify_relevant_matches=model.notify_relevant_matches,
        min_relevance_score=model.min_relevance_score,
        notify_search_errors=model.notify_search_errors,
        notify_follow_up_reminders=model.notify_follow_up_reminders,
        notify_ai_budget_alerts=model.notify_ai_budget_alerts,
        daily_digest_enabled=model.daily_digest_enabled,
        daily_digest_time=model.daily_digest_time,
        timezone=model.timezone,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SQLAlchemyNotificationPreferencesRepository(NotificationPreferencesRepositoryPort):
    """Repository persistant pour les préférences de notification."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, *, owner_id: uuid.UUID) -> NotificationPreferences:
        stmt = select(NotificationPreferenceModel).where(
            NotificationPreferenceModel.owner_id == owner_id
        )
        model = await self._session.scalar(stmt)
        if model is None:
            model = NotificationPreferenceModel(owner_id=owner_id)
            self._session.add(model)
            await self._session.flush()
        return _to_entity(model)

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
        stmt = select(NotificationPreferenceModel).where(
            NotificationPreferenceModel.owner_id == owner_id
        )
        model = await self._session.scalar(stmt)
        if model is None:
            model = NotificationPreferenceModel(owner_id=owner_id)
            self._session.add(model)

        updates: dict[str, Any] = {
            "in_app_enabled": in_app_enabled,
            "email_enabled": email_enabled,
            "email_recipient": email_recipient,
            "email_consent_given": email_consent_given,
            "notify_new_offers": notify_new_offers,
            "notify_relevant_matches": notify_relevant_matches,
            "min_relevance_score": min_relevance_score,
            "notify_search_errors": notify_search_errors,
            "notify_follow_up_reminders": notify_follow_up_reminders,
            "notify_ai_budget_alerts": notify_ai_budget_alerts,
            "daily_digest_enabled": daily_digest_enabled,
            "daily_digest_time": daily_digest_time,
            "timezone": timezone,
        }

        for attr, val in updates.items():
            if val is not None:
                setattr(model, attr, val)

        await self._session.flush()
        return _to_entity(model)
