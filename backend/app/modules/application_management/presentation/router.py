"""Routes du suivi de candidatures et du tableau de bord (EPIC 014).

Routes minces : validation → service → réponse. Les erreurs métier sont traduites par
`presentation/errors.py`. Rien ici n'envoie quoi que ce soit à un employeur : l'application
ouvre le lien de l'annonce, l'utilisateur candidate, puis confirme.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.api.dependencies import SessionDep, get_owner_id
from app.modules.application_management.domain.entities import (
    ApplicationAggregate,
    DocumentVersionInfo,
    MonthlyTrend,
    OfferSummary,
)
from app.modules.application_management.domain.enums import ApplicationStatus
from app.modules.application_management.domain.ports import ApplicationFilter
from app.modules.application_management.domain.rules import (
    allowed_status_targets,
    can_confirm_submission,
)
from app.modules.application_management.infrastructure.composition import (
    build_application_tracking_service,
    build_dashboard_service,
)
from app.modules.application_management.presentation.schemas import (
    AddContactRequest,
    AddInterviewRequest,
    AddNoteRequest,
    AIBudgetResponse,
    ApplicationDetailResponse,
    ApplicationDossierResponse,
    ApplicationListResponse,
    ApplicationResponse,
    ApplicationStatsResponse,
    AssociatedDocumentResponse,
    AttachDocumentsRequest,
    ChangeStatusRequest,
    ConfirmSubmissionRequest,
    ContactResponse,
    CreateApplicationRequest,
    DashboardMetricsResponse,
    FunnelResponse,
    InterviewEventResponse,
    KanbanColumnResponse,
    KanbanViewResponse,
    MonthlyTrendResponse,
    OfferSummaryResponse,
    OpenUrlResponse,
    RecentActivityResponse,
    RecentSearchResponse,
    ScheduleFollowUpRequest,
    TimelineEventResponse,
    TopMatchResponse,
)

applications_router = APIRouter(prefix="/api/v1/applications", tags=["application-tracking"])
dashboard_router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])

Owner = Annotated[uuid.UUID, Depends(get_owner_id)]


def _offer(offre: OfferSummary | None) -> OfferSummaryResponse | None:
    return OfferSummaryResponse(**offre.__dict__) if offre else None


def _trend(tendance: MonthlyTrend) -> MonthlyTrendResponse:
    return MonthlyTrendResponse(
        current=tendance.current, previous=tendance.previous, percent=tendance.percent
    )


def _application(app: ApplicationAggregate) -> ApplicationResponse:
    return ApplicationResponse(
        id=app.id,
        offer_id=app.offer_id,
        offer=_offer(app.offer),
        status=app.status,
        created_at=app.created_at,
        updated_at=app.updated_at,
        applied_at=app.applied_at,
        follow_up_at=app.follow_up_at,
        response_received_at=app.response_received_at,
        cv_version_id=app.cv_version_id,
        letter_version_id=app.letter_version_id,
    )


def _detail(
    app: ApplicationAggregate, documents: list[DocumentVersionInfo]
) -> ApplicationDetailResponse:
    courants = {app.cv_version_id, app.letter_version_id} - {None}
    return ApplicationDetailResponse(
        **_application(app).model_dump(),
        contacts=[ContactResponse(**c.__dict__) for c in app.contacts],
        events=[TimelineEventResponse(**e.__dict__) for e in app.events],
        documents=[
            AssociatedDocumentResponse(
                document_version_id=d.version_id,
                document_id=d.document_id,
                kind=d.kind,
                title=d.title,
                version=d.version,
                quality_passed=d.quality_passed,
                quality_score=d.quality_score,
                is_current=d.version_id in courants,
            )
            for d in documents
        ],
        allowed_transitions=allowed_status_targets(app.status),
        can_confirm_submission=can_confirm_submission(app),
    )


# ---------------------------------------------------------------------------------------------
# Candidatures
# ---------------------------------------------------------------------------------------------


@applications_router.post(
    "", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED
)
async def create_application(
    body: CreateApplicationRequest, session: SessionDep, owner_id: Owner
) -> ApplicationResponse:
    """Crée la candidature d'une offre (TASK-014-01, 02)."""
    app = await build_application_tracking_service(session).create_application(
        owner_id=owner_id, offer_id=body.offer_id, initial_status=body.initial_status
    )
    return _application(app)


