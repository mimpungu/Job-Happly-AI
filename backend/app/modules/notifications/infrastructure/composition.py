"""Fabriques d'injection de dépendances pour les notifications et le planificateur."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import UnitOfWork
from app.modules.notifications.application.daily_digest_service import DailyDigestService
from app.modules.notifications.application.notification_service import NotificationService
from app.modules.notifications.application.scheduler_service import SchedulerService
from app.modules.notifications.infrastructure.email_sender import SafeEmailSender
from app.modules.notifications.infrastructure.notification_repository import (
    SQLAlchemyNotificationRepository,
)
from app.modules.notifications.infrastructure.preferences_repository import (
    SQLAlchemyNotificationPreferencesRepository,
)
from app.modules.notifications.infrastructure.scheduled_task_repository import (
    SQLAlchemyScheduledTaskRepository,
)
from app.modules.platform.infrastructure.job_queue import PostgresJobQueue

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import async_sessionmaker

_EMAIL_SENDER_SINGLETON = SafeEmailSender(configured=True)


def get_email_sender() -> SafeEmailSender:
    """Retourne l'adaptateur d'expédition e-mail configuré pour l'application."""
    return _EMAIL_SENDER_SINGLETON


def build_notification_service(
    session: AsyncSession,
    *,
    email_sender: SafeEmailSender | None = None,
) -> NotificationService:
    """Instancie le service de notifications branché sur la session et l'expéditeur e-mail."""
    notification_repo = SQLAlchemyNotificationRepository(session)
    preferences_repo = SQLAlchemyNotificationPreferencesRepository(session)
    sender = email_sender or get_email_sender()
    return NotificationService(
        notification_repo=notification_repo,
        preferences_repo=preferences_repo,
        email_sender=sender,
    )


def build_scheduler_service(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> SchedulerService:
    """Instancie le service de planification des tâches récurrentes."""
    task_repo = SQLAlchemyScheduledTaskRepository(session)
    uow = UnitOfWork(session_factory)
    job_queue = PostgresJobQueue(uow)
    return SchedulerService(task_repo=task_repo, job_queue=job_queue)


def build_daily_digest_service(
    session: AsyncSession,
    notification_service: NotificationService | None = None,
) -> DailyDigestService:
    """Instancie le service du résumé quotidien."""
    notifs = notification_service or build_notification_service(session)
    return DailyDigestService(session=session, notification_service=notifs)
