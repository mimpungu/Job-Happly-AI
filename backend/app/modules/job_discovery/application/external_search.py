"""Cas d'usage : interroger une source de recherche (API officielle) et enregistrer les offres.

Contrairement à la collecte d'un job board d'entreprise, la source ne liste pas un catalogue
borné : on ne déclare jamais d'offre « disparue » à l'issue d'une recherche.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from app.core.database.session import UnitOfWork
from app.modules.job_discovery.application.ingestion import IngestionService, SourceOutcome
from app.modules.job_discovery.domain.connector import JobSourceConnector
from app.modules.job_discovery.domain.criteria import SearchCriteria
from app.modules.job_discovery.infrastructure.resilience import ResilientConnector
from app.modules.job_discovery.infrastructure.source_repository import SqlJobSourceRepository

MAX_PAGES = 8


class ExternalSearchService:
    def __init__(
        self,
        uow: UnitOfWork,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        resilient: Callable[[JobSourceConnector], JobSourceConnector] | None = None,
    ) -> None:
        self._uow = uow
        self._clock = clock
        self._resilient = resilient or ResilientConnector

    async def run(
        self,
        *,
        owner_id: uuid.UUID,
        connector: JobSourceConnector,
        criteria: SearchCriteria,
        max_pages: int = 3,
    ) -> SourceOutcome:
        if not 1 <= max_pages <= MAX_PAGES:
            raise ValueError(f"max_pages doit être compris entre 1 et {MAX_PAGES}.")
        protege = self._resilient(connector)
        async with self._uow.begin() as session:
            sources = SqlJobSourceRepository(session)
            source = await sources.sync_from_connector(owner_id, protege)
            await sources.set_enabled(owner_id, protege.key, True)
            source_id = source.id
        rapport = await IngestionService(self._uow, clock=self._clock).ingest(
            owner_id=owner_id,
            connectors=[protege],
            source_ids={protege.key: source_id},
            criteria=criteria,
            max_pages=max_pages,
            full_catalogue=False,
        )
        return rapport.outcomes[0]
