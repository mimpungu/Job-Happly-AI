"""Recherche multi-sources et état des sources de données (`/api/v1`)."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core.api.dependencies import SessionDep as Session
from app.core.api.dependencies import UnitOfWorkDep, get_owner_id
from app.core.config import Settings, get_settings
from app.modules.demo.infrastructure.composition import ensure_demo_inactive
from app.modules.job_discovery.application.collection import CollectionService
from app.modules.job_discovery.application.company_resolution import CompanyResolver
from app.modules.job_discovery.application.saved_searches import SearchService
from app.modules.job_discovery.application.source_search import (
    SourceSearchReport,
    SourceSearchService,
    coverage_of,
)
from app.modules.job_discovery.domain.enums import SearchRunStatus
from app.modules.job_discovery.domain.search import OfferFilter
from app.modules.job_discovery.infrastructure.france_travail import FranceTravailConnector
from app.modules.job_discovery.infrastructure.http import create_http_client
from app.modules.job_discovery.infrastructure.models import JobSourceModel
from app.modules.job_discovery.infrastructure.offer_queries import SqlOfferQueryRepository
from app.modules.job_discovery.infrastructure.saved_search_repository import (
    SqlSavedSearchRepository,
)
from app.modules.job_discovery.infrastructure.search_sources import (
    build_search_connectors,
    france_travail_configured,
)
from app.modules.job_discovery.infrastructure.source_repository import SqlJobSourceRepository
from app.modules.job_discovery.presentation.router import OfferPageResponse
from app.modules.job_intelligence.infrastructure.composition import build_matching_service

router = APIRouter(prefix="/api/v1", tags=["search"])

Owner = Annotated[uuid.UUID, Depends(get_owner_id)]
Config = Annotated[Settings, Depends(get_settings)]


class SourceQueryStatus(StrEnum):
    OK = "ok"
    FAILED = "failed"


class SourceSearchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filter: OfferFilter = Field(default_factory=OfferFilter)
    titles: list[Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]] = Field(
        default_factory=list, max_length=10
    )
    refresh: bool = True
    """`False` : lit uniquement la base locale, sans interroger de source."""


class QueriedSourceResponse(BaseModel):
    source_key: str
    source_name: str
    status: SourceQueryStatus
    complete: bool
    fetched: int
    created: int
    merged: int
    changed: int
    unchanged: int
    rejected: int
    error_type: str | None


class CoverageResponse(BaseModel):
    requested: list[str]
    declared: list[str]
    undeclared: list[str]
    sources_without_declared_countries: list[str]


class DiscoveredBoardView(BaseModel):
    ats_kind: str
    token: str
    careers_url: str
    board_name: str | None
    offer_count: int


class CompanySearchResponse(BaseModel):
    status: str
    """`tracked`, `followed`, `candidates`, `not_found` ou `disabled`."""
    query: str
    followed_name: str | None
    boards: list[DiscoveredBoardView]


class SourceSearchResponse(BaseModel):
    company_search: CompanySearchResponse | None
    """Présent quand la recherche porte sur une entreprise précise : ce qui a été retrouvé."""
    coverage: CoverageResponse
    """Couverture géographique des sources interrogées, par rapport aux pays demandés."""
    queried: bool
    """Au moins une source a été interrogée (sinon : résultats de la base locale seulement)."""
    status: SearchRunStatus | None
    sources: list[QueriedSourceResponse]
    results: OfferPageResponse

    @classmethod
    def build(
        cls, rapport: SourceSearchReport, page: OfferPageResponse, pays: tuple[str, ...]
    ) -> SourceSearchResponse:
        couverture = coverage_of(pays, rapport.sources)
        entreprise = rapport.company
        return cls(
            company_search=None
            if entreprise is None
            else CompanySearchResponse(
                status=entreprise.status.value,
                query=entreprise.query,
                followed_name=entreprise.followed_name,
                boards=[
                    DiscoveredBoardView(
                        ats_kind=b.ats_kind.value,
                        token=b.token,
                        careers_url=b.careers_url,
                        board_name=b.board_name,
                        offer_count=b.offer_count,
                    )
                    for b in entreprise.boards
                ],
            ),
            coverage=CoverageResponse(
                requested=list(couverture.requested),
                declared=list(couverture.declared),
                undeclared=list(couverture.undeclared),
                sources_without_declared_countries=list(
                    couverture.sources_without_declared_countries
                ),
            ),
            queried=bool(rapport.sources),
            status=rapport.status,
            sources=[
                QueriedSourceResponse(
                    source_key=s.source_key,
                    source_name=s.company_name,
                    status=(
                        SourceQueryStatus.OK if s.outcome.succeeded else SourceQueryStatus.FAILED
                    ),
                    complete=s.outcome.complete,
                    fetched=s.outcome.fetched,
                    created=s.outcome.created,
                    merged=s.outcome.merged,
                    changed=s.outcome.changed,
                    unchanged=s.outcome.unchanged,
                    rejected=s.outcome.rejected,
                    error_type=s.outcome.error_type,
                )
                for s in rapport.sources
            ],
            results=page,
        )


@router.post("/search", response_model=SourceSearchResponse)
async def search_sources(
    uow: UnitOfWorkDep, owner_id: Owner, settings: Config, body: SourceSearchBody
) -> SourceSearchResponse:
    """Interroge en parallèle les sources utiles, puis renvoie les offres agrégées."""
    rapport = SourceSearchReport(status=None, sources=())
    if body.refresh:
        await ensure_demo_inactive(uow, owner_id)
        collection = CollectionService(uow, create_http_client)
        rapport = await SourceSearchService(
            collection, CompanyResolver(uow, create_http_client)
        ).collect(
            owner_id=owner_id,
            offer_filter=body.filter,
            titles=tuple(body.titles),
            extra_factory=lambda client: build_search_connectors(settings, client),
        )
    async with uow.begin() as session:
        contexte = await build_matching_service(session).score_context(owner_id=owner_id)
        page, _ = await SearchService(
            SqlOfferQueryRepository(session), SqlSavedSearchRepository(session)
        ).run(owner_id=owner_id, offer_filter=body.filter, score_context=contexte)
    return SourceSearchResponse.build(
        rapport, OfferPageResponse.from_page(page), tuple(body.filter.country_codes)
    )


class DataSourceStatus(StrEnum):
    OK = "ok"
    ERROR = "error"
    UNSUPPORTED = "unsupported"
    NOT_CONFIGURED = "not_configured"
    NEVER_CHECKED = "never_checked"


class DataSourceResponse(BaseModel):
    key: str
    name: str
    kind: str
    countries: list[str]
    coverage_declared: bool
    """Faux : la source ne déclare aucun pays, sa couverture n'est pas affirmée."""
    enabled: bool
    requires_configuration: bool
    configured: bool
    status: DataSourceStatus
    last_checked_at: datetime | None
    last_success_at: datetime | None
    last_error: str | None
    offer_count: int


