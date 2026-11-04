"""Offre normalisée et contrat de persistance (le domaine ignore SQL)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol

from app.core.domain.value_objects import CountryCode, EmploymentType, RemoteType


@dataclass(frozen=True, slots=True)
class NormalizedOffer:
    """Offre commune à toutes les sources. Absence d'information = `None`, jamais 0 ni ''."""

    title: str
    description: str
    application_url: str
    content_hash: str
    company_name: str | None = None
    location: str | None = None
    country_code: CountryCode | None = None
    employment_type: EmploymentType | None = None
    remote_type: RemoteType | None = None
    salary_min: Decimal | None = None
    salary_max: Decimal | None = None
    salary_currency: str | None = None
    published_at: datetime | None = None
    expires_at: datetime | None = None
    canonical_url: str | None = None
    language: str | None = None


@dataclass(frozen=True, slots=True)
class UpsertResult:
    offer_id: uuid.UUID
    created: bool
    """L'offre n'existait pas encore."""
    changed: bool
    """Le contenu (empreinte) a changé depuis la dernière observation : analyses à invalider."""
    merged: bool = False
    """L'observation a été rattachée à une offre existante (même poste vu sur une autre source)."""


class JobOfferRepository(Protocol):
    async def upsert_observation(
        self,
        *,
        owner_id: uuid.UUID,
        source_id: uuid.UUID,
        external_id: str,
        offer: NormalizedOffer,
        raw_payload: dict[str, Any],
        observed_at: datetime,
    ) -> UpsertResult:
        """Enregistre une observation de façon idempotente (rejouable sans doublon)."""
        ...
