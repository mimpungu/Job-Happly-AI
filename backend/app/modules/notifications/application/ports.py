"""Port de lecture des faits d'automatisation : le métier ne touche jamais la base (EPIC 004)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol


@dataclass(frozen=True)
class DigestFacts:
    new_offers_count: int
    sample_offers: tuple[dict[str, Any], ...]
    follow_ups_due: int
    active_applications: int
    ai_spent_today: Decimal


@dataclass(frozen=True)
class SavedSearchInfo:
    name: str
    active: bool


@dataclass(frozen=True)
class DueFollowUp:
    application_id: uuid.UUID
    offer_id: uuid.UUID
    title: str
    company: str


class AutomationFactsPort(Protocol):
    async def digest_facts(self, owner_id: uuid.UUID, *, now: datetime) -> DigestFacts: ...

    async def saved_search(
        self, owner_id: uuid.UUID, saved_search_id: uuid.UUID
    ) -> SavedSearchInfo | None: ...

    async def offers_created_since(self, owner_id: uuid.UUID, since: datetime) -> int: ...

    async def due_follow_ups(self, owner_id: uuid.UUID, now: datetime) -> list[DueFollowUp]: ...

    async def ai_spent_since(self, owner_id: uuid.UUID, since: datetime) -> Decimal: ...

    async def ai_currency(self, owner_id: uuid.UUID) -> str: ...
