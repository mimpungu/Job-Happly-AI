"""Point d'entrée de l'API."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.api.errors import register_error_handlers
from app.core.config import get_settings
from app.core.database.session import create_engine, create_session_factory
from app.core.observability.logging import configure_logging
from app.core.observability.metrics import MetricsRegistry
from app.core.observability.middleware import ObservabilityMiddleware
from app.core.observability.rate_limit import SlidingWindowLimiter
from app.modules.ai_management.presentation.router import register_ai_errors
from app.modules.ai_management.presentation.router import router as ai_router
from app.modules.application_management.presentation.errors import register_application_errors
from app.modules.application_management.presentation.router import (
    applications_router,
    dashboard_router,
)
from app.modules.candidate_profile.presentation.router import (
    register_document_errors,
)
from app.modules.candidate_profile.presentation.router import router as profile_router
from app.modules.demo.presentation.router import register_demo_errors
from app.modules.demo.presentation.router import router as demo_router
from app.modules.document_generation.presentation.cover_letter_router import (
    router as cover_letter_router,
)
from app.modules.document_generation.presentation.errors import register_generation_errors
from app.modules.document_generation.presentation.router import router as resume_router
from app.modules.interview_preparation.presentation.errors import register_interview_errors
from app.modules.interview_preparation.presentation.router import router as interview_router
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
from app.modules.job_discovery.presentation.search_router import router as search_router
from app.modules.job_intelligence.presentation.analysis_router import router as analysis_router
from app.modules.job_intelligence.presentation.router import (
    register_matching_errors,
)
from app.modules.job_intelligence.presentation.router import router as matching_router
from app.modules.localization.presentation.router import (
    register_localization_errors,
)
from app.modules.localization.presentation.router import router as localization_router
from app.modules.notifications.application.runtime import AutomationRuntime
from app.modules.notifications.presentation.router import (
    notifications_router,
    scheduler_router,
)
from app.modules.platform.presentation.router import router as health_router
from app.modules.privacy.presentation.errors import register_privacy_errors
from app.modules.privacy.presentation.router import router as privacy_router


@asynccontextmanager
async def _lifespan(application: FastAPI) -> AsyncGenerator[None]:
    settings = get_settings()
    if settings.database_url is None:
        # Sans base, seule la santé répond ; les autres routes renvoient 503.
        yield
        return
    moteur = create_engine(settings.database_url)
    application.state.session_factory = create_session_factory(moteur)
    moteur_taches = (
        AutomationRuntime(
            application.state.session_factory, tick_seconds=settings.worker_tick_seconds
        )
        if settings.worker_enabled
        else None
    )
    if moteur_taches is not None:
        await moteur_taches.start()
    try:
        yield
    finally:
        if moteur_taches is not None:
            await moteur_taches.stop()
        await moteur.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    application = FastAPI(title="Happly AI API", version="0.5.0rc1", lifespan=_lifespan)
    application.state.metrics = MetricsRegistry()
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID", "Retry-After"],
    )
    # Ajouté en dernier = le plus externe : il voit aussi les refus de CORS et les erreurs.
    application.add_middleware(
        ObservabilityMiddleware,
        metrics=application.state.metrics,
        limiter=SlidingWindowLimiter(settings.rate_limit_per_minute),
        expensive_limiter=SlidingWindowLimiter(settings.rate_limit_expensive_per_minute),
        max_body_bytes=settings.max_request_body_mb * 1024 * 1024,
    )
    register_error_handlers(application)
    register_domain_errors(application)
    register_document_errors(application)
    register_generation_errors(application)
    register_application_errors(application)
    register_matching_errors(application)
    register_company_errors(application)
    register_france_travail_errors(application)
    register_manual_errors(application)
    register_ai_errors(application)
    register_interview_errors(application)
    register_privacy_errors(application)
    register_demo_errors(application)
    register_localization_errors(application)

    @application.get("/api/v1/health", tags=["platform"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    application.include_router(health_router)
    application.include_router(manual_router)
    application.include_router(router)
    application.include_router(companies_router)
    application.include_router(france_travail_router)
    application.include_router(search_router)
    application.include_router(profile_router)
    application.include_router(matching_router)
    application.include_router(analysis_router)
    application.include_router(ai_router)
    application.include_router(resume_router)
    application.include_router(cover_letter_router)
    application.include_router(applications_router)
    application.include_router(dashboard_router)
    application.include_router(notifications_router)
    application.include_router(scheduler_router)
    application.include_router(interview_router)
    application.include_router(privacy_router)
    application.include_router(demo_router)
    application.include_router(localization_router)
    return application


app = create_app()
