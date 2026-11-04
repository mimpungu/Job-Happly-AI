"""Routes HTTP pour le suivi des candidatures et le tableau de bord (EPIC 014)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.api.dependencies import SessionDep, get_owner_id
from app.modules.application_management.domain.enums import ApplicationStatus
from app.modules.application_management.domain.exceptions import (
    ApplicationNotFoundError,
    DuplicateApplicationError,
    ExternalOfferLinkMissingError,
    InvalidStatusTransitionError,
)
from app.modules.application_management.infrastructure.composition import (
    build_application_tracking_service,
    build_dashboard_service,
)
from app.modules.application_management.presentation.schemas import (
    AddContactRequest,
    AddInterviewRequest,
    AddNoteRequest,
    ApplicationDetailResponse,
    ApplicationDossierResponse,
    ApplicationListResponse,
    ApplicationResponse,
    ApplicationStatsResponse,
    AttachDocumentsRequest,
    ChangeStatusRequest,
    ConfirmSubmissionRequest,
    ContactResponse,
    CreateApplicationRequest,
    DashboardMetricsResponse,
    KanbanColumnResponse,
    KanbanViewResponse,
    ScheduleFollowUpRequest,
    TimelineEventResponse,
)
from app.modules.job_discovery.infrastructure.models import JobOfferModel

applications_router = APIRouter(prefix="/api/v1/applications", tags=["application-tracking"])
dashboard_router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])

Owner = Annotated[uuid.UUID, Depends(get_owner_id)]


# ---------------------------------------------------------------------------
# Endpoints de gestion des candidatures
# ---------------------------------------------------------------------------


@applications_router.post(
    "",
    response_model=ApplicationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_application(
    body: CreateApplicationRequest,
    session: SessionDep,
    owner_id: Owner,
) -> ApplicationResponse:
    """Crée une nouvelle candidature associée à une offre d'emploi (TASK-014-01, 02)."""
    service = build_application_tracking_service(session)
    try:
        app = await service.create_application(
            owner_id=owner_id,
            offer_id=body.offer_id,
            initial_status=body.initial_status,
        )
    except DuplicateApplicationError as err:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(err)) from err

    return ApplicationResponse(
        id=app.id,
        offer_id=app.offer_id,
        status=app.status,
        created_at=app.created_at,
        updated_at=app.updated_at,
        applied_at=app.applied_at,
        follow_up_at=app.follow_up_at,
        response_received_at=app.response_received_at,
        cv_version_id=app.cv_version_id,
        letter_version_id=app.letter_version_id,
    )


