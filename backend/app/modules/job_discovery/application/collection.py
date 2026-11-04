"""Cas d'usage : collecter les offres des entreprises suivies et activées (TASK-008-11 à 008-14).

Choix de conception :
- seules les entreprises activées dont la source publique est reconnue sont interrogées ;
- les sources sont interrogées en parallèle, avec délai, nouvelles tentatives et débit limité ;
- une source en échec n'empêche jamais les autres : le bilan est détaillé source par source ;
- un refus d'accès (401/403) rend la source « non supportée » : elle n'est jamais contournée.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, replace
from datetime import UTC, datetime

import httpx

from app.core.database.session import UnitOfWork
from app.modules.job_discovery.application.ingestion import IngestionService, SourceOutcome
from app.modules.job_discovery.application.target_connectors import connector_for
from app.modules.job_discovery.domain.connector import (
    ConnectorCapabilities,
    ConnectorOffer,
    HealthState,
    HealthStatus,
    JobSourceConnector,
    SearchPage,
)
from app.modules.job_discovery.domain.criteria import SearchCriteria
from app.modules.job_discovery.domain.enums import SearchRunStatus, SourceKind
from app.modules.job_discovery.domain.it_offers import is_it_offer
from app.modules.job_discovery.domain.multilingual import expand_term
from app.modules.job_discovery.domain.offers import NormalizedOffer
from app.modules.job_discovery.domain.text import normalize_text
from app.modules.job_discovery.infrastructure.resilience import ResilientConnector
from app.modules.job_discovery.infrastructure.source_repository import SqlJobSourceRepository
from app.modules.job_discovery.infrastructure.target_company_repository import (
    SqlTargetCompanyRepository,
)

ClientFactory = Callable[[], AbstractAsyncContextManager[httpx.AsyncClient]]
ExtraFactory = Callable[[httpx.AsyncClient], Sequence[JobSourceConnector]]

# Erreurs qui signalent un refus du site : la source est écartée, jamais contournée.
_REFUS = frozenset({"AccessDeniedError", "AuthenticationFailedError"})


@dataclass(frozen=True, slots=True)
class CollectionFilter:
    """Ce qu'on garde à la collecte. Vide = tout le catalogue de chaque entreprise."""

    it_only: bool = False
    city: str | None = None
    country_codes: tuple[str, ...] = ()
    titles: tuple[str, ...] = ()
    """Intitulés visés : l'offre est gardée si son titre en contient un (TASK-006-21)."""
    keywords: tuple[str, ...] = ()
    """Mots-clés exigés : chacun doit figurer dans le titre ou la description."""
    multilingual: bool = False
    """Accepte aussi les équivalents français/anglais des intitulés et mots-clés."""

    @property
    def is_empty(self) -> bool:
        return not (self.it_only or self.city or self.country_codes or self.titles or self.keywords)

    def _variantes(self, terme: str) -> tuple[str, ...]:
        return expand_term(terme) if self.multilingual else (terme,)

    def keeps(self, offre: NormalizedOffer) -> bool:
        if self.it_only and not is_it_offer(offre.title):
            return False
        if self.titles:
            titre = normalize_text(offre.title)
            if not any(normalize_text(v) in titre for t in self.titles for v in self._variantes(t)):
                return False
        if self.keywords:
            contenu = normalize_text(f"{offre.title} {offre.description}")
            if not all(
                any(normalize_text(v) in contenu for v in self._variantes(m)) for m in self.keywords
            ):
                return False
        if self.city and not (
            offre.location and normalize_text(self.city) in normalize_text(offre.location)
        ):
            return False
        pays = offre.country_code
        return not (
            self.country_codes and pays is not None and pays.value not in self.country_codes
        )


class _FilteredConnector:
    """Écarte, avant enregistrement, les offres hors filtre ; le reste passe tel quel."""

    def __init__(self, inner: JobSourceConnector, keep: CollectionFilter) -> None:
        self._inner = inner
        self._keep = keep

    @property
    def key(self) -> str:
        return self._inner.key

    @property
    def name(self) -> str:
        return self._inner.name

    @property
    def kind(self) -> SourceKind:
        return self._inner.kind

    def get_capabilities(self) -> ConnectorCapabilities:
        return self._inner.get_capabilities()

    async def search(self, criteria: SearchCriteria) -> SearchPage:
        page = await self._inner.search(criteria)
        return replace(page, offers=tuple(o for o in page.offers if self._keep.keeps(o.offer)))

    async def get_details(self, external_id: str) -> ConnectorOffer | None:
        return await self._inner.get_details(external_id)

    async def health_check(self) -> HealthStatus:
        return await self._inner.health_check()


class NoEnabledCompanyError(Exception):
    """Aucune entreprise suivie n'est activée : il n'y a rien à collecter."""


@dataclass(frozen=True, slots=True)
class CompanyCollection:
    company_id: uuid.UUID | None
    """`None` pour une source qui n'est pas une entreprise suivie (API officielle)."""
    company_name: str
    source_key: str
    outcome: SourceOutcome


@dataclass(frozen=True, slots=True)
class CollectionReport:
    started_at: datetime
    finished_at: datetime
    status: SearchRunStatus
    companies: tuple[CompanyCollection, ...]


