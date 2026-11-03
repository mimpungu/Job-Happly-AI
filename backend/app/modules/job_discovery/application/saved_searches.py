"""Cas d'usage : relancer une recherche sauvegardée et en garder la trace."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from app.modules.job_discovery.domain.saved_search import SavedSearchRepository, SearchRun
from app.modules.job_discovery.domain.search import OfferFilter, OfferPage, OfferQueryRepository


def _maintenant() -> datetime:
    return datetime.now(UTC)


class SearchService:
    def __init__(
        self,
        offers: OfferQueryRepository,
        saved: SavedSearchRepository,
        *,
        clock: Callable[[], datetime] = _maintenant,
    ) -> None:
        self._offers = offers
        self._saved = saved
        self._clock = clock

    async def run(
        self,
        *,
        owner_id: uuid.UUID,
        offer_filter: OfferFilter,
        saved_search_id: uuid.UUID | None = None,
    ) -> tuple[OfferPage, SearchRun]:
        """Exécute la recherche puis l'enregistre dans l'historique."""
        debut = self._clock()
        page = await self._offers.search(owner_id=owner_id, offer_filter=offer_filter)
        execution = await self._saved.record_run(
            owner_id=owner_id,
            saved_search_id=saved_search_id,
            offer_filter=offer_filter,
            result_count=page.total,
            started_at=debut,
            finished_at=self._clock(),
        )
        return page, execution

    async def rerun(
        self, *, owner_id: uuid.UUID, saved_search_id: uuid.UUID
    ) -> tuple[OfferPage, SearchRun]:
        """Relance les critères mémorisés, toujours depuis la première page."""
        recherche = await self._saved.get(owner_id=owner_id, search_id=saved_search_id)
        return await self.run(
            owner_id=owner_id,
            offer_filter=recherche.offer_filter.model_copy(update={"page": 1}),
            saved_search_id=saved_search_id,
        )
