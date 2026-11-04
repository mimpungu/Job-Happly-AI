"""Tests unitaires des gestionnaires de tâches de fond et de l'orchestrateur."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.notifications.application.orchestrator import (
    AutomationJobHandlers,
    list_job_history,
)
from app.modules.notifications.domain.enums import NotificationKind
from app.modules.platform.infrastructure.job_queue import ReservedJob
from app.modules.platform.infrastructure.models import JobModel

T0 = datetime(2026, 11, 4, 14, 0, 0, tzinfo=UTC)


class TestAutomationJobHandlers:
    @pytest.fixture
    def owner_id(self) -> uuid.UUID:
        return uuid.uuid4()

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        return AsyncMock()

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
        mock_session: AsyncMock,
        mock_notifications: AsyncMock,
        mock_queue: AsyncMock,
    ) -> AutomationJobHandlers:
        return AutomationJobHandlers(
            session=mock_session,
            notification_service=mock_notifications,
            job_queue=mock_queue,
            clock=lambda: T0,
        )

    async def test_handle_recurring_search_emet_notification(
        self,
        handlers: AutomationJobHandlers,
        mock_session: AsyncMock,
        mock_notifications: AsyncMock,
        owner_id: uuid.UUID,
    ) -> None:
        saved_search_id = uuid.uuid4()
        saved_search_mock = MagicMock()
        saved_search_mock.active = True
        saved_search_mock.name = "Offres Python Paris"

        mock_session.scalar.side_effect = [
            saved_search_mock,  # select SavedSearchModel
            4,  # count offres récentes
        ]

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
        mock_session: AsyncMock,
        mock_notifications: AsyncMock,
        owner_id: uuid.UUID,
    ) -> None:
        app_mock = MagicMock()
        app_mock.id = uuid.uuid4()
        app_mock.offer_id = uuid.uuid4()

        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [app_mock]
        mock_session.scalars.return_value = scalars_mock

        offre_mock = MagicMock()
        offre_mock.title = "Software Engineer"
        offre_mock.company_name = "Acme Corp"
        mock_session.scalar.return_value = offre_mock

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
        mock_session: AsyncMock,
        mock_notifications: AsyncMock,
        owner_id: uuid.UUID,
    ) -> None:
        settings_mock = MagicMock()
        settings_mock.currency = "EUR"

        # scalar renvoie settings puis somme dépense (ex: 2.5000 EUR > 1.0000)
        mock_session.scalar.side_effect = [
            settings_mock,
            Decimal("2.5000"),
        ]

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


class TestListJobHistory:
    async def test_list_job_history_formate_correctement(self) -> None:
        session = AsyncMock()
        session.scalar.return_value = 1

        job = JobModel(
            kind="recurring_search",
            idempotency_key="cle-test",
            status="succeeded",
            attempts=1,
            max_attempts=3,
            run_at=T0,
            created_at=T0,
        )
        job.id = uuid.uuid4()
        job.owner_id = uuid.uuid4()

        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [job]
        session.scalars.return_value = scalars_mock

        items, total = await list_job_history(session, limit=10, offset=0)
        assert total == 1
        assert len(items) == 1
        assert items[0]["kind"] == "recurring_search"
        assert items[0]["status"] == "succeeded"