@dataclass(frozen=True, slots=True)
class _Cible:
    company_id: uuid.UUID | None
    company_name: str
    connector: JobSourceConnector
    source_id: uuid.UUID


class CollectionService:
    def __init__(
        self,
        uow: UnitOfWork,
        client_factory: ClientFactory,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        resilient: Callable[[JobSourceConnector], JobSourceConnector] | None = None,
    ) -> None:
        self._uow = uow
        self._client_factory = client_factory
        self._clock = clock
        self._resilient = resilient or ResilientConnector

    async def run(
        self,
        *,
        owner_id: uuid.UUID,
        keep: CollectionFilter | None = None,
        extra_factory: ExtraFactory | None = None,
        criteria: SearchCriteria | None = None,
    ) -> CollectionReport:
        """Collecte les entreprises activées, plus d'éventuelles sources de recherche.

        `extra_factory` construit, avec le client HTTP de la collecte, des sources de recherche
        (API officielles) interrogées avec `criteria`, en parallèle des entreprises ; leur bilan
        est distinct, jamais mélangé.
        """
        keep = keep or CollectionFilter()
        debut = self._clock()
        async with self._client_factory() as client:
            cibles = await self._preparer(owner_id, client)
            recherche = criteria or SearchCriteria(whole_catalogue=True)
            # Seules les sources dont la couverture correspond à la recherche sont interrogées.
            compatibles = [
                c
                for c in (extra_factory(client) if extra_factory else ())
                if c.get_capabilities().covers(recherche)
            ]
            cibles += await self._preparer_extras(owner_id, compatibles)
            if not cibles:
                raise NoEnabledCompanyError
            # Seule une énumération complète du catalogue autorise à déclarer des offres disparues.
            catalogue_complet = keep.is_empty and criteria is None
            rapport = await IngestionService(self._uow, clock=self._clock).ingest(
                owner_id=owner_id,
                connectors=[
                    c.connector if keep.is_empty else _FilteredConnector(c.connector, keep)
                    for c in cibles
                ],
                source_ids={c.connector.key: c.source_id for c in cibles},
                criteria=recherche,
                # Retirer des offres « disparues » n'est sûr que si tout le catalogue a été vu :
                # avec un filtre, une offre absente peut simplement être hors filtre.
                full_catalogue=catalogue_complet,
            )
        par_cle = {o.source_key: o for o in rapport.outcomes}
        resultats = tuple(
            CompanyCollection(
                c.company_id, c.company_name, c.connector.key, par_cle[c.connector.key]
            )
            for c in cibles
        )
        await self._enregistrer_sante(owner_id, resultats)
        return CollectionReport(
            started_at=debut,
            finished_at=self._clock(),
            status=rapport.status,
            companies=resultats,
        )

    async def _preparer(self, owner_id: uuid.UUID, client: httpx.AsyncClient) -> list[_Cible]:
        cibles: list[_Cible] = []
        async with self._uow.begin() as session:
            sources = SqlJobSourceRepository(session)
            entreprises = await SqlTargetCompanyRepository(session).list(owner_id)
            for entreprise in entreprises:
                if not entreprise.enabled:
                    continue
                connecteur = connector_for(entreprise, client)
                if connecteur is None:
                    continue
                protege = self._resilient(connecteur)
                source = await sources.sync_from_connector(owner_id, protege)
                await sources.set_enabled(owner_id, protege.key, True)
                cibles.append(_Cible(entreprise.id, entreprise.name, protege, source.id))
        return cibles

    async def _preparer_extras(
        self, owner_id: uuid.UUID, connecteurs: Sequence[JobSourceConnector]
    ) -> list[_Cible]:
        cibles: list[_Cible] = []
        if not connecteurs:
            return cibles
        async with self._uow.begin() as session:
            sources = SqlJobSourceRepository(session)
            for connecteur in connecteurs:
                protege = self._resilient(connecteur)
                source = await sources.sync_from_connector(owner_id, protege)
                await sources.set_enabled(owner_id, protege.key, True)
                cibles.append(_Cible(None, protege.name, protege, source.id))
        return cibles

    async def _enregistrer_sante(
        self, owner_id: uuid.UUID, resultats: tuple[CompanyCollection, ...]
    ) -> None:
        maintenant = self._clock()
        async with self._uow.begin() as session:
            sources = SqlJobSourceRepository(session)
            entreprises = SqlTargetCompanyRepository(session)
            existantes = {e.id: e for e in await entreprises.list(owner_id)}
            for r in resultats:
                bilan = r.outcome
                if bilan.succeeded:
                    statut = HealthStatus(HealthState.OK, maintenant)
                else:
                    etat = (
                        HealthState.UNSUPPORTED
                        if bilan.error_type in _REFUS
                        else HealthState.UNAVAILABLE
                    )
                    statut = HealthStatus(etat, maintenant, bilan.error_type)
                await sources.record_health(owner_id, r.source_key, statut)
                if (
                    bilan.error_type in _REFUS
                    and r.company_id is not None
                    and (e := existantes.get(r.company_id))
                ):
                    await entreprises.mark_unsupported(e, "access_denied", maintenant)