@applications_router.get("", response_model=ApplicationListResponse)
async def list_applications(
    session: SessionDep,
    owner_id: Owner,
    status_filter: Annotated[ApplicationStatus | None, Query(alias="status")] = None,
    company: Annotated[str | None, Query()] = None,
    title: Annotated[str | None, Query()] = None,
    has_follow_up_due: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ApplicationListResponse:
    """Liste les candidatures avec filtres (vue tableau) (TASK-014-11, 13)."""
    service = build_application_tracking_service(session)
    items, total = await service.list_applications(
        owner_id=owner_id,
        status=status_filter,
        company_query=company,
        title_query=title,
        has_follow_up_due=has_follow_up_due,
        limit=limit,
        offset=offset,
    )

    responses = [
        ApplicationResponse(
            id=a.id,
            offer_id=a.offer_id,
            status=a.status,
            created_at=a.created_at,
            updated_at=a.updated_at,
            applied_at=a.applied_at,
            follow_up_at=a.follow_up_at,
            response_received_at=a.response_received_at,
            cv_version_id=a.cv_version_id,
            letter_version_id=a.letter_version_id,
        )
        for a in items
    ]

    return ApplicationListResponse(
        items=responses,
        total=total,
        limit=limit,
        offset=offset,
    )


@applications_router.get("/kanban", response_model=KanbanViewResponse)
async def get_kanban_view(
    session: SessionDep,
    owner_id: Owner,
) -> KanbanViewResponse:
    """Vue Kanban découpée par colonne de statut (TASK-014-12)."""
    service = build_application_tracking_service(session)
    kanban_dict = await service.get_kanban_view(owner_id=owner_id)

    columns = []
    for st in ApplicationStatus:
        apps = kanban_dict.get(st, [])
        columns.append(
            KanbanColumnResponse(
                status=st,
                count=len(apps),
                items=[
                    ApplicationResponse(
                        id=a.id,
                        offer_id=a.offer_id,
                        status=a.status,
                        created_at=a.created_at,
                        updated_at=a.updated_at,
                        applied_at=a.applied_at,
                        follow_up_at=a.follow_up_at,
                        response_received_at=a.response_received_at,
                        cv_version_id=a.cv_version_id,
                        letter_version_id=a.letter_version_id,
                    )
                    for a in apps
                ],
            )
        )
    return KanbanViewResponse(columns=columns)


@applications_router.get("/stats", response_model=ApplicationStatsResponse)
async def get_application_stats(
    session: SessionDep,
    owner_id: Owner,
) -> ApplicationStatsResponse:
    """Statistiques de suivi basées strictement sur des données réelles (TASK-014-15, 22)."""
    service = build_application_tracking_service(session)
    stats = await service.get_stats(owner_id=owner_id)
    return ApplicationStatsResponse(
        total_applications=stats.total_applications,
        sent_applications=stats.sent_applications,
        interviews_count=stats.interviews_count,
        offers_received_count=stats.offers_received_count,
        rejections_count=stats.rejections_count,
        response_rate=stats.response_rate,
        active_applications=stats.active_applications,
        pending_follow_ups_count=stats.pending_follow_ups_count,
    )


@applications_router.get("/{application_id}", response_model=ApplicationDetailResponse)
async def get_application_detail(
    application_id: uuid.UUID,
    session: SessionDep,
    owner_id: Owner,
) -> ApplicationDetailResponse:
    """Fiche détaillée d'une candidature avec contacts et historique (TASK-014-14)."""
    service = build_application_tracking_service(session)
    try:
        app = await service.get_application(owner_id=owner_id, application_id=application_id)
    except ApplicationNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err

    return ApplicationDetailResponse(
        id=app.id,
        offer_id=app.offer_id,
        status=app.status,
        created_at=app.created_at,
        updated_at=app.updated_at,
        applied_at=app.applied_at,
        follow_up_at=app.follow_up_at,
        response_received_at=app.response_received_at,
        cv_version_id=app.cv_version_id,
        letter_version_id=app.letter_version_id,
        contacts=[
            ContactResponse(
                id=c.id,
                application_id=c.application_id,
                name=c.name,
                email=c.email,
                phone=c.phone,
                role=c.role,
                created_at=c.created_at,
            )
            for c in app.contacts
        ],
        events=[
            TimelineEventResponse(
                id=e.id,
                application_id=e.application_id,
                kind=e.kind,
                occurred_at=e.occurred_at,
                from_status=e.from_status,
                to_status=e.to_status,
                body=e.body,
            )
            for e in app.events
        ],
        documents=[],
    )


@applications_router.patch("/{application_id}/status", response_model=ApplicationResponse)
async def change_application_status(
    application_id: uuid.UUID,
    body: ChangeStatusRequest,
    session: SessionDep,
    owner_id: Owner,
) -> ApplicationResponse:
    """Met à jour le statut avec validation de la machine à états (TASK-014-03, 06)."""
    service = build_application_tracking_service(session)
    try:
        app = await service.change_status(
            owner_id=owner_id,
            application_id=application_id,
            target_status=body.target_status,
            reason=body.reason,
        )
    except ApplicationNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err
    except InvalidStatusTransitionError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err)
        ) from err

    return ApplicationResponse(
        id=app.id,
        offer_id=app.offer_id,
        status=app.status,
        created_at=app.created_at,
        updated_at=app.updated_at,
        applied_at=app.applied_at,
        follow_up_at=app.follow_up_at,
        response_received_at=app.response_received_at,
        cv_version_id=app.cv_version_id,
        letter_version_id=app.letter_version_id,
    )


