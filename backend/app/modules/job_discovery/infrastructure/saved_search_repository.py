"""Persistance des recherches sauvegardées et de l'historique d'exécution."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.job_discovery.domain.enums import SearchRunStatus
from app.modules.job_discovery.domain.saved_search import (
    DuplicateSavedSearchError,
    SavedSearch,
    SavedSearchNotFoundError,
    SearchRun,
    clean_name,
)
from app.modules.job_discovery.domain.search import OfferFilter
from app.modules.job_discovery.infrastructure.models import SavedSearchModel, SearchRunModel


def _serialiser(offer_filter: OfferFilter) -> dict[str, Any]:
    # La page courante n'est pas un critère : elle n'est jamais mémorisée.
    return offer_filter.model_dump(mode="json", exclude={"page"})


def _deserialiser(donnees: dict[str, Any]) -> OfferFilter:
    return OfferFilter.model_validate(donnees)


def _vers_recherche(modele: SavedSearchModel) -> SavedSearch:
    return SavedSearch(
        id=modele.id,
        name=modele.name,
        offer_filter=_deserialiser(modele.criteria),
        active=modele.active,
        created_at=modele.created_at,
        updated_at=modele.updated_at,
    )


def _vers_execution(modele: SearchRunModel) -> SearchRun:
    return SearchRun(
        id=modele.id,
        saved_search_id=modele.saved_search_id,
        offer_filter=_deserialiser(modele.criteria),
        status=SearchRunStatus(modele.status),
        started_at=modele.started_at,
        finished_at=modele.finished_at,
        result_count=modele.result_count,
    )


class SqlSavedSearchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self, *, owner_id: uuid.UUID, name: str, offer_filter: OfferFilter
    ) -> SavedSearch:
        modele = SavedSearchModel(
            owner_id=owner_id, name=clean_name(name), criteria=_serialiser(offer_filter)
        )
        async with self._signaler_doublon():
            self._session.add(modele)
        await self._session.refresh(modele)
        return _vers_recherche(modele)

    async def update(
        self,
        *,
        owner_id: uuid.UUID,
        search_id: uuid.UUID,
        name: str | None = None,
        offer_filter: OfferFilter | None = None,
        active: bool | None = None,
    ) -> SavedSearch:
        modele = await self._charger(owner_id, search_id)
        nom = clean_name(name) if name is not None else None
        async with self._signaler_doublon():
            if nom is not None:
                modele.name = nom
            if offer_filter is not None:
                modele.criteria = _serialiser(offer_filter)
            if active is not None:
                modele.active = active
        await self._session.refresh(modele)
        return _vers_recherche(modele)

    async def get(self, *, owner_id: uuid.UUID, search_id: uuid.UUID) -> SavedSearch:
        return _vers_recherche(await self._charger(owner_id, search_id))

    async def list(self, *, owner_id: uuid.UUID) -> tuple[SavedSearch, ...]:
        lignes = await self._session.scalars(
            select(SavedSearchModel)
            .where(SavedSearchModel.owner_id == owner_id)
            .order_by(func.lower(SavedSearchModel.name))
        )
        return tuple(_vers_recherche(ligne) for ligne in lignes)

    async def delete(self, *, owner_id: uuid.UUID, search_id: uuid.UUID) -> None:
        # L'historique est conservé : `saved_search_id` passe à NULL (ON DELETE SET NULL).
        await self._session.delete(await self._charger(owner_id, search_id))
        await self._session.flush()

    async def record_run(
        self,
        *,
        owner_id: uuid.UUID,
        saved_search_id: uuid.UUID | None,
        offer_filter: OfferFilter,
        result_count: int,
        started_at: datetime,
        finished_at: datetime,
    ) -> SearchRun:
        if saved_search_id is not None:
            await self._charger(owner_id, saved_search_id)
        modele = SearchRunModel(
            owner_id=owner_id,
            saved_search_id=saved_search_id,
            criteria=_serialiser(offer_filter),
            status=SearchRunStatus.SUCCEEDED.value,
            started_at=started_at,
            finished_at=finished_at,
            result_count=result_count,
        )
        self._session.add(modele)
        await self._session.flush()
        await self._session.refresh(modele)
        return _vers_execution(modele)

    async def history(self, *, owner_id: uuid.UUID, limit: int = 50) -> tuple[SearchRun, ...]:
        lignes = await self._session.scalars(
            select(SearchRunModel)
            .where(SearchRunModel.owner_id == owner_id)
            .order_by(SearchRunModel.started_at.desc(), SearchRunModel.id.asc())
            .limit(limit)
        )
        return tuple(_vers_execution(ligne) for ligne in lignes)

    async def _charger(self, owner_id: uuid.UUID, search_id: uuid.UUID) -> SavedSearchModel:
        modele = await self._session.scalar(
            select(SavedSearchModel).where(
                SavedSearchModel.id == search_id, SavedSearchModel.owner_id == owner_id
            )
        )
        if modele is None:
            raise SavedSearchNotFoundError(str(search_id))
        return modele

    @asynccontextmanager
    async def _signaler_doublon(self) -> AsyncIterator[None]:
        """Écrit dans un savepoint : un nom en double est refusé sans casser la transaction.

        Le savepoint est ouvert *avant* les modifications, car l'ouvrir force déjà un flush.
        """
        try:
            async with self._session.begin_nested():
                yield
                await self._session.flush()
        except IntegrityError as erreur:
            if "uq_saved_searches_owner_id_name_lower" in str(erreur.orig):
                raise DuplicateSavedSearchError("Une recherche porte déjà ce nom.") from erreur
            raise
