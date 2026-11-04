"""Routes du mode démonstration (TASK-002-10) : activation et désactivation toujours explicites."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.api.dependencies import SessionDep, get_owner_id
from app.core.api.errors import error_response
from app.modules.demo.application.service import DemoStatus
from app.modules.demo.domain.catalogue import CONFIRMATION_DEMO
from app.modules.demo.domain.exceptions import DemoModeActiveError, RealDataPresentError
from app.modules.demo.infrastructure.composition import build_demo_service

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])
Owner = Annotated[uuid.UUID, Depends(get_owner_id)]


class DemoStatusResponse(BaseModel):
    enabled: bool
    offers: int
    applications: int
    notice: str = CONFIRMATION_DEMO


def _reponse(s: DemoStatus) -> DemoStatusResponse:
    return DemoStatusResponse(enabled=s.enabled, offers=s.offers, applications=s.applications)


@router.get("", response_model=DemoStatusResponse)
async def status(session: SessionDep, owner_id: Owner) -> DemoStatusResponse:
    return _reponse(await build_demo_service(session).status(owner_id))


@router.post("/enable", response_model=DemoStatusResponse)
async def enable(session: SessionDep, owner_id: Owner) -> DemoStatusResponse:
    """Ajoute des offres **fictives** ; refusé s'il existe des données réelles (jamais mêlées)."""
    return _reponse(await build_demo_service(session).enable(owner_id))


@router.post("/disable", response_model=DemoStatusResponse)
async def disable(session: SessionDep, owner_id: Owner) -> DemoStatusResponse:
    """Retire les données fictives et ce qui en dérive ; le réel n'est pas touché."""
    return _reponse(await build_demo_service(session).disable(owner_id))


def register_demo_errors(application: FastAPI) -> None:
    async def _conflit(_: Request, erreur: Exception) -> JSONResponse:
        code = (
            "demo_unavailable" if isinstance(erreur, RealDataPresentError) else "demo_mode_active"
        )
        return error_response(409, code, str(erreur))

    application.add_exception_handler(RealDataPresentError, _conflit)
    application.add_exception_handler(DemoModeActiveError, _conflit)