@applications_router.get("", response_model=ApplicationListResponse)
async def list_applications(
    session: SessionDep,
    owner_id: Owner,
    status_filter: Annotated[ApplicationStatus | None, Query(alias="status")] = None,
    company: Annotated[str | None, Query(max_length=200)] = None,
    title: Annotated[str | None, Query(max_length=200)] = None,
    follow_up_due: Annotated[bool, Query()] = False,
    has_follow_up: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ApplicationListResponse:
    """Vue tableau filtrée et paginée côté base (TASK-014-11, 13)."""
    items, total = await build_application_tracking_service(session).list_applications(
        owner_id=owner_id,
        criteria=ApplicationFilter(
            status=status_filter,
            company_query=company,
            title_query=title,
            follow_up_due=follow_up_due,
            has_follow_up=has_follow_up,
        ),
        limit=limit,
        offset=offset,
    )
    return ApplicationListResponse(
        items=[_application(a) for a in items], total=total, limit=limit, offset=offset
    )


@applications_router.get("/kanban", response_model=KanbanViewResponse)
async def get_kanban_view(
    session: SessionDep,
    owner_id: Owner,
    per_column_limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> KanbanViewResponse:
    """Vue Kanban : total réel par colonne et cartes les plus récentes (TASK-014-12)."""
    colonnes = await build_application_tracking_service(session).get_kanban_view(
        owner_id=owner_id, per_column_limit=per_column_limit
    )
    return KanbanViewResponse(
        columns=[
            KanbanColumnResponse(
                status=statut,
                count=colonne.count,
                items=[_application(a) for a in colonne.items],
                has_more=colonne.count > len(colonne.items),
            )
            for statut, colonne in colonnes.items()
        ]
    )


@applications_router.get("/stats", response_model=ApplicationStatsResponse)
async def get_application_stats(session: SessionDep, owner_id: Owner) -> ApplicationStatsResponse:
    """Statistiques strictement fondées sur les données réelles (TASK-014-15, 22)."""
    stats = await build_application_tracking_service(session).get_stats(owner_id=owner_id)
    return ApplicationStatsResponse(**stats.__dict__)


@applications_router.get("/{application_id}", response_model=ApplicationDetailResponse)
async def get_application_detail(
    application_id: uuid.UUID, session: SessionDep, owner_id: Owner
) -> ApplicationDetailResponse:
    """Fiche d'une candidature : contacts, historique, documents (TASK-014-14)."""
    service = build_application_tracking_service(session)
    app = await service.get_application(owner_id=owner_id, application_id=application_id)
    return _detail(app, await service.describe_documents(app))


@applications_router.patch("/{application_id}/status", response_model=ApplicationDetailResponse)
async def change_application_status(
    application_id: uuid.UUID, body: ChangeStatusRequest, session: SessionDep, owner_id: Owner
) -> ApplicationDetailResponse:
    """Change le statut selon la machine à états (TASK-014-03, 06)."""
    service = build_application_tracking_service(session)
    app = await service.change_status(
        owner_id=owner_id,
        application_id=application_id,
        target_status=body.target_status,
        reason=body.reason,
    )
    return _detail(app, await service.describe_documents(app))


@applications_router.post(
    "/{application_id}/confirm-submission", response_model=ApplicationDetailResponse
)
async def confirm_manual_submission(
    application_id: uuid.UUID, body: ConfirmSubmissionRequest, session: SessionDep, owner_id: Owner
) -> ApplicationDetailResponse:
    """Enregistre que l'utilisateur a envoyé sa candidature lui-même (TASK-014-04, 20)."""
    service = build_application_tracking_service(session)
    app = await service.confirm_manual_submission(
        owner_id=owner_id,
        application_id=application_id,
        notes=body.notes,
        applied_at=body.applied_at,
    )
    return _detail(app, await service.describe_documents(app))


@applications_router.post(
    "/{application_id}/notes",
    response_model=TimelineEventResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_application_note(
    application_id: uuid.UUID, body: AddNoteRequest, session: SessionDep, owner_id: Owner
) -> TimelineEventResponse:
    """Ajoute une note à l'historique (TASK-014-07)."""
    event = await build_application_tracking_service(session).add_note(
        owner_id=owner_id, application_id=application_id, note_body=body.body
    )
    return TimelineEventResponse(**event.__dict__)


@applications_router.post(
    "/{application_id}/interviews",
    response_model=TimelineEventResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_interview_event(
    application_id: uuid.UUID, body: AddInterviewRequest, session: SessionDep, owner_id: Owner
) -> TimelineEventResponse:
    """Ajoute un entretien ou un échange à l'historique (TASK-014-08)."""
    event = await build_application_tracking_service(session).add_interview_event(
        owner_id=owner_id,
        application_id=application_id,
        description=body.description,
        interview_time=body.interview_time,
    )
    return TimelineEventResponse(**event.__dict__)


@applications_router.patch("/{application_id}/follow-up", response_model=ApplicationDetailResponse)
async def schedule_follow_up(
    application_id: uuid.UUID, body: ScheduleFollowUpRequest, session: SessionDep, owner_id: Owner
) -> ApplicationDetailResponse:
    """Planifie ou annule la relance (TASK-014-10)."""
    service = build_application_tracking_service(session)
    app = await service.schedule_follow_up(
        owner_id=owner_id,
        application_id=application_id,
        follow_up_at=body.follow_up_at,
        notes=body.notes,
    )
    return _detail(app, await service.describe_documents(app))


@applications_router.put("/{application_id}/documents", response_model=ApplicationDetailResponse)
async def attach_documents(
    application_id: uuid.UUID, body: AttachDocumentsRequest, session: SessionDep, owner_id: Owner
) -> ApplicationDetailResponse:
    """Associe les versions exactes de CV et de lettre (TASK-014-09)."""
    service = build_application_tracking_service(session)
    app = await service.attach_documents(
        owner_id=owner_id,
        application_id=application_id,
        cv_version_id=body.cv_version_id,
        letter_version_id=body.letter_version_id,
    )
    return _detail(app, await service.describe_documents(app))


@applications_router.post(
    "/{application_id}/contacts",
    response_model=ContactResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_contact(
    application_id: uuid.UUID, body: AddContactRequest, session: SessionDep, owner_id: Owner
) -> ContactResponse:
    """Enregistre le recruteur ou un contact (TASK-014-05)."""
    contact = await build_application_tracking_service(session).add_contact(
        owner_id=owner_id,
        application_id=application_id,
        name=body.name,
        email=body.email,
        phone=body.phone,
        role=body.role,
    )
    return ContactResponse(**contact.__dict__)


@applications_router.get("/{application_id}/dossier", response_model=ApplicationDossierResponse)
async def get_application_dossier(
    application_id: uuid.UUID, session: SessionDep, owner_id: Owner
) -> ApplicationDossierResponse:
    """Dossier de candidature et contrôle de ses pièces (TASK-014-16, 17, 18)."""
    dossier = await build_application_tracking_service(session).prepare_dossier(
        owner_id=owner_id, application_id=application_id
    )
    return ApplicationDossierResponse(
        **{
            **dossier.__dict__,
            "missing_elements": list(dossier.missing_elements),
            "warnings": list(dossier.warnings),
        }
    )


@applications_router.get("/{application_id}/open-url", response_model=OpenUrlResponse)
async def get_application_action_url(
    application_id: uuid.UUID, session: SessionDep, owner_id: Owner
) -> OpenUrlResponse:
    """Lien vérifié de l'annonce, que l'utilisateur ouvre lui-même (TASK-014-19)."""
    url = await build_application_tracking_service(session).get_application_url_action(
        owner_id=owner_id, application_id=application_id
    )
    return OpenUrlResponse(application_url=url)


# ---------------------------------------------------------------------------------------------
# Tableau de bord
# ---------------------------------------------------------------------------------------------


@dashboard_router.get("", response_model=DashboardMetricsResponse)
async def get_dashboard_metrics(session: SessionDep, owner_id: Owner) -> DashboardMetricsResponse:
    """Indicateurs réels ; `None` quand la donnée n'existe pas (TASK-014-21, 22)."""
    m = await build_dashboard_service(session).get_dashboard(owner_id=owner_id)
    return DashboardMetricsResponse(
        display_name=m.display_name,
        total_offers_found=m.total_offers_found,
        active_offers_count=m.active_offers_count,
        active_offers_trend=_trend(m.active_offers_trend),
        new_offers_count=m.new_offers_count,
        relevant_offers_count=m.relevant_offers_count,
        relevance_threshold=m.relevance_threshold,
        top_matches=[
            TopMatchResponse(**{**t.__dict__, "score": round(float(t.score), 1)})
            for t in m.top_matches
        ],
        active_applications_count=m.active_applications_count,
        applications_trend=_trend(m.applications_trend),
        applications_sent_count=m.applications_sent_count,
        interviews_count=m.interviews_count,
        response_rate=m.response_rate,
        funnel=FunnelResponse(**m.funnel.__dict__),
        applications_by_status=m.applications_by_status,
        interviews=[InterviewEventResponse(**i.__dict__) for i in m.interviews],
        ai_budget=AIBudgetResponse(**m.ai_budget.__dict__),
        recent_searches=[RecentSearchResponse(**s.__dict__) for s in m.recent_searches],
        recent_activities=[RecentActivityResponse(**a.__dict__) for a in m.recent_activities],
    )
