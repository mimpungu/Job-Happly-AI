"""Routes REST des offres et des recherches (`/api/v1`). Routes minces : validation → use case."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.types import ExceptionHandler

from app.core.api.dependencies import SessionDep as Session
from app.core.api.dependencies import get_owner_id
from app.core.api.errors import error_response
from app.modules.job_discovery.application.saved_searches import SearchService
from app.modules.job_discovery.domain.enums import OfferState
from app.modules.job_discovery.domain.saved_search import (
    DuplicateSavedSearchError,
    InvalidSavedSearchError,
    SavedSearch,
    SavedSearchNotFoundError,
    SearchRun,
)
from app.modules.job_discovery.domain.search import (
    OfferDetail,
    OfferFilter,
    OfferNotFoundError,
    OfferPage,
    OfferSummary,
    SuggestionField,
)
from app.modules.job_discovery.infrastructure.offer_queries import SqlOfferQueryRepository
from app.modules.job_discovery.infrastructure.saved_search_repository import (
    SqlSavedSearchRepository,
)
from app.modules.job_intelligence.infrastructure.composition import build_matching_service

router = APIRouter(prefix="/api/v1", tags=["job-discovery"])

Owner = Annotated[uuid.UUID, Depends(get_owner_id)]


class OfferPageResponse(BaseModel):
    items: list[OfferSummary]
    total: int
    page: int
    page_size: int
    page_count: int

    @classmethod
    def from_page(cls, page: OfferPage) -> OfferPageResponse:
        return cls(
            items=list(page.items),
            total=page.total,
            page=page.page,
            page_size=page.page_size,
            page_count=page.page_count,
        )


class OfferStateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # `null` retire l'état (l'offre redevient une offre ordinaire).
    state: OfferState | None


class SavedSearchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    filter: OfferFilter = Field(default_factory=OfferFilter)
    active: bool = True


class SavedSearchPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    filter: OfferFilter | None = None
    active: bool | None = None


class SearchRunResponse(BaseModel):
    run: SearchRun
    results: OfferPageResponse


@router.get("/offers", response_model=OfferPageResponse)
async def list_offers(
    session: Session, owner_id: Owner, offer_filter: Annotated[OfferFilter, Query()]
) -> OfferPageResponse:
    # Contexte de score : profil validé et pondérations courants (`None` sans profil validé).
    contexte = await build_matching_service(session).score_context(owner_id=owner_id)
    page = await SqlOfferQueryRepository(session).search(
        owner_id=owner_id, offer_filter=offer_filter, score_context=contexte
    )
    return OfferPageResponse.from_page(page)


@router.get("/offers/suggestions", response_model=list[str])
async def suggest_values(
    session: Session,
    owner_id: Owner,
    field: Annotated[SuggestionField, Query()],
    q: Annotated[str, Query(min_length=1, max_length=100)],
    limit: Annotated[int, Query(ge=1, le=15)] = 8,
) -> list[str]:
    """Suggestions pour un champ de recherche : valeurs existantes des offres actives."""
    return await SqlOfferQueryRepository(session).suggest(
        owner_id=owner_id, field=field, prefix=q.strip(), limit=limit
    )


@router.get("/offers/{offer_id}", response_model=OfferDetail)
async def get_offer(session: Session, owner_id: Owner, offer_id: uuid.UUID) -> OfferDetail:
    return await SqlOfferQueryRepository(session).get(owner_id=owner_id, offer_id=offer_id)


@router.put("/offers/{offer_id}/state", status_code=204)
async def set_offer_state(
    session: Session, owner_id: Owner, offer_id: uuid.UUID, body: OfferStateBody
) -> Response:
    await SqlOfferQueryRepository(session).set_state(
        owner_id=owner_id, offer_id=offer_id, state=body.state
    )
    return Response(status_code=204)


@router.get("/saved-searches", response_model=list[SavedSearch])
async def list_saved_searches(session: Session, owner_id: Owner) -> tuple[SavedSearch, ...]:
    return await SqlSavedSearchRepository(session).list(owner_id=owner_id)


@router.post("/saved-searches", response_model=SavedSearch, status_code=201)
async def create_saved_search(
    session: Session, owner_id: Owner, body: SavedSearchBody
) -> SavedSearch:
    return await SqlSavedSearchRepository(session).create(
        owner_id=owner_id, name=body.name, offer_filter=body.filter
    )


@router.patch("/saved-searches/{search_id}", response_model=SavedSearch)
async def update_saved_search(
    session: Session, owner_id: Owner, search_id: uuid.UUID, body: SavedSearchPatch
) -> SavedSearch:
    return await SqlSavedSearchRepository(session).update(
        owner_id=owner_id,
        search_id=search_id,
        name=body.name,
        offer_filter=body.filter,
        active=body.active,
    )


@router.delete("/saved-searches/{search_id}", status_code=204)
async def delete_saved_search(session: Session, owner_id: Owner, search_id: uuid.UUID) -> Response:
    await SqlSavedSearchRepository(session).delete(owner_id=owner_id, search_id=search_id)
    return Response(status_code=204)


@router.post("/saved-searches/{search_id}/run", response_model=SearchRunResponse)
async def run_saved_search(
    session: Session, owner_id: Owner, search_id: uuid.UUID
) -> SearchRunResponse:
    service = SearchService(SqlOfferQueryRepository(session), SqlSavedSearchRepository(session))
    contexte = await build_matching_service(session).score_context(owner_id=owner_id)
    page, execution = await service.rerun(
        owner_id=owner_id, saved_search_id=search_id, score_context=contexte
    )
    return SearchRunResponse(run=execution, results=OfferPageResponse.from_page(page))


@router.get("/search-runs", response_model=list[SearchRun])
async def search_history(
    session: Session, owner_id: Owner, limit: Annotated[int, Query(ge=1, le=200)] = 50
) -> tuple[SearchRun, ...]:
    return await SqlSavedSearchRepository(session).history(owner_id=owner_id, limit=limit)


_ERREURS: dict[type[Exception], tuple[int, str, str]] = {
    OfferNotFoundError: (404, "offer_not_found", "Offre introuvable."),
    SavedSearchNotFoundError: (404, "saved_search_not_found", "Recherche introuvable."),
    DuplicateSavedSearchError: (409, "saved_search_duplicate", "Ce nom de recherche existe déjà."),
    InvalidSavedSearchError: (422, "saved_search_invalid", "Nom de recherche invalide."),
}


def _gestionnaire(status: int, code: str, message: str) -> ExceptionHandler:
    async def _repondre(_: Request, __: Exception) -> JSONResponse:
        return error_response(status, code, message)

    return _repondre


def register_domain_errors(application: FastAPI) -> None:
    """Associe les erreurs métier à des réponses HTTP normalisées (messages fixes)."""
    for type_erreur, (status, code, message) in _ERREURS.items():
        application.add_exception_handler(type_erreur, _gestionnaire(status, code, message))
