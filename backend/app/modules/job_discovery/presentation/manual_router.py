"""Route d'ajout manuel d'une offre (`POST /api/v1/offers/manual`)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.core.api.dependencies import SessionDep as Session
from app.core.api.dependencies import get_owner_id
from app.core.api.errors import error_response
from app.core.domain.value_objects import EmploymentType, RemoteType
from app.modules.demo.infrastructure.composition import build_demo_service
from app.modules.job_discovery.application.manual_offers import (
    InvalidManualOfferError,
    ManualOfferInput,
    ManualOfferService,
)

router = APIRouter(prefix="/api/v1", tags=["job-discovery"])

Owner = Annotated[uuid.UUID, Depends(get_owner_id)]


class ManualOfferBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=2, max_length=300)
    description: str = Field(min_length=20, max_length=50_000)
    application_url: str = Field(min_length=10, max_length=2000)
    company_name: str | None = Field(default=None, max_length=300)
    location: str | None = Field(default=None, max_length=300)
    country_code: str | None = Field(default=None, pattern=r"^[A-Za-z]{2}$")
    employment_type: EmploymentType | None = None
    remote_type: RemoteType | None = None
    published_at: AwareDatetime | None = None


class ManualOfferResponse(BaseModel):
    offer_id: uuid.UUID
    created: bool
    merged: bool
    changed: bool
    already_known: bool
    """Vrai si l'offre existait déjà (même adresse ou même poste vu ailleurs)."""


@router.post("/offers/manual", response_model=ManualOfferResponse, status_code=201)
async def add_manual_offer(
    session: Session, owner_id: Owner, body: ManualOfferBody
) -> ManualOfferResponse:
    await build_demo_service(session).ensure_inactive(owner_id)
    resultat = await ManualOfferService().add(
        session,
        owner_id,
        ManualOfferInput(
            title=body.title,
            description=body.description,
            application_url=body.application_url,
            company_name=body.company_name,
            location=body.location,
            country_code=body.country_code.upper() if body.country_code else None,
            employment_type=body.employment_type,
            remote_type=body.remote_type,
            published_at=body.published_at,
        ),
    )
    return ManualOfferResponse(
        offer_id=resultat.offer_id,
        created=resultat.created,
        merged=resultat.merged,
        changed=resultat.changed,
        already_known=not resultat.created,
    )


def register_manual_errors(application: FastAPI) -> None:
    async def _refuser(_: Request, erreur: Exception) -> JSONResponse:
        # Message rédigé par nos soins dans le service (jamais la saisie brute).
        return error_response(422, "manual_offer_invalid", str(erreur))

    application.add_exception_handler(InvalidManualOfferError, _refuser)
