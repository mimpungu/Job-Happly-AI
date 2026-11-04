"""Routes FastAPI pour les notifications, les préférences et la planification."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.api.dependencies import SessionDep, get_owner_id
from app.modules.notifications.application.daily_digest_service import DailyDigestService
from app.modules.notifications.domain.enums import NotificationKind
from app.modules.notifications.domain.exceptions import (
    InvalidFrequencyError,
    InvalidTimezoneError,
    NotificationNotFoundError,
    ScheduledTaskNotFoundError,
)
from app.modules.notifications.infrastructure.composition import (
    build_daily_digest_service,
    build_notification_service,
    build_scheduler_service,
)
from app.modules.notifications.infrastructure.job_history import list_job_history
from app.modules.notifications.presentation.schemas import (
    DailyDigestResponse,
    JobAuditItem,
    JobHistoryResponse,
    NotificationListResponse,
    NotificationPreferencesRequest,
    NotificationPreferencesResponse,
    NotificationResponse,
    ScheduledTaskCreateRequest,
    ScheduledTaskResponse,
    ScheduledTaskUpdateRequest,
    TriggerTaskResponse,
    UnreadCountResponse,
)

notifications_router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])
scheduler_router = APIRouter(prefix="/api/v1/scheduler", tags=["scheduler"])

Owner = Annotated[uuid.UUID, Depends(get_owner_id)]


# --- Endpoints Notifications ---


@notifications_router.get("", response_model=NotificationListResponse)
async def list_notifications(
    session: SessionDep,
    owner_id: Owner,
    unread_only: Annotated[bool, Query(description="Filtrer uniquement les non lues")] = False,
    kind: Annotated[NotificationKind | None, Query(description="Filtrer par type")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> NotificationListResponse:
    service = build_notification_service(session)
    items, total = await service.list_notifications(
        owner_id=owner_id,
        unread_only=unread_only,
        kind=kind,
        limit=limit,
        offset=offset,
    )
    unread_count = await service.count_unread(owner_id=owner_id)
    return NotificationListResponse(
        items=[
            NotificationResponse(
                id=n.id,
                owner_id=n.owner_id,
                kind=n.kind,
                title=n.title,
                body=n.body,
                payload=n.payload,
                read_at=n.read_at,
                created_at=n.created_at,
                is_read=n.is_read,
            )
            for n in items
        ],
        total=total,
        unread_count=unread_count,
    )


@notifications_router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    session: SessionDep,
    owner_id: Owner,
) -> UnreadCountResponse:
    service = build_notification_service(session)
    count = await service.count_unread(owner_id=owner_id)
    return UnreadCountResponse(unread_count=count)


@notifications_router.patch("/{notification_id}/read", response_model=NotificationResponse)
async def mark_as_read(
    notification_id: uuid.UUID,
    session: SessionDep,
    owner_id: Owner,
) -> NotificationResponse:
    service = build_notification_service(session)
    try:
        updated = await service.mark_as_read(
            owner_id=owner_id,
            notification_id=notification_id,
        )
    except NotificationNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err

    await session.commit()
    return NotificationResponse(
        id=updated.id,
        owner_id=updated.owner_id,
        kind=updated.kind,
        title=updated.title,
        body=updated.body,
        payload=updated.payload,
        read_at=updated.read_at,
        created_at=updated.created_at,
        is_read=updated.is_read,
    )


@notifications_router.post("/mark-all-read")
async def mark_all_as_read(
    session: SessionDep,
    owner_id: Owner,
) -> dict[str, int]:
    service = build_notification_service(session)
    modifies = await service.mark_all_as_read(owner_id=owner_id)
    await session.commit()
    return {"marked_read": modifies}


@notifications_router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    notification_id: uuid.UUID,
    session: SessionDep,
    owner_id: Owner,
) -> None:
    service = build_notification_service(session)
    deleted = await service.delete_notification(
        owner_id=owner_id,
        notification_id=notification_id,
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification {notification_id} introuvable.",
        )
    await session.commit()


@notifications_router.get("/preferences", response_model=NotificationPreferencesResponse)
async def get_preferences(
    session: SessionDep,
    owner_id: Owner,
) -> NotificationPreferencesResponse:
    service = build_notification_service(session)
    prefs = await service.get_preferences(owner_id=owner_id)
    return NotificationPreferencesResponse(
        id=prefs.id,
        owner_id=prefs.owner_id,
        in_app_enabled=prefs.in_app_enabled,
        email_enabled=prefs.email_enabled,
        email_recipient=prefs.email_recipient,
        email_consent_given=prefs.email_consent_given,
        notify_new_offers=prefs.notify_new_offers,
        notify_relevant_matches=prefs.notify_relevant_matches,
        min_relevance_score=prefs.min_relevance_score,
        notify_search_errors=prefs.notify_search_errors,
        notify_follow_up_reminders=prefs.notify_follow_up_reminders,
        notify_ai_budget_alerts=prefs.notify_ai_budget_alerts,
        daily_digest_enabled=prefs.daily_digest_enabled,
        daily_digest_time=prefs.daily_digest_time,
        timezone=prefs.timezone,
    )


@notifications_router.put("/preferences", response_model=NotificationPreferencesResponse)
async def update_preferences(
    req: NotificationPreferencesRequest,
    session: SessionDep,
    owner_id: Owner,
) -> NotificationPreferencesResponse:
    service = build_notification_service(session)
    updated = await service.update_preferences(
        owner_id=owner_id,
        in_app_enabled=req.in_app_enabled,
        email_enabled=req.email_enabled,
        email_recipient=req.email_recipient,
        email_consent_given=req.email_consent_given,
        notify_new_offers=req.notify_new_offers,
        notify_relevant_matches=req.notify_relevant_matches,
        min_relevance_score=req.min_relevance_score,
        notify_search_errors=req.notify_search_errors,
        notify_follow_up_reminders=req.notify_follow_up_reminders,
        notify_ai_budget_alerts=req.notify_ai_budget_alerts,
        daily_digest_enabled=req.daily_digest_enabled,
        daily_digest_time=req.daily_digest_time,
        timezone=req.timezone,
    )
    await session.commit()
    return NotificationPreferencesResponse(
        id=updated.id,
        owner_id=updated.owner_id,
        in_app_enabled=updated.in_app_enabled,
        email_enabled=updated.email_enabled,
        email_recipient=updated.email_recipient,
        email_consent_given=updated.email_consent_given,
        notify_new_offers=updated.notify_new_offers,
        notify_relevant_matches=updated.notify_relevant_matches,
        min_relevance_score=updated.min_relevance_score,
        notify_search_errors=updated.notify_search_errors,
        notify_follow_up_reminders=updated.notify_follow_up_reminders,
        notify_ai_budget_alerts=updated.notify_ai_budget_alerts,
        daily_digest_enabled=updated.daily_digest_enabled,
        daily_digest_time=updated.daily_digest_time,
        timezone=updated.timezone,
    )


# --- Endpoints Scheduler ---


@scheduler_router.post(
    "/tasks", response_model=ScheduledTaskResponse, status_code=status.HTTP_201_CREATED
)
async def create_scheduled_task(
    req: ScheduledTaskCreateRequest,
    request: Request,
    session: SessionDep,
    owner_id: Owner,
) -> ScheduledTaskResponse:
    fabrique: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    service = build_scheduler_service(session, fabrique)
    try:
        task = await service.create_task(
            owner_id=owner_id,
            task_type=req.task_type,
            frequency=req.frequency,
            interval_minutes=req.interval_minutes,
            target_hour=req.target_hour,
            target_minute=req.target_minute,
            timezone=req.timezone,
            payload=req.payload,
            enabled=req.enabled,
        )
    except (InvalidTimezoneError, InvalidFrequencyError) as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err)
        ) from err

    await session.commit()
    return ScheduledTaskResponse(
        id=task.id,
        owner_id=task.owner_id,
        task_type=task.task_type,
        frequency=task.frequency,
        interval_minutes=task.interval_minutes,
        target_hour=task.target_hour,
        target_minute=task.target_minute,
        timezone=task.timezone,
        payload=task.payload,
        enabled=task.enabled,
        last_run_at=task.last_run_at,
        next_run_at=task.next_run_at,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@scheduler_router.get("/tasks", response_model=list[ScheduledTaskResponse])
async def list_scheduled_tasks(
    request: Request,
    session: SessionDep,
    owner_id: Owner,
    enabled_only: Annotated[bool, Query()] = False,
) -> list[ScheduledTaskResponse]:
    fabrique: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    service = build_scheduler_service(session, fabrique)
    tasks = await service.list_tasks(owner_id=owner_id, enabled_only=enabled_only)
    return [
        ScheduledTaskResponse(
            id=t.id,
            owner_id=t.owner_id,
            task_type=t.task_type,
            frequency=t.frequency,
            interval_minutes=t.interval_minutes,
            target_hour=t.target_hour,
            target_minute=t.target_minute,
            timezone=t.timezone,
            payload=t.payload,
            enabled=t.enabled,
            last_run_at=t.last_run_at,
            next_run_at=t.next_run_at,
            created_at=t.created_at,
            updated_at=t.updated_at,
        )
        for t in tasks
    ]


@scheduler_router.get("/tasks/{task_id}", response_model=ScheduledTaskResponse)
async def get_scheduled_task(
    task_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    owner_id: Owner,
) -> ScheduledTaskResponse:
    fabrique: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    service = build_scheduler_service(session, fabrique)
    try:
        task = await service.get_task(task_id=task_id, owner_id=owner_id)
    except ScheduledTaskNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err

    return ScheduledTaskResponse(
        id=task.id,
        owner_id=task.owner_id,
        task_type=task.task_type,
        frequency=task.frequency,
        interval_minutes=task.interval_minutes,
        target_hour=task.target_hour,
        target_minute=task.target_minute,
        timezone=task.timezone,
        payload=task.payload,
        enabled=task.enabled,
        last_run_at=task.last_run_at,
        next_run_at=task.next_run_at,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@scheduler_router.put("/tasks/{task_id}", response_model=ScheduledTaskResponse)
async def update_scheduled_task(
    task_id: uuid.UUID,
    req: ScheduledTaskUpdateRequest,
    request: Request,
    session: SessionDep,
    owner_id: Owner,
) -> ScheduledTaskResponse:
    fabrique: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    service = build_scheduler_service(session, fabrique)
    try:
        task = await service.update_task(
            task_id=task_id,
            owner_id=owner_id,
            frequency=req.frequency,
            interval_minutes=req.interval_minutes,
            target_hour=req.target_hour,
            target_minute=req.target_minute,
            timezone=req.timezone,
            payload=req.payload,
            enabled=req.enabled,
        )
    except ScheduledTaskNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err
    except (InvalidTimezoneError, InvalidFrequencyError) as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err)
        ) from err

    await session.commit()
    return ScheduledTaskResponse(
        id=task.id,
        owner_id=task.owner_id,
        task_type=task.task_type,
        frequency=task.frequency,
        interval_minutes=task.interval_minutes,
        target_hour=task.target_hour,
        target_minute=task.target_minute,
        timezone=task.timezone,
        payload=task.payload,
        enabled=task.enabled,
        last_run_at=task.last_run_at,
        next_run_at=task.next_run_at,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@scheduler_router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scheduled_task(
    task_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    owner_id: Owner,
) -> None:
    fabrique: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    service = build_scheduler_service(session, fabrique)
    deleted = await service.delete_task(task_id=task_id, owner_id=owner_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tâche planifiée {task_id} introuvable.",
        )
    await session.commit()


@scheduler_router.post("/tasks/{task_id}/trigger", response_model=TriggerTaskResponse)
async def trigger_task(
    task_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    owner_id: Owner,
) -> TriggerTaskResponse:
    fabrique: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    service = build_scheduler_service(session, fabrique)
    try:
        job_id = await service.trigger_task_now(task_id=task_id, owner_id=owner_id)
    except ScheduledTaskNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err

    return TriggerTaskResponse(job_id=job_id, status="queued")


@scheduler_router.post("/enqueue-due")
async def enqueue_due_tasks(
    request: Request,
    session: SessionDep,
    _owner_id: Owner,
) -> dict[str, int]:
    fabrique: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    service = build_scheduler_service(session, fabrique)
    count = await service.enqueue_due_tasks()
    await session.commit()
    return {"enqueued": count}


@scheduler_router.get("/jobs/history", response_model=JobHistoryResponse)
async def get_job_history(
    session: SessionDep,
    owner_id: Owner,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    kind: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> JobHistoryResponse:
    items, total = await list_job_history(
        session,
        owner_id=owner_id,
        status=status_filter,
        kind=kind,
        limit=limit,
        offset=offset,
    )
    return JobHistoryResponse(
        items=[JobAuditItem(**it) for it in items],
        total=total,
    )


@scheduler_router.post("/daily-digest/generate", response_model=DailyDigestResponse)
async def generate_daily_digest(
    session: SessionDep,
    owner_id: Owner,
) -> DailyDigestResponse:
    service: DailyDigestService = build_daily_digest_service(session)
    digest = await service.generate_digest(owner_id=owner_id)
    await session.commit()
    return DailyDigestResponse(
        date=digest.date,
        new_offers_count=digest.new_offers_count,
        top_offers_count=digest.top_offers_count,
        follow_ups_due_count=digest.follow_ups_due_count,
        active_applications_count=digest.active_applications_count,
        ai_spent_today=float(digest.ai_spent_today),
        sample_offers=list(digest.sample_offers),
    )
