"""Routes de santé et de mesures (EPIC 018). `/health` reste le test de vivacité, sans base."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel

from app.core.api.dependencies import SessionDep
from app.core.config import Settings, get_settings
from app.modules.platform.domain.health import ComponentHealth, Status, overall_status
from app.modules.platform.infrastructure import health_checks as checks

router = APIRouter(prefix="/api/v1/health", tags=["platform"])
SettingsDep = Annotated[Settings, Depends(get_settings)]


class ComponentResponse(BaseModel):
    name: str
    status: Status
    detail: str | None
    data: dict[str, Any]


class HealthResponse(BaseModel):
    status: Status
    components: list[ComponentResponse]


def _response(components: list[ComponentHealth]) -> HealthResponse:
    return HealthResponse(
        status=overall_status(components),
        components=[
            ComponentResponse(name=c.name, status=c.status, detail=c.detail, data=c.data)
            for c in components
        ],
    )


@router.get("/ready", response_model=HealthResponse)
async def ready(session: SessionDep, settings: SettingsDep, response: Response) -> HealthResponse:
    """Prêt à servir : base et stockage. 503 sinon (utilisable par un orchestrateur)."""
    resultat = _response([await checks.check_database(session), checks.check_storage(settings)])
    if resultat.status is Status.DOWN:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return resultat


@router.get("/details", response_model=HealthResponse)
async def details(session: SessionDep, settings: SettingsDep) -> HealthResponse:
    """Tableau de santé complet : composants essentiels et facultatifs."""
    return _response(
        [
            await checks.check_database(session),
            checks.check_storage(settings),
            checks.check_latex(settings),
            checks.check_ai(settings),
            await checks.check_sources(session),
            await checks.check_tasks(session),
        ]
    )


@router.get("/metrics")
async def metrics(request: Request) -> dict[str, object]:
    """Durées et volumes par route depuis le démarrage (mémoire du processus)."""
    return request.app.state.metrics.snapshot()  # type: ignore[no-any-return]
