"""Tests unitaires du service de résumé quotidien (DailyDigestService)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.modules.notifications.application.daily_digest_service import DailyDigestService
from app.modules.notifications.application.ports import DigestFacts
from app.modules.notifications.domain.enums import NotificationKind
from tests.unit.notifications.fakes import FakeFacts

T0 = datetime(2026, 11, 4, 8, 0, 0, tzinfo=UTC)


class TestDailyDigestService:
    @pytest.fixture
    def owner_id(self) -> uuid.UUID:
        return uuid.uuid4()

    @pytest.fixture
    def facts(self) -> FakeFacts:
        return FakeFacts(
            digest=DigestFacts(
                new_offers_count=5,
                sample_offers=(
                    {"title": "Lead Développeur Python", "company": "TechCorp", "id": "x"},
                ),
                follow_ups_due=2,
                active_applications=7,
                ai_spent_today=Decimal("0.0450"),
            )
        )

    @pytest.fixture
    def mock_notifications(self) -> AsyncMock:
        service = AsyncMock()
        service.notify = AsyncMock()
        return service

    async def test_generate_digest_consolide_et_notifie(
        self,
        facts: FakeFacts,
        mock_notifications: AsyncMock,
        owner_id: uuid.UUID,
    ) -> None:
        digest_service = DailyDigestService(
            facts=facts,
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
