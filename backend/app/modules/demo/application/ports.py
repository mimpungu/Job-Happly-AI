from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.modules.demo.domain.catalogue import DemoOffer


@dataclass(frozen=True)
class DemoCounts:
    offers: int
    applications: int


@dataclass(frozen=True)
class DemoRemoval:
    offers: int
    applications: int
    documents: int
    file_keys: tuple[str, ...]


class DemoRepositoryPort(Protocol):
    async def demo_counts(self, owner_id: uuid.UUID) -> DemoCounts: ...

    async def real_counts(self, owner_id: uuid.UUID) -> DemoCounts: ...

    async def add_offers(
        self, owner_id: uuid.UUID, offers: tuple[DemoOffer, ...], *, now: datetime
    ) -> int: ...

    async def remove_all(self, owner_id: uuid.UUID) -> DemoRemoval: ...


class FileDeleterPort(Protocol):
    async def delete(self, key: str) -> None: ...
