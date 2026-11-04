"""Orchestration des tâches asynchrones et gestionnaires de jobs d'automatisation."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from app.modules.job_discovery.domain.saved_search import SavedSearchNotFoundError
from app.modules.notifications.application.daily_digest_service import DailyDigestService
from app.modules.notifications.application.notification_service import NotificationService
from app.modules.notifications.application.ports import AutomationFactsPort
from app.modules.notifications.domain.enums import NotificationKind, ScheduledTaskType
from app.modules.platform.infrastructure.job_queue import PostgresJobQueue, ReservedJob

logger = logging.getLogger("happly.orchestrator")


def _now() -> datetime:
    return datetime.now(UTC)


class AutomationJobHandlers:
    """Fournit les handlers de traitement des différentes tâches de fond."""

    def __init__(
        self,
        facts: AutomationFactsPort,
        notification_service: NotificationService,
        job_queue: PostgresJobQueue,
        *,
        clock: Callable[[], datetime] = _now,
    ) -> None:
        self._facts = facts
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
        saved_search = await self._facts.saved_search(owner_id, saved_search_id)
        if saved_search is None:
            raise SavedSearchNotFoundError(f"Recherche sauvegardée {saved_search_id} introuvable.")

        if not saved_search.active:
            logger.info(
                "Recherche inactive ignorée", extra={"saved_search_id": str(saved_search_id)}
            )
            return

        # Compte les offres récentes créées depuis 24h
        maintenant = self._clock()
        count_recent = await self._facts.offers_created_since(
            owner_id, maintenant - timedelta(days=1)
        )

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
        for relance in await self._facts.due_follow_ups(owner_id, maintenant):
            titre, entreprise = relance.title, relance.company
            corps = (
                f"Votre candidature pour '{titre}' chez {entreprise} est à relancer aujourd'hui."
            )
            await self._notifications.notify(
                owner_id=owner_id,
                kind=NotificationKind.FOLLOW_UP_REMINDER,
                title=f"Rappel de relance : {entreprise}",
                body=corps,
                payload={
                    "application_id": str(relance.application_id),
                    "offer_id": str(relance.offer_id),
                    "company": entreprise,
                    "title": titre,
                },
            )

    async def handle_ai_budget_check(self, job: ReservedJob) -> None:
        """Contrôle les seuils de consommation du budget IA et alerte si nécessaire."""
        owner_id = job.owner_id
        if owner_id is None:
            return

        maintenant = self._clock()
        debut_jour = datetime(maintenant.year, maintenant.month, maintenant.day, tzinfo=UTC)
        depense = await self._facts.ai_spent_since(owner_id, debut_jour)

        # Seuil d'avertissement si la dépense quotidienne dépasse un montant significatif
        if depense > Decimal("1.0000"):
            await self._notifications.notify(
                owner_id=owner_id,
                kind=NotificationKind.AI_BUDGET_ALERT,
                title="Alerte consommation IA",
                body=f"Votre consommation IA aujourd'hui s'élève à {depense:.4f} EUR.",
                payload={
                    "spent_today": float(depense),
                    "currency": await self._facts.ai_currency(owner_id),
                },
            )

    async def handle_daily_digest(self, job: ReservedJob) -> None:
        """Génère le résumé quotidien pour le propriétaire."""
        owner_id = job.owner_id
        if owner_id is None:
            return

        digest_service = DailyDigestService(
            facts=self._facts,
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
