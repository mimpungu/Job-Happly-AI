"""Routes REST des entreprises suivies et de la collecte d'offres (`/api/v1`)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.types import ExceptionHandler

from app.core.api.dependencies import SessionDep as Session
from app.core.api.dependencies import UnitOfWorkDep, get_owner_id
from app.core.api.errors import error_response
from app.modules.demo.infrastructure.composition import build_demo_service, ensure_demo_inactive
from app.modules.job_discovery.application.collection import (
    CollectionFilter,
    CollectionReport,
    CollectionService,
    NoEnabledCompanyError,
)
from app.modules.job_discovery.domain.enums import SearchRunStatus
from app.modules.job_discovery.infrastructure.ats.discovery import discover_boards
from app.modules.job_discovery.infrastructure.http import create_http_client
from app.modules.job_discovery.infrastructure.models import JobSourceModel, TargetCompanyModel
from app.modules.job_discovery.infrastructure.source_repository import SqlJobSourceRepository
from app.modules.job_discovery.infrastructure.target_company_repository import (
    SqlTargetCompanyRepository,
    TargetCompanyError,
    TargetCompanyNotFoundError,
)

router = APIRouter(prefix="/api/v1", tags=["companies"])

Owner = Annotated[uuid.UUID, Depends(get_owner_id)]


class DiscoverBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=100)


class DiscoveredBoardResponse(BaseModel):
    ats_kind: str
    token: str
    careers_url: str
    board_name: str | None
    offer_count: int


class CollectionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    it_only: bool = False
    city: str | None = Field(default=None, max_length=200)
    country_codes: list[str] = Field(default_factory=list, max_length=10)


class CompanyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    careers_url: str | None = Field(default=None, max_length=500)
    enabled: bool = False


class CompanyPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool


class CompanyResponse(BaseModel):
    id: uuid.UUID
    name: str
    careers_url: str | None
    ats_kind: str | None
    detection_status: str
    enabled: bool
    last_checked_at: datetime | None
    last_success_at: datetime | None
    last_error: str | None


class SourceOutcomeResponse(BaseModel):
    company_id: uuid.UUID | None
    company_name: str
    source_key: str
    succeeded: bool
    complete: bool
    fetched: int
    created: int
    merged: int
    changed: int
    unchanged: int
    rejected: int
    expired: int
    error_type: str | None


class CollectionResponse(BaseModel):
    started_at: datetime
    finished_at: datetime
    status: SearchRunStatus
    sources: list[SourceOutcomeResponse]

    @classmethod
    def from_report(cls, rapport: CollectionReport) -> CollectionResponse:
        return cls(
            started_at=rapport.started_at,
            finished_at=rapport.finished_at,
            status=rapport.status,
            sources=[
                SourceOutcomeResponse(
                    company_id=c.company_id,
                    company_name=c.company_name,
                    source_key=c.source_key,
                    succeeded=c.outcome.succeeded,
                    complete=c.outcome.complete,
                    fetched=c.outcome.fetched,
                    created=c.outcome.created,
                    merged=c.outcome.merged,
                    changed=c.outcome.changed,
                    unchanged=c.outcome.unchanged,
                    rejected=c.outcome.rejected,
                    expired=c.outcome.expired,
                    error_type=c.outcome.error_type,
                )
                for c in rapport.companies
            ],
        )


async def _vues(session: Session, owner_id: uuid.UUID) -> list[CompanyResponse]:
    """Entreprises suivies, avec l'état de leur dernière collecte (table des sources)."""
    entreprises = await SqlTargetCompanyRepository(session).list(owner_id)
    sources = await SqlJobSourceRepository(session).list_by_owner(owner_id)
    return [_vue(e, sources.get(_cle_source(e))) for e in entreprises]


def _cle_source(entreprise: TargetCompanyModel) -> str:
    return f"{entreprise.ats_kind}:{entreprise.ats_token}"


