"""Orchestration des tâches asynchrones et gestionnaires de jobs d'automatisation."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai_management.infrastructure.models import AISettingsModel, AIUsageModel
from app.modules.application_management.domain.enums import ApplicationStatus
from app.modules.application_management.infrastructure.models import (
    ApplicationModel,
)
from app.modules.job_discovery.domain.saved_search import SavedSearchNotFoundError
from app.modules.job_discovery.infrastructure.models import JobOfferModel, SavedSearchModel
from app.modules.notifications.application.daily_digest_service import DailyDigestService
from app.modules.notifications.application.notification_service import NotificationService
from app.modules.notifications.domain.enums import NotificationKind, ScheduledTaskType
from app.modules.platform.infrastructure.job_queue import PostgresJobQueue, ReservedJob
from app.modules.platform.infrastructure.models import JobModel

logger = logging.getLogger("happly.orchestrator")


def _now() -> datetime:
    return datetime.now(UTC)


class AutomationJobHandlers:
    """Fournit les handlers de traitement des différentes tâches de fond."""

    def __init__(
        self,
        session: AsyncSession,
        notification_service: NotificationService,
        job_queue: PostgresJobQueue,
        *,
        clock: Callable[[], datetime] = _now,
    ) -> None:
        self._session = session
        self._notifications = notification_service
        self._job_queue = job_queue
        self._clock = clock

    async def handle_recurring_search(self, job: ReservedJob) -> None:
        """Exécute une recherche sauvegardée récurrente et notifie l'utilisateur."""
        owner_id = job.owner_id
        if owner_id is None:
            return

        payload = job.payload
        saved_search_id_str = payload.get("saved_search_id")
        if not saved_search_id_str:
            return

        saved_search_id = uuid.UUID(saved_search_id_str)
        stmt = select(SavedSearchModel).where(
            SavedSearchModel.id == saved_search_id,
            SavedSearchModel.owner_id == owner_id,
        )
        saved_search = await self._session.scalar(stmt)
        if saved_search is None:
            raise SavedSearchNotFoundError(f"Recherche sauvegardée {saved_search_id} introuvable.")

        if not saved_search.active:
            logger.info(
                "Recherche inactive ignorée", extra={"saved_search_id": str(saved_search_id)}
            )
            return

        # Compte les offres récentes créées depuis 24h
        maintenant = self._clock()
        hier = maintenant - timedelta(days=1)
        count_stmt = select(func.count(JobOfferModel.id)).where(
            JobOfferModel.owner_id == owner_id,
            JobOfferModel.created_at >= hier,
        )
        count_recent = (await self._session.scalar(count_stmt)) or 0

        # Si des offres sont trouvées, notifier l'utilisateur
        if count_recent > 0:
            await self._notifications.notify(
                owner_id=owner_id,
                kind=NotificationKind.NEW_OFFERS,
                title="Nouvelles offres d'emploi disponibles",
                body=(
                    f"{count_recent} nouvelle(s) offre(s) correspondent à votre recherche "
                    f"'{saved_search.name}'."
                ),
                payload={
                    "saved_search_id": str(saved_search_id),
                    "search_name": saved_search.name,
                    "new_offers_count": count_recent,
                },
            )

    async def handle_follow_up_check(self, job: ReservedJob) -> None:
        """Vérifie les relances de candidatures échues et émet les rappels."""
        owner_id = job.owner_id
        if owner_id is None:
            return

        maintenant = self._clock()
        stmt = select(ApplicationModel).where(
            ApplicationModel.owner_id == owner_id,
            ApplicationModel.follow_up_at.is_not(None),
            ApplicationModel.follow_up_at <= maintenant,
            ApplicationModel.status.in_(
                [
                    ApplicationStatus.SENT.value,
                    ApplicationStatus.PENDING.value,
                    ApplicationStatus.INTERVIEW.value,
                    ApplicationStatus.SECOND_INTERVIEW.value,
                ]
            ),
        )
        applications = (await self._session.scalars(stmt)).all()

        for app in applications:
            # Récupération de l'intitulé et de l'entreprise via l'offre associée
            offre_stmt = select(JobOfferModel).where(JobOfferModel.id == app.offer_id)
            offre = await self._session.scalar(offre_stmt)
            titre = offre.title if offre else "Poste candidaté"
            entreprise = offre.company_name if offre and offre.company_name else "Entreprise"

            corps = (
                f"Votre candidature pour '{titre}' chez {entreprise} est à relancer aujourd'hui."
            )
            await self._notifications.notify(
                owner_id=owner_id,
                kind=NotificationKind.FOLLOW_UP_REMINDER,
                title=f"Rappel de relance : {entreprise}",
                body=corps,
                payload={
                    "application_id": str(app.id),
                    "offer_id": str(app.offer_id),
                    "company": entreprise,
                    "title": titre,
                },
            )

    async def handle_ai_budget_check(self, job: ReservedJob) -> None:
        """Contrôle les seuils de consommation du budget IA et alerte si nécessaire."""
        owner_id = job.owner_id
        if owner_id is None:
            return

        # Récupération des plafonds configurés
        settings_stmt = select(AISettingsModel).where(AISettingsModel.owner_id == owner_id)
        settings = await self._session.scalar(settings_stmt)

        maintenant = self._clock()
        debut_jour = datetime(maintenant.year, maintenant.month, maintenant.day, tzinfo=UTC)

        usage_stmt = select(
            func.coalesce(
                func.sum(AIUsageModel.actual_cost),
                func.sum(AIUsageModel.estimated_cost),
                0,
            )
        ).where(
            AIUsageModel.owner_id == owner_id,
            AIUsageModel.created_at >= debut_jour,
        )
        somme = await self._session.scalar(usage_stmt)
        depense = Decimal(str(somme)) if somme is not None else Decimal("0.0000")

        # Seuil d'avertissement si la dépense quotidienne dépasse un montant significatif
        if depense > Decimal("1.0000"):
            await self._notifications.notify(
                owner_id=owner_id,
                kind=NotificationKind.AI_BUDGET_ALERT,
                title="Alerte consommation IA",
                body=f"Votre consommation IA aujourd'hui s'élève à {depense:.4f} EUR.",
                payload={
                    "spent_today": float(depense),
                    "currency": settings.currency if settings else "EUR",
                },
            )

    async def handle_daily_digest(self, job: ReservedJob) -> None:
        """Génère le résumé quotidien pour le propriétaire."""
        owner_id = job.owner_id
        if owner_id is None:
            return

        digest_service = DailyDigestService(
            session=self._session,
            notification_service=self._notifications,
            clock=self._clock,
        )
        await digest_service.generate_digest(owner_id=owner_id)

    async def handle_stale_jobs_cleanup(self, job: ReservedJob) -> None:
        """Reprend les tâches orphelines dont le verrou a expiré."""
        await self._job_queue.recover_stale(lock_timeout=timedelta(minutes=15))

    def as_handler_mapping(self) -> dict[str, Callable[[ReservedJob], Any]]:
        """Mappe les types de tâches planifiées vers leurs méthodes d'exécution respectives."""
        return {
            ScheduledTaskType.RECURRING_SEARCH.value: self.handle_recurring_search,
            ScheduledTaskType.FOLLOW_UP_CHECK.value: self.handle_follow_up_check,
            ScheduledTaskType.AI_BUDGET_CHECK.value: self.handle_ai_budget_check,
            ScheduledTaskType.DAILY_DIGEST.value: self.handle_daily_digest,
            ScheduledTaskType.STALE_JOBS_CLEANUP.value: self.handle_stale_jobs_cleanup,
        }


