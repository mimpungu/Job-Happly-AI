"""Service d'ingestion : interroge les sources, normalise, déduplique et enregistre.

Garanties :
- une source en échec n'empêche jamais les autres (résultats partiels explicites) ;
- une offre invalide est écartée et comptée, sans interrompre la page ;
- chaque page est enregistrée dans sa propre transaction : en cas d'interruption, le travail déjà
  fait est conservé et la relance ne crée aucun doublon (idempotence) ;
- les offres ne sont marquées « disparues » qu'après un parcours complet du catalogue de la
  source, jamais après une simple recherche filtrée.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy.exc import DBAPIError

from app.core.database.session import UnitOfWork
from app.core.domain.value_objects import DomainValueError
from app.modules.job_discovery.domain.connector import (
    ConnectorError,
    ConnectorOffer,
    JobSourceConnector,
)
from app.modules.job_discovery.domain.criteria import SearchCriteria
from app.modules.job_discovery.domain.enums import SearchRunStatus
from app.modules.job_discovery.domain.normalization import normalize_offer
from app.modules.job_discovery.infrastructure.repositories import SqlJobOfferRepository

logger = logging.getLogger("happly.ingestion")

DEFAULT_MAX_PAGES = 20


@dataclass(slots=True)
class SourceOutcome:
    source_key: str
    succeeded: bool = False
    complete: bool = False
    """Toutes les pages ont été parcourues (le curseur est arrivé à son terme)."""
    pages: int = 0
    fetched: int = 0
    created: int = 0
    merged: int = 0
    changed: int = 0
    unchanged: int = 0
    rejected: int = 0
    expired: int = 0
    error_type: str | None = None


@dataclass(frozen=True, slots=True)
class IngestionReport:
    started_at: datetime
    finished_at: datetime
    outcomes: tuple[SourceOutcome, ...] = field(default_factory=tuple)

    @property
    def status(self) -> SearchRunStatus:
        if not self.outcomes:
            return SearchRunStatus.FAILED
        reussies = sum(1 for o in self.outcomes if o.succeeded)
        if reussies == len(self.outcomes):
            return SearchRunStatus.SUCCEEDED
        return SearchRunStatus.PARTIAL if reussies else SearchRunStatus.FAILED

    @property
    def total_fetched(self) -> int:
        return sum(o.fetched for o in self.outcomes)


class IngestionService:
    def __init__(
        self,
        uow: UnitOfWork,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._uow = uow
        self._clock = clock

    async def ingest(
        self,
        *,
        owner_id: uuid.UUID,
        connectors: Sequence[JobSourceConnector],
        source_ids: Mapping[str, uuid.UUID],
        criteria: SearchCriteria,
        max_pages: int = DEFAULT_MAX_PAGES,
        full_catalogue: bool = False,
        concurrency: int = 3,
    ) -> IngestionReport:
        """Ingère les offres de chaque connecteur, en parallèle (limité par `concurrency`).

        `full_catalogue=True` n'est à utiliser que si la recherche énumère **tout** le catalogue de
        la source : seul ce cas autorise à déclarer disparues les offres non revues.
        """
        if max_pages < 1 or concurrency < 1:
            raise ValueError("max_pages et concurrency doivent être strictement positifs.")
        debut = self._clock()
        limite = asyncio.Semaphore(concurrency)

        async def une_source(connecteur: JobSourceConnector) -> SourceOutcome:
            async with limite:
                return await self._ingerer_source(
                    owner_id=owner_id,
                    connector=connecteur,
                    source_id=source_ids[connecteur.key],
                    criteria=criteria,
                    max_pages=max_pages,
                    full_catalogue=full_catalogue,
                    started_at=debut,
                )

        resultats = await asyncio.gather(*(une_source(c) for c in connectors))
        return IngestionReport(
            started_at=debut, finished_at=self._clock(), outcomes=tuple(resultats)
        )

    async def _ingerer_source(
        self,
        *,
        owner_id: uuid.UUID,
        connector: JobSourceConnector,
        source_id: uuid.UUID,
        criteria: SearchCriteria,
        max_pages: int,
        full_catalogue: bool,
        started_at: datetime,
    ) -> SourceOutcome:
        bilan = SourceOutcome(source_key=connector.key)
        courant = criteria
        try:
            while bilan.pages < max_pages:
                page = await connector.search(courant)
                bilan.pages += 1
                bilan.fetched += len(page.offers)
                await self._enregistrer_page(owner_id, source_id, page.offers, bilan)
                if page.next_cursor is None:
                    bilan.complete = True
                    break
                courant = criteria.model_copy(update={"cursor": page.next_cursor})
            bilan.succeeded = True
        except ConnectorError as erreur:
            # Les offres déjà enregistrées (pages précédentes) sont conservées.
            bilan.error_type = type(erreur).__name__
            logger.warning(
                "Source en échec pendant l'ingestion",
                extra={
                    "source": connector.key,
                    "error_type": bilan.error_type,
                    "pages": bilan.pages,
                },
            )
            return bilan

        if full_catalogue and bilan.complete:
            await self._expirer(owner_id, source_id, started_at, bilan)
        return bilan

    async def _enregistrer_page(
        self,
        owner_id: uuid.UUID,
        source_id: uuid.UUID,
        offres: Sequence[ConnectorOffer],
        bilan: SourceOutcome,
    ) -> None:
        async with self._uow.begin() as session:
            depot = SqlJobOfferRepository(session)
            for brute in offres:
                try:
                    # Point de sauvegarde par offre : une offre invalide n'annule pas la page.
                    async with session.begin_nested():
                        resultat = await depot.upsert_observation(
                            owner_id=owner_id,
                            source_id=source_id,
                            external_id=brute.external_id,
                            offer=normalize_offer(brute.offer),
                            raw_payload=brute.raw_payload,
                            observed_at=self._clock(),
                        )
                except (DomainValueError, DBAPIError, ValueError) as erreur:
                    bilan.rejected += 1
                    logger.warning(
                        "Offre rejetée",
                        extra={
                            "error_type": type(erreur).__name__,
                            "external_id": brute.external_id,
                        },
                    )
                    continue
                if resultat.created:
                    bilan.created += 1
                elif resultat.merged:
                    bilan.merged += 1
                elif resultat.changed:
                    bilan.changed += 1
                else:
                    bilan.unchanged += 1

    async def _expirer(
        self, owner_id: uuid.UUID, source_id: uuid.UUID, started_at: datetime, bilan: SourceOutcome
    ) -> None:
        async with self._uow.begin() as session:
            depot = SqlJobOfferRepository(session)
            maintenant = self._clock()
            await depot.mark_unseen_observations_gone(
                owner_id=owner_id, source_id=source_id, seen_since=started_at, now=maintenant
            )
            bilan.expired = await depot.expire_offers(owner_id=owner_id, now=maintenant)
