"""Tests unitaires du service de notifications et des préférences."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from app.modules.notifications.application.notification_service import NotificationService
from app.modules.notifications.domain.entities import (
    Notification,
    NotificationPreferences,
)
from app.modules.notifications.domain.enums import NotificationKind
from app.modules.notifications.domain.exceptions import (
    EmailConsentRequiredError,
    NotificationNotFoundError,
)
from app.modules.notifications.domain.ports import (
    NotificationPreferencesRepositoryPort,
    NotificationRepositoryPort,
)
from app.modules.notifications.infrastructure.email_sender import SafeEmailSender

T0 = datetime(2026, 11, 4, 12, 0, 0, tzinfo=UTC)


class InMemoryNotificationRepository(NotificationRepositoryPort):
    def __init__(self) -> None:
        self._items: dict[uuid.UUID, Notification] = {}

    async def create(
        self,
        *,
        owner_id: uuid.UUID,
        kind: NotificationKind,
        title: str,
        body: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> Notification:
        notif_id = uuid.uuid4()
        notif = Notification(
            id=notif_id,
            owner_id=owner_id,
            kind=kind,
            title=title,
            body=body,
            payload=payload or {},
            read_at=None,
            created_at=T0,
        )
        self._items[notif_id] = notif
        return notif

    async def get_by_id(
        self,
        *,
        owner_id: uuid.UUID,
        notification_id: uuid.UUID,
    ) -> Notification | None:
        notif = self._items.get(notification_id)
        if notif and notif.owner_id == owner_id:
            return notif
        return None

    async def list(
        self,
        *,
        owner_id: uuid.UUID,
        unread_only: bool = False,
        kind: NotificationKind | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Notification], int]:
        items = [n for n in self._items.values() if n.owner_id == owner_id]
        if unread_only:
            items = [n for n in items if n.read_at is None]
        if kind is not None:
            items = [n for n in items if n.kind == kind]
        return items[offset : offset + limit], len(items)

    async def count_unread(self, *, owner_id: uuid.UUID) -> int:
        return sum(1 for n in self._items.values() if n.owner_id == owner_id and n.read_at is None)

    async def mark_as_read(
        self,
        *,
        owner_id: uuid.UUID,
        notification_id: uuid.UUID,
        read_at: datetime | None = None,
    ) -> Notification:
        notif = self._items.get(notification_id)
        if notif is None or notif.owner_id != owner_id:
            raise NotificationNotFoundError("Notification introuvable.")
        updated = Notification(
            id=notif.id,
            owner_id=notif.owner_id,
            kind=notif.kind,
            title=notif.title,
            body=notif.body,
            payload=notif.payload,
            read_at=read_at or T0,
            created_at=notif.created_at,
        )
        self._items[notification_id] = updated
        return updated

    async def mark_all_as_read(
        self,
        *,
        owner_id: uuid.UUID,
        read_at: datetime | None = None,
    ) -> int:
        count = 0
        for notif_id, notif in list(self._items.items()):
            if notif.owner_id == owner_id and notif.read_at is None:
                self._items[notif_id] = Notification(
                    id=notif.id,
                    owner_id=notif.owner_id,
                    kind=notif.kind,
                    title=notif.title,
                    body=notif.body,
                    payload=notif.payload,
                    read_at=read_at or T0,
                    created_at=notif.created_at,
                )
                count += 1
        return count

    async def delete(
        self,
        *,
        owner_id: uuid.UUID,
        notification_id: uuid.UUID,
    ) -> bool:
        notif = self._items.get(notification_id)
        if notif and notif.owner_id == owner_id:
            del self._items[notification_id]
            return True
        return False


class InMemoryPreferencesRepository(NotificationPreferencesRepositoryPort):
    def __init__(self) -> None:
        self._prefs: dict[uuid.UUID, NotificationPreferences] = {}

    async def get(self, *, owner_id: uuid.UUID) -> NotificationPreferences:
        if owner_id not in self._prefs:
            self._prefs[owner_id] = NotificationPreferences(
                id=uuid.uuid4(),
                owner_id=owner_id,
            )
        return self._prefs[owner_id]

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
        actuel = await self.get(owner_id=owner_id)
        maj = NotificationPreferences(
            id=actuel.id,
            owner_id=owner_id,
            in_app_enabled=in_app_enabled if in_app_enabled is not None else actuel.in_app_enabled,
            email_enabled=email_enabled if email_enabled is not None else actuel.email_enabled,
            email_recipient=(
                email_recipient if email_recipient is not None else actuel.email_recipient
            ),
            email_consent_given=(
                email_consent_given
                if email_consent_given is not None
                else actuel.email_consent_given
            ),
            notify_new_offers=(
                notify_new_offers if notify_new_offers is not None else actuel.notify_new_offers
            ),
            notify_relevant_matches=(
                notify_relevant_matches
                if notify_relevant_matches is not None
                else actuel.notify_relevant_matches
            ),
            min_relevance_score=(
                min_relevance_score
                if min_relevance_score is not None
                else actuel.min_relevance_score
            ),
            notify_search_errors=(
                notify_search_errors
                if notify_search_errors is not None
                else actuel.notify_search_errors
            ),
            notify_follow_up_reminders=(
                notify_follow_up_reminders
                if notify_follow_up_reminders is not None
                else actuel.notify_follow_up_reminders
            ),
            notify_ai_budget_alerts=(
                notify_ai_budget_alerts
                if notify_ai_budget_alerts is not None
                else actuel.notify_ai_budget_alerts
            ),
            daily_digest_enabled=(
                daily_digest_enabled
                if daily_digest_enabled is not None
                else actuel.daily_digest_enabled
            ),
            daily_digest_time=(
                daily_digest_time if daily_digest_time is not None else actuel.daily_digest_time
            ),
            timezone=timezone if timezone is not None else actuel.timezone,
        )
        self._prefs[owner_id] = maj
        return maj


class TestNotificationService:
    @pytest.fixture
    def owner_id(self) -> uuid.UUID:
        return uuid.uuid4()

    @pytest.fixture
    def notif_repo(self) -> InMemoryNotificationRepository:
        return InMemoryNotificationRepository()

    @pytest.fixture
    def prefs_repo(self) -> InMemoryPreferencesRepository:
        return InMemoryPreferencesRepository()

    @pytest.fixture
    def email_sender(self) -> SafeEmailSender:
        return SafeEmailSender(configured=True)

    @pytest.fixture
    def service(
        self,
        notif_repo: InMemoryNotificationRepository,
        prefs_repo: InMemoryPreferencesRepository,
        email_sender: SafeEmailSender,
    ) -> NotificationService:
        return NotificationService(
            notification_repo=notif_repo,
            preferences_repo=prefs_repo,
            email_sender=email_sender,
            clock=lambda: T0,
        )

    async def test_cree_notification_in_app(
        self,
        service: NotificationService,
        owner_id: uuid.UUID,
    ) -> None:
        notif = await service.notify(
            owner_id=owner_id,
            kind=NotificationKind.NEW_OFFERS,
            title="3 nouvelles offres",
            body="Offres trouvées pour Python",
        )
        assert notif is not None
        assert notif.kind == NotificationKind.NEW_OFFERS
        assert not notif.is_read

        count = await service.count_unread(owner_id=owner_id)
        assert count == 1

    async def test_respecte_seuil_pertinence(
        self,
        service: NotificationService,
        owner_id: uuid.UUID,
    ) -> None:
        # Seuil par défaut = 70
        refusee = await service.notify(
            owner_id=owner_id,
            kind=NotificationKind.RELEVANT_MATCH,
            title="Match moyen",
            match_score=65,
        )
        assert refusee is None

        acceptee = await service.notify(
            owner_id=owner_id,
            kind=NotificationKind.RELEVANT_MATCH,
            title="Match fort",
            match_score=85,
        )
        assert acceptee is not None
        assert acceptee.title == "Match fort"

    async def test_envoi_email_strictement_avec_consentement(
        self,
        service: NotificationService,
        prefs_repo: InMemoryPreferencesRepository,
        email_sender: SafeEmailSender,
        owner_id: uuid.UUID,
    ) -> None:
        # Sans consentement
        await prefs_repo.update(
            owner_id=owner_id,
            email_enabled=True,
            email_recipient="user@test.org",
            email_consent_given=False,
        )
        await service.notify(
            owner_id=owner_id,
            kind=NotificationKind.SEARCH_ERROR,
            title="Erreur de recherche",
        )
        assert len(email_sender.outbox) == 0

        # Avec consentement explicite
        await prefs_repo.update(
            owner_id=owner_id,
            email_enabled=True,
            email_recipient="user@test.org",
            email_consent_given=True,
        )
        await service.notify(
            owner_id=owner_id,
            kind=NotificationKind.SEARCH_ERROR,
            title="Erreur de recherche",
        )
        assert len(email_sender.outbox) == 1
        assert email_sender.outbox[0].recipient == "user@test.org"

    async def test_marquer_comme_lu_et_suppression(
        self,
        service: NotificationService,
        owner_id: uuid.UUID,
    ) -> None:
        n1 = await service.notify(
            owner_id=owner_id,
            kind=NotificationKind.FOLLOW_UP_REMINDER,
            title="Relance 1",
        )
        n2 = await service.notify(
            owner_id=owner_id,
            kind=NotificationKind.FOLLOW_UP_REMINDER,
            title="Relance 2",
        )
        assert n1 is not None and n2 is not None

        assert await service.count_unread(owner_id=owner_id) == 2

        lue = await service.mark_as_read(owner_id=owner_id, notification_id=n1.id)
        assert lue.is_read
        assert await service.count_unread(owner_id=owner_id) == 1

        modifies = await service.mark_all_as_read(owner_id=owner_id)
        assert modifies == 1
        assert await service.count_unread(owner_id=owner_id) == 0

        deleted = await service.delete_notification(owner_id=owner_id, notification_id=n1.id)
        assert deleted is True
        assert await service.delete_notification(owner_id=owner_id, notification_id=n1.id) is False

    async def test_email_sender_rejette_sans_consentement(
        self,
        email_sender: SafeEmailSender,
    ) -> None:
        with pytest.raises(EmailConsentRequiredError):
            await email_sender.send_email(
                recipient="test@example.com",
                subject="Sujet",
                body="Corps",
                consent_verified=False,
            )
