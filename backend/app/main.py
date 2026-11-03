"""Point d'entrée de l'API."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.api.errors import register_error_handlers
from app.core.config import get_settings
from app.core.database.session import create_engine, create_session_factory
from app.modules.candidate_profile.presentation.router import (
    register_document_errors,
)
from app.modules.candidate_profile.presentation.router import router as profile_router
from app.modules.job_discovery.presentation.companies_router import (
    register_company_errors,
)
from app.modules.job_discovery.presentation.companies_router import router as companies_router
from app.modules.job_discovery.presentation.france_travail_router import (
    register_france_travail_errors,
)
from app.modules.job_discovery.presentation.france_travail_router import (
    router as france_travail_router,
)
from app.modules.job_discovery.presentation.manual_router import register_manual_errors
from app.modules.job_discovery.presentation.manual_router import router as manual_router
from app.modules.job_discovery.presentation.router import register_domain_errors, router
from app.modules.job_intelligence.presentation.router import (
    register_matching_errors,
)
from app.modules.job_intelligence.presentation.router import router as matching_router


@asynccontextmanager
async def _lifespan(application: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    if settings.database_url is None:
        # Sans base, seule la santé répond ; les autres routes renvoient 503.
        yield
        return
    moteur = create_engine(settings.database_url)
    application.state.session_factory = create_session_factory(moteur)
    try:
        yield
    finally:
        await moteur.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title="Happly AI API", version="0.1.0", lifespan=_lifespan)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type"],
    )
    register_error_handlers(application)
    register_domain_errors(application)
    register_document_errors(application)
    register_matching_errors(application)
    register_company_errors(application)
    register_france_travail_errors(application)
    register_manual_errors(application)

    @application.get("/api/v1/health", tags=["platform"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    application.include_router(manual_router)
    application.include_router(router)
    application.include_router(companies_router)
    application.include_router(france_travail_router)
    application.include_router(profile_router)
    application.include_router(matching_router)
    return application


app = create_app()
