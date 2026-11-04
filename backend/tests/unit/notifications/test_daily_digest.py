"""Tests unitaires du service de résumé quotidien (DailyDigestService)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.notifications.application.daily_digest_service import DailyDigestService
from app.modules.notifications.domain.enums import NotificationKind

T0 = datetime(2026, 11, 4, 8, 0, 0, tzinfo=UTC)


class TestDailyDigestService:
    @pytest.fixture
    def owner_id(self) -> uuid.UUID:
        return uuid.uuid4()

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        session = AsyncMock()
        # scalar renverra successivement :
        # 1. count nouvelles offres (ex: 5)
        # 2. count relances dues (ex: 2)
        # 3. count candidatures actives (ex: 7)
        # 4. sum ai cost (ex: Decimal("0.0450"))
        session.scalar.side_effect = [
            5,
            2,
            7,
            Decimal("0.0450"),
        ]

        # execute renverra pour les 3 offres récentes :
        row1 = MagicMock()
        row1.title = "Lead Développeur Python"
        row1.company_name = "TechCorp"
        row1.id = uuid.uuid4()

        result_mock = MagicMock()
        result_mock.all.return_value = [row1]
        session.execute.return_value = result_mock

        return session

    @pytest.fixture
    def mock_notifications(self) -> AsyncMock:
        service = AsyncMock()
        service.notify = AsyncMock()
        return service

    async def test_generate_digest_consolide_et_notifie(
        self,
        mock_session: AsyncMock,
        mock_notifications: AsyncMock,
        owner_id: uuid.UUID,
    ) -> None:
        digest_service = DailyDigestService(
            session=mock_session,
            notification_service=mock_notifications,
            clock=lambda: T0,
        )

        summary = await digest_service.generate_digest(owner_id=owner_id)

        assert summary.date == "2026-11-04"
        assert summary.new_offers_count == 5
        assert summary.follow_ups_due_count == 2
        assert summary.active_applications_count == 7
        assert summary.ai_spent_today == Decimal("0.0450")
        assert len(summary.sample_offers) == 1
        assert summary.sample_offers[0]["title"] == "Lead Développeur Python"

        # Vérification de l'émission de notification
        mock_notifications.notify.assert_awaited_once()
        call_kwargs: dict[str, Any] = mock_notifications.notify.await_args.kwargs
        assert call_kwargs["owner_id"] == owner_id
        assert call_kwargs["kind"] == NotificationKind.DAILY_DIGEST
        assert "5 nouvelle(s) offre(s)" in call_kwargs["body"]
        assert "2 relance(s)" in call_kwargs["body"]
        assert call_kwargs["payload"]["new_offers_count"] == 5
