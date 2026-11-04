"""Exécution en arrière-plan des tâches planifiées et des tâches de fond (EPIC 015).

Sans ce moteur, les tâches mises en file (planifiées ou déclenchées à la main) ne seraient jamais
exécutées. Il vit dans le processus de l'API (application locale mono-processus, ADR-0008/0009) :
- un « tic » met en file les tâches planifiées arrivées à échéance ;
- un worker consomme la file et exécute chaque tâche dans sa propre transaction.

Rien n'est lancé que l'utilisateur n'ait planifié ou déclenché lui-même, et le moteur se
désactive par `HAPPLY_WORKER_ENABLED=false`.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from app.core.database.session import UnitOfWork
from app.modules.notifications.application.orchestrator import AutomationJobHandlers
from app.modules.notifications.domain.enums import ScheduledTaskType
from app.modules.notifications.infrastructure.automation_facts import SqlAutomationFacts
from app.modules.notifications.infrastructure.composition import (
    build_notification_service,
    build_scheduler_service,
)
from app.modules.platform.application.worker import JobWorker
from app.modules.platform.infrastructure.job_queue import PostgresJobQueue, ReservedJob

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger("happly.runtime")


class AutomationRuntime:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        tick_seconds: float = 30.0,
        poll_seconds: float = 5.0,
    ) -> None:
        self._factory = session_factory
        self._queue = PostgresJobQueue(UnitOfWork(session_factory))
        self._tick = tick_seconds
        self._poll = poll_seconds
        self._stop = asyncio.Event()
        self._tasks: list[asyncio.Task[None]] = []

    # ------------------------------------------------------------ une exécution

    async def enqueue_due(self) -> int:
        """Met en file les tâches planifiées échues (une transaction, validée si tout réussit)."""
        async with self._factory() as session, session.begin():
            return await build_scheduler_service(session, self._factory).enqueue_due_tasks()

    def _handler(self, kind: str) -> Callable[[ReservedJob], Awaitable[None]]:
        async def executer(job: ReservedJob) -> None:
            # Une tâche = une transaction : un échec n'abîme pas les autres, il est rejoué.
            async with self._factory() as session, session.begin():
                handlers = AutomationJobHandlers(
                    facts=SqlAutomationFacts(session),
                    notification_service=build_notification_service(session),
                    job_queue=self._queue,
                )
                await handlers.as_handler_mapping()[kind](job)

        return executer

    def _worker(self) -> JobWorker:
        return JobWorker(
            self._queue,
            {t.value: self._handler(t.value) for t in ScheduledTaskType},
            worker_id=f"api-{uuid.uuid4().hex[:8]}",
            poll_interval=self._poll,
        )

    async def run_pending_once(self) -> int:
        """Exécute toutes les tâches prêtes (utile aux tests et à un arrêt propre)."""
        worker, faites = self._worker(), 0
        while await worker.run_once():
            faites += 1
        return faites

    # ------------------------------------------------------------ cycle de vie

    async def _boucle_planificateur(self) -> None:
        while not self._stop.is_set():
            try:
                await self.enqueue_due()
            except Exception:
                logger.exception("Échec de la mise en file des tâches planifiées")
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._stop.wait(), timeout=self._tick)

    async def _boucle_worker(self) -> None:
        try:
            await self._worker().run_forever(self._stop)
        except Exception:
            logger.exception("Le worker de tâches s'est arrêté sur une erreur")

    async def start(self) -> None:
        if self._tasks:
            return
        self._stop.clear()
        self._tasks = [
            asyncio.create_task(self._boucle_planificateur(), name="happly-scheduler-tick"),
            asyncio.create_task(self._boucle_worker(), name="happly-job-worker"),
        ]
        logger.info("Moteur d'automatisation démarré")

    async def stop(self, *, delai_max: float = 10.0) -> None:
        self._stop.set()
        if self._tasks:
            _, restantes = await asyncio.wait(self._tasks, timeout=delai_max)
            for tache in restantes:
                tache.cancel()
        self._tasks = []
        logger.info("Moteur d'automatisation arrêté")
