"""Cas d'usage : collecter les offres des entreprises suivies et activées (TASK-008-11 à 008-14).

Choix de conception :
- seules les entreprises activées dont la source publique est reconnue sont interrogées ;
- les sources sont interrogées en parallèle, avec délai, nouvelles tentatives et débit limité ;
- une source en échec n'empêche jamais les autres : le bilan est détaillé source par source ;
- un refus d'accès (401/403) rend la source « non supportée » : elle n'est jamais contournée.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from app.core.database.session import UnitOfWork
from app.modules.job_discovery.application.ingestion import IngestionService, SourceOutcome
from app.modules.job_discovery.application.target_connectors import connector_for
from app.modules.job_discovery.domain.connector import (
    HealthState,
    HealthStatus,
    JobSourceConnector,
)
from app.modules.job_discovery.domain.criteria import SearchCriteria
from app.modules.job_discovery.domain.enums import SearchRunStatus
from app.modules.job_discovery.infrastructure.resilience import ResilientConnector
from app.modules.job_discovery.infrastructure.source_repository import SqlJobSourceRepository
from app.modules.job_discovery.infrastructure.target_company_repository import (
    SqlTargetCompanyRepository,
)

ClientFactory = Callable[[], AbstractAsyncContextManager[httpx.AsyncClient]]

# Erreurs qui signalent un refus du site : la source est écartée, jamais contournée.
_REFUS = frozenset({"AccessDeniedError", "AuthenticationFailedError"})


class NoEnabledCompanyError(Exception):
    """Aucune entreprise suivie n'est activée : il n'y a rien à collecter."""


@dataclass(frozen=True, slots=True)
class CompanyCollection:
    company_id: uuid.UUID
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
    company_id: uuid.UUID
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

    async def run(self, *, owner_id: uuid.UUID) -> CollectionReport:
        debut = self._clock()
        async with self._client_factory() as client:
            cibles = await self._preparer(owner_id, client)
            if not cibles:
                raise NoEnabledCompanyError
            rapport = await IngestionService(self._uow, clock=self._clock).ingest(
                owner_id=owner_id,
                connectors=[c.connector for c in cibles],
                source_ids={c.connector.key: c.source_id for c in cibles},
                criteria=SearchCriteria(whole_catalogue=True),
                # Un job board d'entreprise liste tout son catalogue : un parcours complet
                # permet de déclarer disparues les offres retirées.
                full_catalogue=True,
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
                if bilan.error_type in _REFUS and (e := existantes.get(r.company_id)):
                    await entreprises.mark_unsupported(e, "access_denied", maintenant)
