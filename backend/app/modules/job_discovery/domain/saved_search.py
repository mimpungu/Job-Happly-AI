"""Recherches sauvegardées et historique d'exécution."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.modules.job_discovery.domain.enums import SearchRunStatus
from app.modules.job_discovery.domain.search import OfferFilter

MAX_NAME_LENGTH = 200


class InvalidSavedSearchError(ValueError):
    """Nom vide ou trop long."""


class DuplicateSavedSearchError(ValueError):
    """Une recherche porte déjà ce nom (comparaison insensible à la casse)."""


class SavedSearchNotFoundError(LookupError):
    """La recherche n'existe pas pour ce propriétaire."""


def clean_name(name: str) -> str:
    nettoye = " ".join(name.split())
    if not nettoye:
        raise InvalidSavedSearchError("Le nom de la recherche est obligatoire.")
    if len(nettoye) > MAX_NAME_LENGTH:
        raise InvalidSavedSearchError(f"Le nom dépasse {MAX_NAME_LENGTH} caractères.")
    return nettoye


@dataclass(frozen=True, slots=True)
class SavedSearch:
    id: uuid.UUID
    name: str
    # Filtres sans pagination : relancer une recherche repart toujours de la première page.
    offer_filter: OfferFilter
    active: bool
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class SearchRun:
    id: uuid.UUID
    saved_search_id: uuid.UUID | None
    offer_filter: OfferFilter
    status: SearchRunStatus
    started_at: datetime
    finished_at: datetime | None
    result_count: int | None


class SavedSearchRepository(Protocol):
    async def create(
        self, *, owner_id: uuid.UUID, name: str, offer_filter: OfferFilter
    ) -> SavedSearch: ...

    async def update(
        self,
        *,
        owner_id: uuid.UUID,
        search_id: uuid.UUID,
        name: str | None = None,
        offer_filter: OfferFilter | None = None,
        active: bool | None = None,
    ) -> SavedSearch: ...

    async def get(self, *, owner_id: uuid.UUID, search_id: uuid.UUID) -> SavedSearch: ...

    async def list(self, *, owner_id: uuid.UUID) -> tuple[SavedSearch, ...]: ...

    async def delete(self, *, owner_id: uuid.UUID, search_id: uuid.UUID) -> None: ...

    async def record_run(
        self,
        *,
        owner_id: uuid.UUID,
        saved_search_id: uuid.UUID | None,
        offer_filter: OfferFilter,
        result_count: int,
        started_at: datetime,
        finished_at: datetime,
    ) -> SearchRun: ...

    async def history(self, *, owner_id: uuid.UUID, limit: int = 50) -> tuple[SearchRun, ...]: ...
