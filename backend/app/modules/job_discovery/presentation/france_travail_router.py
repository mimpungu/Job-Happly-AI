"""Routes de la source officielle France Travail (`/api/v1/france-travail`)."""

from __future__ import annotations

import uuid
from typing import Annotated, Self

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator
from starlette.types import ExceptionHandler

from app.core.api.dependencies import UnitOfWorkDep, get_owner_id
from app.core.api.errors import error_response
from app.core.config import Settings, get_settings
from app.modules.job_discovery.application.external_search import ExternalSearchService
from app.modules.job_discovery.domain.connector import NotConfiguredError
from app.modules.job_discovery.domain.criteria import SearchCriteria
from app.modules.job_discovery.infrastructure.france_travail import FranceTravailConnector
from app.modules.job_discovery.infrastructure.http import create_http_client

router = APIRouter(prefix="/api/v1/france-travail", tags=["france-travail"])

Owner = Annotated[uuid.UUID, Depends(get_owner_id)]
Config = Annotated[Settings, Depends(get_settings)]


class StatusResponse(BaseModel):
    configured: bool


class SearchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=200)
    company: str | None = Field(default=None, max_length=200)
    keywords: list[str] = Field(default_factory=list, max_length=10)
    city: str | None = Field(default=None, max_length=200)
    department: str | None = Field(default=None, pattern=r"^(\d{2}|2[AB]|97\d)$")
    max_pages: int = Field(default=3, ge=1, le=8)

    @model_validator(mode="after")
    def _au_moins_un_critere(self) -> Self:
        if not ((self.title or "").strip() or (self.company or "").strip() or self.keywords):
            raise ValueError("Précisez un intitulé, une entreprise ou un mot-clé.")
        return self


class SearchResponse(BaseModel):
    succeeded: bool
    complete: bool
    pages: int
    fetched: int
    created: int
    merged: int
    changed: int
    unchanged: int
    rejected: int
    error_type: str | None


def _configured(settings: Settings) -> bool:
    return (
        settings.france_travail_client_id is not None
        and settings.france_travail_client_secret is not None
    )


@router.get("/status", response_model=StatusResponse)
async def status(settings: Config) -> StatusResponse:
    return StatusResponse(configured=_configured(settings))


@router.post("/search", response_model=SearchResponse)
async def search(
    uow: UnitOfWorkDep, owner_id: Owner, settings: Config, body: SearchBody
) -> SearchResponse:
    """Interroge France Travail et enregistre les offres trouvées (jamais de candidature)."""
    if not _configured(settings):
        raise NotConfiguredError("Identifiants France Travail absents.")
    criteres = SearchCriteria(
        title=body.title,
        company=body.company,
        keywords=tuple(body.keywords),
        city=body.city,
        country_codes=("FR",),
    )
    async with create_http_client() as client:
        connecteur = FranceTravailConnector(
            client=client,
            client_id=settings.france_travail_client_id,
            client_secret=settings.france_travail_client_secret,
            department=body.department,
        )
        bilan = await ExternalSearchService(uow).run(
            owner_id=owner_id, connector=connecteur, criteria=criteres, max_pages=body.max_pages
        )
    return SearchResponse(
        succeeded=bilan.succeeded,
        complete=bilan.complete,
        pages=bilan.pages,
        fetched=bilan.fetched,
        created=bilan.created,
        merged=bilan.merged,
        changed=bilan.changed,
        unchanged=bilan.unchanged,
        rejected=bilan.rejected,
        error_type=bilan.error_type,
    )


def _gestionnaire(status_code: int, code: str, message: str) -> ExceptionHandler:
    async def _repondre(_: Request, __: Exception) -> JSONResponse:
        return error_response(status_code, code, message)

    return _repondre


def register_france_travail_errors(application: FastAPI) -> None:
    application.add_exception_handler(
        NotConfiguredError,
        _gestionnaire(
            409,
            "source_not_configured",
            "France Travail n'est pas configuré : renseignez les identifiants de l'API.",
        ),
    )
