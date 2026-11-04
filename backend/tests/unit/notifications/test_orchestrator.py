"""Tests unitaires des gestionnaires de tâches de fond et de l'orchestrateur."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.modules.job_discovery.domain.saved_search import SavedSearchNotFoundError
from app.modules.notifications.application.orchestrator import AutomationJobHandlers
from app.modules.notifications.application.ports import DueFollowUp, SavedSearchInfo
from app.modules.notifications.domain.enums import NotificationKind, ScheduledTaskType
from app.modules.platform.infrastructure.job_queue import ReservedJob
from tests.unit.notifications.fakes import FakeFacts

T0 = datetime(2026, 11, 4, 14, 0, 0, tzinfo=UTC)


class TestAutomationJobHandlers:
    @pytest.fixture
    def owner_id(self) -> uuid.UUID:
        return uuid.uuid4()

    @pytest.fixture
    def facts(self) -> FakeFacts:
        return FakeFacts()

    @pytest.fixture
    def mock_notifications(self) -> AsyncMock:
        serv = AsyncMock()
        serv.notify = AsyncMock()
        return serv

    @pytest.fixture
    def mock_queue(self) -> AsyncMock:
        q = AsyncMock()
        q.recover_stale = AsyncMock(return_value=2)
        return q

    @pytest.fixture
    def handlers(
        self,
        facts: FakeFacts,
        mock_notifications: AsyncMock,
        mock_queue: AsyncMock,
    ) -> AutomationJobHandlers:
        return AutomationJobHandlers(
            facts=facts,
            notification_service=mock_notifications,
            job_queue=mock_queue,
            clock=lambda: T0,
        )

    async def test_handle_recurring_search_emet_notification(
        self,
        handlers: AutomationJobHandlers,
        facts: FakeFacts,
        mock_notifications: AsyncMock,
        owner_id: uuid.UUID,
    ) -> None:
        saved_search_id = uuid.uuid4()
        facts.searches[saved_search_id] = SavedSearchInfo("Offres Python Paris", True)
        facts.recent_offers = 4

        job = ReservedJob(
            id=uuid.uuid4(),
            kind="recurring_search",
            payload={"saved_search_id": str(saved_search_id)},
            owner_id=owner_id,
            attempts=1,
            max_attempts=3,
        )

        await handlers.handle_recurring_search(job)

        mock_notifications.notify.assert_awaited_once()
        call_kwargs = mock_notifications.notify.await_args.kwargs
        assert call_kwargs["kind"] == NotificationKind.NEW_OFFERS
        assert "4 nouvelle(s) offre(s)" in call_kwargs["body"]
        assert call_kwargs["payload"]["new_offers_count"] == 4

    async def test_handle_follow_up_check_emet_rappels(
        self,
        handlers: AutomationJobHandlers,
        facts: FakeFacts,
        mock_notifications: AsyncMock,
        owner_id: uuid.UUID,
    ) -> None:
        facts.follow_ups = [
            DueFollowUp(uuid.uuid4(), uuid.uuid4(), "Software Engineer", "Acme Corp")
        ]

        job = ReservedJob(
            id=uuid.uuid4(),
            kind="follow_up_check",
            payload={},
            owner_id=owner_id,
            attempts=1,
            max_attempts=3,
        )

        await handlers.handle_follow_up_check(job)

        mock_notifications.notify.assert_awaited_once()
        call_kwargs = mock_notifications.notify.await_args.kwargs
        assert call_kwargs["kind"] == NotificationKind.FOLLOW_UP_REMINDER
        assert "Acme Corp" in call_kwargs["title"]
        assert call_kwargs["payload"]["company"] == "Acme Corp"

    async def test_handle_ai_budget_check_emet_alerte(
        self,
        handlers: AutomationJobHandlers,
        facts: FakeFacts,
        mock_notifications: AsyncMock,
        owner_id: uuid.UUID,
    ) -> None:
        facts.ai_spent = Decimal("2.5000")  # au-delà du seuil d'alerte de 1.0000

        job = ReservedJob(
            id=uuid.uuid4(),
            kind="ai_budget_check",
            payload={},
            owner_id=owner_id,
            attempts=1,
            max_attempts=3,
        )

        await handlers.handle_ai_budget_check(job)

        mock_notifications.notify.assert_awaited_once()
        call_kwargs = mock_notifications.notify.await_args.kwargs
        assert call_kwargs["kind"] == NotificationKind.AI_BUDGET_ALERT
        assert "2.5000 EUR" in call_kwargs["body"]

    async def test_handle_stale_jobs_cleanup(
        self,
        handlers: AutomationJobHandlers,
        mock_queue: AsyncMock,
    ) -> None:
        job = ReservedJob(
            id=uuid.uuid4(),
            kind="stale_jobs_cleanup",
            payload={},
            owner_id=None,
            attempts=1,
            max_attempts=3,
        )
        await handlers.handle_stale_jobs_cleanup(job)
        mock_queue.recover_stale.assert_awaited_once()


def _job(kind: str, owner: uuid.UUID | None, payload: dict[str, str] | None = None) -> ReservedJob:
    return ReservedJob(
        id=uuid.uuid4(),
        kind=kind,
        payload=payload or {},
        owner_id=owner,
        attempts=1,
        max_attempts=3,
    )


class TestCasLimites:
    @pytest.fixture
    def parts(self) -> tuple[AutomationJobHandlers, FakeFacts, AsyncMock]:
        facts, notifications = FakeFacts(), AsyncMock()
        handlers = AutomationJobHandlers(
            facts=facts, notification_service=notifications, job_queue=AsyncMock(), clock=lambda: T0
        )
        return handlers, facts, notifications

    async def test_recherche_inactive_n_emet_rien(
        self, parts: tuple[AutomationJobHandlers, FakeFacts, AsyncMock]
    ) -> None:
        handlers, facts, notifications = parts
        identifiant = uuid.uuid4()
        facts.searches[identifiant] = SavedSearchInfo("Ancienne", False)
        facts.recent_offers = 9

        await handlers.handle_recurring_search(
            _job("recurring_search", uuid.uuid4(), {"saved_search_id": str(identifiant)})
        )

        notifications.notify.assert_not_awaited()

    async def test_recherche_sans_nouvelle_offre_n_emet_rien(
        self, parts: tuple[AutomationJobHandlers, FakeFacts, AsyncMock]
    ) -> None:
        handlers, facts, notifications = parts
        identifiant = uuid.uuid4()
        facts.searches[identifiant] = SavedSearchInfo("Active", True)

        await handlers.handle_recurring_search(
            _job("recurring_search", uuid.uuid4(), {"saved_search_id": str(identifiant)})
        )

        notifications.notify.assert_not_awaited()

    async def test_recherche_inconnue_leve_une_erreur_explicite(
        self, parts: tuple[AutomationJobHandlers, FakeFacts, AsyncMock]
    ) -> None:
        handlers, _, _ = parts

        with pytest.raises(SavedSearchNotFoundError):
            await handlers.handle_recurring_search(
                _job("recurring_search", uuid.uuid4(), {"saved_search_id": str(uuid.uuid4())})
            )

    async def test_tache_sans_proprietaire_est_ignoree(
        self, parts: tuple[AutomationJobHandlers, FakeFacts, AsyncMock]
    ) -> None:
        handlers, facts, notifications = parts
        facts.ai_spent = Decimal("50")
        facts.recent_offers = 3

        for traiter, genre in (
            (handlers.handle_recurring_search, "recurring_search"),
            (handlers.handle_follow_up_check, "follow_up_check"),
            (handlers.handle_ai_budget_check, "ai_budget_check"),
            (handlers.handle_daily_digest, "daily_digest"),
        ):
            await traiter(_job(genre, None))

        notifications.notify.assert_not_awaited()

    async def test_depense_sous_le_seuil_n_alerte_pas(
        self, parts: tuple[AutomationJobHandlers, FakeFacts, AsyncMock]
    ) -> None:
        handlers, facts, notifications = parts
        facts.ai_spent = Decimal("0.9000")

        await handlers.handle_ai_budget_check(_job("ai_budget_check", uuid.uuid4()))

        notifications.notify.assert_not_awaited()

    async def test_alerte_budget_porte_la_devise_de_l_utilisateur(
        self, parts: tuple[AutomationJobHandlers, FakeFacts, AsyncMock]
    ) -> None:
        handlers, facts, notifications = parts
        facts.ai_spent = Decimal("3")
        facts.currency = "USD"

        await handlers.handle_ai_budget_check(_job("ai_budget_check", uuid.uuid4()))

        assert notifications.notify.await_args.kwargs["payload"]["currency"] == "USD"

    async def test_table_des_gestionnaires_couvre_tous_les_types_planifiables(
        self, parts: tuple[AutomationJobHandlers, FakeFacts, AsyncMock]
    ) -> None:
        handlers, _, _ = parts

        assert set(handlers.as_handler_mapping()) == {t.value for t in ScheduledTaskType}