@applications_router.post(
    "/{application_id}/confirm-submission",
    response_model=ApplicationResponse,
)
async def confirm_manual_submission(
    application_id: uuid.UUID,
    body: ConfirmSubmissionRequest,
    session: SessionDep,
    owner_id: Owner,
) -> ApplicationResponse:
    """Confirme manuellement l'envoi de la candidature par l'utilisateur (TASK-014-04, 20)."""
    service = build_application_tracking_service(session)
    try:
        app = await service.confirm_manual_submission(
            owner_id=owner_id,
            application_id=application_id,
            notes=body.notes,
        )
    except ApplicationNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err

    return ApplicationResponse(
        id=app.id,
        offer_id=app.offer_id,
        status=app.status,
        created_at=app.created_at,
        updated_at=app.updated_at,
        applied_at=app.applied_at,
        follow_up_at=app.follow_up_at,
        response_received_at=app.response_received_at,
        cv_version_id=app.cv_version_id,
        letter_version_id=app.letter_version_id,
    )


@applications_router.post(
    "/{application_id}/notes",
    response_model=TimelineEventResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_application_note(
    application_id: uuid.UUID,
    body: AddNoteRequest,
    session: SessionDep,
    owner_id: Owner,
) -> TimelineEventResponse:
    """Ajoute une note personnelle à la candidature (TASK-014-07)."""
    service = build_application_tracking_service(session)
    try:
        event = await service.add_note(
            owner_id=owner_id,
            application_id=application_id,
            note_body=body.body,
        )
    except ApplicationNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err

    return TimelineEventResponse(
        id=event.id,
        application_id=event.application_id,
        kind=event.kind,
        occurred_at=event.occurred_at,
        from_status=event.from_status,
        to_status=event.to_status,
        body=event.body,
    )


@applications_router.post(
    "/{application_id}/interviews",
    response_model=TimelineEventResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_interview_event(
    application_id: uuid.UUID,
    body: AddInterviewRequest,
    session: SessionDep,
    owner_id: Owner,
) -> TimelineEventResponse:
    """Ajoute un événement d'entretien ou de rendez-vous (TASK-014-08)."""
    service = build_application_tracking_service(session)
    try:
        event = await service.add_interview_event(
            owner_id=owner_id,
            application_id=application_id,
            description=body.description,
            interview_time=body.interview_time,
        )
    except ApplicationNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err

    return TimelineEventResponse(
        id=event.id,
        application_id=event.application_id,
        kind=event.kind,
        occurred_at=event.occurred_at,
        from_status=event.from_status,
        to_status=event.to_status,
        body=event.body,
    )


@applications_router.patch("/{application_id}/follow-up", response_model=ApplicationResponse)
async def schedule_follow_up(
    application_id: uuid.UUID,
    body: ScheduleFollowUpRequest,
    session: SessionDep,
    owner_id: Owner,
) -> ApplicationResponse:
    """Planifie ou modifie la date de relance (TASK-014-10)."""
    service = build_application_tracking_service(session)
    try:
        app = await service.schedule_follow_up(
            owner_id=owner_id,
            application_id=application_id,
            follow_up_at=body.follow_up_at,
            notes=body.notes,
        )
    except ApplicationNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err

    return ApplicationResponse(
        id=app.id,
        offer_id=app.offer_id,
        status=app.status,
        created_at=app.created_at,
        updated_at=app.updated_at,
        applied_at=app.applied_at,
        follow_up_at=app.follow_up_at,
        response_received_at=app.response_received_at,
        cv_version_id=app.cv_version_id,
        letter_version_id=app.letter_version_id,
    )


@applications_router.put("/{application_id}/documents", response_model=ApplicationResponse)
async def attach_documents(
    application_id: uuid.UUID,
    body: AttachDocumentsRequest,
    session: SessionDep,
    owner_id: Owner,
) -> ApplicationResponse:
    """Associe les versions exactes de CV et/ou lettre envoyées (TASK-014-09)."""
    service = build_application_tracking_service(session)
    try:
        app = await service.attach_documents(
            owner_id=owner_id,
            application_id=application_id,
            cv_version_id=body.cv_version_id,
            letter_version_id=body.letter_version_id,
        )
    except ApplicationNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err

    return ApplicationResponse(
        id=app.id,
        offer_id=app.offer_id,
        status=app.status,
        created_at=app.created_at,
        updated_at=app.updated_at,
        applied_at=app.applied_at,
        follow_up_at=app.follow_up_at,
        response_received_at=app.response_received_at,
        cv_version_id=app.cv_version_id,
        letter_version_id=app.letter_version_id,
    )


@applications_router.post(
    "/{application_id}/contacts",
    response_model=ContactResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_contact(
    application_id: uuid.UUID,
    body: AddContactRequest,
    session: SessionDep,
    owner_id: Owner,
) -> ContactResponse:
    """Enregistre un contact ou recruteur lié à la candidature (TASK-014-05)."""
    service = build_application_tracking_service(session)
    try:
        contact = await service.add_contact(
            owner_id=owner_id,
            application_id=application_id,
            name=body.name,
            email=body.email,
            phone=body.phone,
            role=body.role,
        )
    except ApplicationNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err

    return ContactResponse(
        id=contact.id,
        application_id=contact.application_id,
        name=contact.name,
        email=contact.email,
        phone=contact.phone,
        role=contact.role,
        created_at=contact.created_at,
    )


@applications_router.get("/{application_id}/dossier", response_model=ApplicationDossierResponse)
async def get_application_dossier(
    application_id: uuid.UUID,
    session: SessionDep,
    owner_id: Owner,
) -> ApplicationDossierResponse:
    """Consulte et vérifie le dossier de candidature (TASK-014-16, 17, 18)."""
    service = build_application_tracking_service(session)
    try:
        app = await service.get_application(owner_id=owner_id, application_id=application_id)
    except ApplicationNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err

    offer = await session.get(JobOfferModel, app.offer_id)
    if offer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offre liée introuvable.")

    dossier = await service.prepare_dossier(
        owner_id=owner_id,
        application_id=application_id,
        job_title=offer.title,
        company_name=offer.company_name,
        application_url=offer.application_url,
    )

    return ApplicationDossierResponse(
        application_id=dossier.application_id,
        offer_id=dossier.offer_id,
        job_title=dossier.job_title,
        company_name=dossier.company_name,
        application_url=dossier.application_url,
        has_cv=dossier.has_cv,
        cv_version_id=dossier.cv_version_id,
        has_letter=dossier.has_letter,
        letter_version_id=dossier.letter_version_id,
        is_ready_to_send=dossier.is_ready_to_send,
        missing_elements=list(dossier.missing_elements),
    )


@applications_router.get("/{application_id}/open-url")
async def get_application_action_url(
    application_id: uuid.UUID,
    session: SessionDep,
    owner_id: Owner,
) -> dict[str, str]:
    """Retourne l'URL de candidature externe vérifiée (TASK-014-19)."""
    service = build_application_tracking_service(session)
    try:
        app = await service.get_application(owner_id=owner_id, application_id=application_id)
    except ApplicationNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err

    offer = await session.get(JobOfferModel, app.offer_id)
    if offer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offre liée introuvable.")

    try:
        url = await service.get_application_url_action(
            owner_id=owner_id,
            application_id=application_id,
            offer_application_url=offer.application_url,
        )
    except ExternalOfferLinkMissingError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err

    return {"application_url": url}


# ---------------------------------------------------------------------------
# Endpoints du tableau de bord
# ---------------------------------------------------------------------------


@dashboard_router.get("", response_model=DashboardMetricsResponse)
async def get_dashboard_metrics(
    session: SessionDep,
    owner_id: Owner,
) -> DashboardMetricsResponse:
    """Retourne la synthèse des indicateurs réels du tableau de bord (TASK-014-21, 22)."""
    service = build_dashboard_service(session)
    metrics = await service.get_dashboard(owner_id=owner_id)
    return DashboardMetricsResponse(
        total_offers_found=metrics.total_offers_found,
        new_offers_count=metrics.new_offers_count,
        relevant_offers_count=metrics.relevant_offers_count,
        applications_sent_count=metrics.applications_sent_count,
        interviews_count=metrics.interviews_count,
        response_rate=metrics.response_rate,
        ai_budget_consumed_cents=metrics.ai_budget_consumed_cents,
        ai_budget_limit_cents=metrics.ai_budget_limit_cents,
    )