def _vue(entreprise: TargetCompanyModel, source: JobSourceModel | None) -> CompanyResponse:
    return CompanyResponse(
        id=entreprise.id,
        name=entreprise.name,
        careers_url=entreprise.careers_url,
        ats_kind=entreprise.ats_kind,
        detection_status=entreprise.detection_status,
        enabled=entreprise.enabled,
        last_checked_at=source.last_checked_at if source else None,
        last_success_at=source.last_success_at if source else None,
        last_error=source.last_error if source else None,
    )


@router.get("/target-companies", response_model=list[CompanyResponse])
async def list_companies(session: Session, owner_id: Owner) -> list[CompanyResponse]:
    return await _vues(session, owner_id)


@router.post("/target-companies/discover", response_model=list[DiscoveredBoardResponse])
async def discover_company(body: DiscoverBody) -> list[DiscoveredBoardResponse]:
    """Cherche le job board public d'une entreprise d'après son nom. Ne persiste rien."""
    async with create_http_client() as client:
        boards = await discover_boards(body.name, client)
    return [
        DiscoveredBoardResponse(
            ats_kind=b.ats_kind.value,
            token=b.token,
            careers_url=b.careers_url,
            board_name=b.board_name,
            offer_count=b.offer_count,
        )
        for b in boards
    ]


@router.post("/target-companies", response_model=CompanyResponse, status_code=201)
async def add_company(session: Session, owner_id: Owner, body: CompanyBody) -> CompanyResponse:
    await build_demo_service(session).ensure_inactive(owner_id)
    depot = SqlTargetCompanyRepository(session)
    entreprise = await depot.add(
        owner_id, name=body.name, careers_url=body.careers_url, now=datetime.now(UTC)
    )
    if body.enabled:
        await depot.set_enabled(entreprise, True)
    return _vue(entreprise, None)


@router.patch("/target-companies/{company_id}", response_model=CompanyResponse)
async def update_company(
    session: Session, owner_id: Owner, company_id: uuid.UUID, body: CompanyPatch
) -> CompanyResponse:
    depot = SqlTargetCompanyRepository(session)
    entreprise = await depot.get(owner_id, company_id)
    await depot.set_enabled(entreprise, body.enabled)
    return next(v for v in await _vues(session, owner_id) if v.id == company_id)


@router.post("/collection/run", response_model=CollectionResponse)
async def run_collection(
    uow: UnitOfWorkDep, owner_id: Owner, body: CollectionBody | None = None
) -> CollectionResponse:
    """Collecte, en parallèle, les offres de toutes les entreprises activées."""
    await ensure_demo_inactive(uow, owner_id)
    service = CollectionService(uow, create_http_client)
    corps = body or CollectionBody()
    garder = CollectionFilter(
        it_only=corps.it_only,
        city=(corps.city or "").strip() or None,
        country_codes=tuple(c.upper() for c in corps.country_codes),
    )
    return CollectionResponse.from_report(await service.run(owner_id=owner_id, keep=garder))


def _gestionnaire(status: int, code: str, message: str | None) -> ExceptionHandler:
    async def _repondre(_: Request, erreur: Exception) -> JSONResponse:
        # Les messages de TargetCompanyError sont rédigés par nos soins (jamais d'entrée brute).
        return error_response(status, code, message or str(erreur))

    return _repondre


def register_company_errors(application: FastAPI) -> None:
    application.add_exception_handler(
        TargetCompanyNotFoundError,
        _gestionnaire(404, "company_not_found", "Entreprise introuvable."),
    )
    application.add_exception_handler(
        TargetCompanyError, _gestionnaire(422, "company_invalid", None)
    )
    application.add_exception_handler(
        NoEnabledCompanyError,
        _gestionnaire(
            409,
            "no_company_enabled",
            "Aucune entreprise activée : ajoutez-en une avant de collecter.",
        ),
    )