async def list_job_history(
    session: AsyncSession,
    *,
    owner_id: uuid.UUID | None = None,
    status: str | None = None,
    kind: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Interroge la table jobs pour fournir un audit et historique d'exécution (TASK-015-10)."""
    critères = []
    if owner_id is not None:
        critères.append(JobModel.owner_id == owner_id)
    if status is not None:
        critères.append(JobModel.status == status)
    if kind is not None:
        critères.append(JobModel.kind == kind)

    count_stmt = select(func.count(JobModel.id)).where(*critères)
    total = (await session.scalar(count_stmt)) or 0

    stmt = (
        select(JobModel)
        .where(*critères)
        .order_by(JobModel.created_at.desc(), JobModel.id.desc())
        .limit(limit)
        .offset(offset)
    )
    jobs = (await session.scalars(stmt)).all()

    items = [
        {
            "id": str(j.id),
            "owner_id": str(j.owner_id) if j.owner_id else None,
            "kind": j.kind,
            "idempotency_key": j.idempotency_key,
            "status": j.status,
            "attempts": j.attempts,
            "max_attempts": j.max_attempts,
            "run_at": j.run_at.isoformat() if j.run_at else None,
            "locked_at": j.locked_at.isoformat() if j.locked_at else None,
            "locked_by": j.locked_by,
            "finished_at": j.finished_at.isoformat() if j.finished_at else None,
            "last_error": j.last_error,
            "created_at": j.created_at.isoformat() if j.created_at else None,
        }
        for j in jobs
    ]
    return items, total
