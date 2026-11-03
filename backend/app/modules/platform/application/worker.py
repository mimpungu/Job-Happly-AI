"""Worker de tâches de fond : exécute les tâches réservées avec leurs gestionnaires."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping
from datetime import timedelta

from app.modules.platform.infrastructure.job_queue import PostgresJobQueue, ReservedJob

logger = logging.getLogger("happly.worker")

Handler = Callable[[ReservedJob], Awaitable[None]]


class NonRetryableJobError(Exception):
    """Échec définitif : rejouer la tâche ne servirait à rien."""


def backoff(attempts: int, *, base: float = 30.0, maximum: float = 3600.0) -> timedelta:
    """Attente avant la tentative suivante : exponentielle, plafonnée."""
    return timedelta(seconds=min(base * (2 ** max(attempts - 1, 0)), maximum))


class JobWorker:
    def __init__(
        self,
        queue: PostgresJobQueue,
        handlers: Mapping[str, Handler],
        *,
        worker_id: str,
        poll_interval: float = 2.0,
        lock_timeout: timedelta = timedelta(minutes=15),
    ) -> None:
        self._queue = queue
        self._handlers = dict(handlers)
        self._worker_id = worker_id
        self._poll_interval = poll_interval
        self._lock_timeout = lock_timeout

    async def run_once(self) -> bool:
        """Traite au plus une tâche. Retourne `True` si une tâche a été exécutée."""
        job = await self._queue.reserve(worker_id=self._worker_id)
        if job is None:
            return False
        handler = self._handlers.get(job.kind)
        if handler is None:
            await self._queue.fail(
                job.id, error=f"Aucun gestionnaire pour '{job.kind}'.", retry_delay=None
            )
            logger.error("Tâche sans gestionnaire", extra={"kind": job.kind, "job_id": str(job.id)})
            return True
        try:
            await handler(job)
        except NonRetryableJobError as erreur:
            await self._queue.fail(job.id, error=str(erreur), retry_delay=None)
            logger.warning(
                "Tâche en échec définitif", extra={"kind": job.kind, "job_id": str(job.id)}
            )
        except Exception as erreur:
            # Jamais avalée : journalisée avec son type, puis rejouée ou déclarée morte.
            etat = await self._queue.fail(
                job.id,
                error=f"{type(erreur).__name__}: {erreur}",
                retry_delay=backoff(job.attempts),
            )
            logger.exception(
                "Échec de tâche",
                extra={
                    "kind": job.kind,
                    "job_id": str(job.id),
                    "attempt": job.attempts,
                    "next": etat.value,
                },
            )
        else:
            await self._queue.complete(job.id)
        return True

    async def run_forever(self, stop: asyncio.Event) -> None:
        """Boucle du worker : reprend d'abord les tâches orphelines, puis traite la file."""
        await self._queue.recover_stale(lock_timeout=self._lock_timeout)
        while not stop.is_set():
            if not await self.run_once():
                try:
                    await asyncio.wait_for(stop.wait(), timeout=self._poll_interval)
                except TimeoutError:
                    continue