def _statut(ligne: JobSourceModel | None, *, configuree: bool) -> DataSourceStatus:
    if not configuree:
        return DataSourceStatus.NOT_CONFIGURED
    if ligne is None or ligne.last_checked_at is None:
        return DataSourceStatus.NEVER_CHECKED
    if ligne.last_error is None:
        return DataSourceStatus.OK
    if ligne.last_error.startswith("unsupported"):
        return DataSourceStatus.UNSUPPORTED
    return DataSourceStatus.ERROR


@router.get("/sources", response_model=list[DataSourceResponse])
async def list_sources(
    session: Session,
    owner_id: Owner,
    settings: Config,
    country: Annotated[str | None, Query(pattern=r"^[A-Za-z]{2}$")] = None,
) -> list[DataSourceResponse]:
    """Sources de données : état, dernier accès, dernière erreur et nombre d'offres.

    `country` ne garde que les sources qui déclarent ce pays **ou** dont la couverture n'est pas
    déclarée (signalée par `coverage_declared: false`, jamais présentée comme couvrante).
    """
    depot = SqlJobSourceRepository(session)
    lignes = await depot.list_by_owner(owner_id)
    totaux = await depot.offer_counts(owner_id)
    vues: list[DataSourceResponse] = []
    for ligne in sorted(lignes.values(), key=lambda s: s.name.lower()):
        configuree = ligne.key != FranceTravailConnector.key or france_travail_configured(settings)
        vues.append(
            DataSourceResponse(
                key=ligne.key,
                name=ligne.name,
                kind=ligne.kind,
                countries=list(ligne.countries),
                coverage_declared=bool(ligne.countries),
                enabled=ligne.enabled,
                requires_configuration=ligne.requires_api_key,
                configured=configuree,
                status=_statut(ligne, configuree=configuree),
                last_checked_at=ligne.last_checked_at,
                last_success_at=ligne.last_success_at,
                last_error=ligne.last_error,
                offer_count=totaux.get(ligne.id, 0),
            )
        )
    if FranceTravailConnector.key not in lignes:
        configuree = france_travail_configured(settings)
        # Source officielle connue mais jamais utilisée : affichée explicitement, pas masquée.
        vues.append(
            DataSourceResponse(
                key=FranceTravailConnector.key,
                name=FranceTravailConnector.name,
                kind=FranceTravailConnector.kind.value,
                countries=["FR"],
                coverage_declared=True,
                enabled=False,
                requires_configuration=True,
                configured=configuree,
                status=_statut(None, configuree=configuree),
                last_checked_at=None,
                last_success_at=None,
                last_error=None,
                offer_count=0,
            )
        )
    if country:
        voulu = country.upper()
        vues = [v for v in vues if not v.coverage_declared or voulu in v.countries]
    return vues
