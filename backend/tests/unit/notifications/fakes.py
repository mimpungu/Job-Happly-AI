"""Doublure en mémoire du port des faits d'automatisation (le métier ne touche pas la base)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from app.modules.notifications.application.ports import DigestFacts, DueFollowUp, SavedSearchInfo


class FakeFacts:
    def __init__(self, digest: DigestFacts | None = None) -> None:
        self.digest = digest or DigestFacts(0, (), 0, 0, Decimal("0"))
        self.searches: dict[uuid.UUID, SavedSearchInfo] = {}
        self.recent_offers = 0
        self.follow_ups: list[DueFollowUp] = []
        self.ai_spent = Decimal("0")
        self.currency = "EUR"

    async def digest_facts(self, owner_id: uuid.UUID, *, now: datetime) -> DigestFacts:
        return self.digest

    async def saved_search(
        self, owner_id: uuid.UUID, saved_search_id: uuid.UUID
    ) -> SavedSearchInfo | None:
        return self.searches.get(saved_search_id)

    async def offers_created_since(self, owner_id: uuid.UUID, since: datetime) -> int:
        return self.recent_offers

    async def due_follow_ups(self, owner_id: uuid.UUID, now: datetime) -> list[DueFollowUp]:
        return self.follow_ups

    async def ai_spent_since(self, owner_id: uuid.UUID, since: datetime) -> Decimal:
        return self.ai_spent

    async def ai_currency(self, owner_id: uuid.UUID) -> str:
        return self.currency
