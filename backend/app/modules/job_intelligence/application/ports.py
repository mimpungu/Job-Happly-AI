"""Ports du scoring : lectures dans les autres modules (CandidateFactsReader, JobOfferReader,
voir MODULE_CONTRACTS) et persistance des scores et des pondérations."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol

from app.modules.job_intelligence.domain.matching.models import OfferFacts, ProfileFacts


class NoValidatedProfileError(RuntimeError):
    """Aucun profil validé : le score ne se calcule que sur des faits confirmés."""


@dataclass(frozen=True, slots=True)
class ProfileSnapshot:
    profile_id: uuid.UUID
    version: int
    facts: ProfileFacts


@dataclass(frozen=True, slots=True)
class ScoreRecord:
    offer_id: uuid.UUID
    score: Decimal
    breakdown: dict[str, Any]
    weights_version: str


class CandidateFactsReader(Protocol):
    async def validated_snapshot(self, *, owner_id: uuid.UUID) -> ProfileSnapshot | None:
        """Faits de la dernière version **validée** du CV maître, ou `None`."""
        ...


class JobOfferReader(Protocol):
    async def get(self, *, owner_id: uuid.UUID, offer_id: uuid.UUID) -> OfferFacts:
        """Faits d'une offre ; lève `OfferNotFoundError` si elle est introuvable."""
        ...

    async def active_batch(
        self, *, owner_id: uuid.UUID, after: uuid.UUID | None, limit: int
    ) -> list[tuple[uuid.UUID, OfferFacts]]:
        """Offres actives par identifiants croissants (pagination par curseur, mémoire bornée)."""
        ...


class MatchStore(Protocol):
    async def get_weights(self, *, owner_id: uuid.UUID) -> dict[str, Any]: ...

    async def set_weights(
        self, *, owner_id: uuid.UUID, weights: dict[str, Any], now: datetime
    ) -> None: ...

    async def clear_weights(self, *, owner_id: uuid.UUID) -> None: ...

    async def save_scores(
        self,
        *,
        owner_id: uuid.UUID,
        profile_id: uuid.UUID,
        records: list[ScoreRecord],
        now: datetime,
    ) -> None: ...

    async def prune_scores(
        self, *, owner_id: uuid.UUID, profile_id: uuid.UUID, weights_version: str
    ) -> int:
        """Supprime les scores d'une autre version de profil ou de poids (obsolètes)."""
        ...
