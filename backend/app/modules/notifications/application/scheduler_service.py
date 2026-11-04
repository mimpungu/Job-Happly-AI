"""Service de gestion des plannings et d'ordonnancement des tâches de fond."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from app.modules.notifications.domain.entities import ScheduledTask
from app.modules.notifications.domain.enums import (
    ScheduledTaskType,
    ScheduleFrequency,
)
from app.modules.notifications.domain.exceptions import ScheduledTaskNotFoundError
from app.modules.notifications.domain.ports import ScheduledTaskRepositoryPort
from app.modules.notifications.domain.rules import (
    build_idempotency_key,
    compute_next_run,
    get_zone_info,
)
from app.modules.platform.infrastructure.job_queue import PostgresJobQueue

logger = logging.getLogger("happly.scheduler.service")


def _now() -> datetime:
    return datetime.now(UTC)


class SchedulerService:
    """Service applicatif pour planifier, ajuster et déclencher les tâches récurrentes."""

    def __init__(
        self,
        task_repo: ScheduledTaskRepositoryPort,
        job_queue: PostgresJobQueue,
        *,
        clock: Callable[[], datetime] = _now,
    ) -> None:
        self._task_repo = task_repo
        self._job_queue = job_queue
        self._clock = clock

    async def create_task(
        self,
        *,
        owner_id: uuid.UUID | None,
        task_type: ScheduledTaskType,
        frequency: ScheduleFrequency,
        interval_minutes: int | None = None,
        target_hour: int | None = None,
        target_minute: int | None = None,
        timezone: str = "Europe/Paris",
        payload: dict[str, Any] | None = None,
        enabled: bool = True,
        first_run_at: datetime | None = None,
    ) -> ScheduledTask:
        # Valide le fuseau horaire
        get_zone_info(timezone)

        maintenant = self._clock()
        next_run = first_run_at or compute_next_run(
            frequency,
            from_time=maintenant,
            tz_name=timezone,
            target_hour=target_hour,
            target_minute=target_minute,
            interval_minutes=interval_minutes,
        )

        return await self._task_repo.create(
            owner_id=owner_id,
            task_type=task_type,
            frequency=frequency,
            interval_minutes=interval_minutes,
            target_hour=target_hour,
            target_minute=target_minute,
            timezone=timezone,
            payload=payload,
            enabled=enabled,
            next_run_at=next_run,
        )

    async def get_task(
        self,
        *,
        task_id: uuid.UUID,
        owner_id: uuid.UUID | None = None,
    ) -> ScheduledTask:
        tache = await self._task_repo.get_by_id(task_id=task_id, owner_id=owner_id)
        if tache is None:
            raise ScheduledTaskNotFoundError(f"Tâche planifiée {task_id} introuvable.")
        return tache

    async def list_tasks(
        self,
        *,
        owner_id: uuid.UUID | None,
        enabled_only: bool = False,
    ) -> list[ScheduledTask]:
        return await self._task_repo.list_by_owner(owner_id=owner_id, enabled_only=enabled_only)

    async def update_task(
        self,
        *,
        task_id: uuid.UUID,
        owner_id: uuid.UUID | None = None,
        frequency: ScheduleFrequency | None = None,
        interval_minutes: int | None = None,
        target_hour: int | None = None,
        target_minute: int | None = None,
        timezone: str | None = None,
        payload: dict[str, Any] | None = None,
        enabled: bool | None = None,
    ) -> ScheduledTask:
        tache = await self.get_task(task_id=task_id, owner_id=owner_id)

        nouvelle_tz = timezone or tache.timezone
        get_zone_info(nouvelle_tz)

        nouvelle_freq = frequency or tache.frequency
        nouvel_intervalle = (
            interval_minutes if interval_minutes is not None else tache.interval_minutes
        )
        nouveau_h = target_hour if target_hour is not None else tache.target_hour
        nouveau_m = target_minute if target_minute is not None else tache.target_minute

        prochain_run = compute_next_run(
            nouvelle_freq,
            from_time=self._clock(),
            tz_name=nouvelle_tz,
            target_hour=nouveau_h,
            target_minute=nouveau_m,
            interval_minutes=nouvel_intervalle,
        )

        return await self._task_repo.update(
            task_id=task_id,
            owner_id=owner_id,
            frequency=nouvelle_freq,
            interval_minutes=nouvel_intervalle,
            target_hour=nouveau_h,
            target_minute=nouveau_m,
            timezone=nouvelle_tz,
            payload=payload,
            enabled=enabled,
            next_run_at=prochain_run,
        )

    async def delete_task(
        self,
        *,
        task_id: uuid.UUID,
        owner_id: uuid.UUID | None = None,
    ) -> bool:
        return await self._task_repo.delete(task_id=task_id, owner_id=owner_id)

    async def trigger_task_now(
        self,
        *,
        task_id: uuid.UUID,
        owner_id: uuid.UUID | None = None,
    ) -> uuid.UUID:
        """Déclenche immédiatement une exécution d'une tâche planifiée."""
        tache = await self.get_task(task_id=task_id, owner_id=owner_id)
        maintenant = self._clock()
        time_bucket = maintenant.strftime("%Y%m%d%H%M%S")
        cle_idempotence = build_idempotency_key(
            tache.task_type.value, str(tache.id), f"manual-{time_bucket}"
        )

        res = await self._job_queue.enqueue(
            kind=tache.task_type.value,
            idempotency_key=cle_idempotence,
            payload={**tache.payload, "task_id": str(tache.id), "manual": True},
            owner_id=tache.owner_id,
            run_at=maintenant,
        )
        return res.job_id

    async def enqueue_due_tasks(self) -> int:
        """Parcourt les tâches planifiées échues et les injecte dans la file de jobs."""
        maintenant = self._clock()
        taches_echues = await self._task_repo.list_due_tasks(as_of=maintenant)
        nb_enqueued = 0

        for tache in taches_echues:
            # Clé d'idempotence prévenant les doublons au sein du même intervalle
            time_bucket = tache.next_run_at.strftime("%Y%m%d%H%M")
            cle_idempotence = build_idempotency_key(
                tache.task_type.value, str(tache.id), time_bucket
            )

            res = await self._job_queue.enqueue(
                kind=tache.task_type.value,
                idempotency_key=cle_idempotence,
                payload={**tache.payload, "task_id": str(tache.id)},
                owner_id=tache.owner_id,
                run_at=maintenant,
            )
            if res.created:
                nb_enqueued += 1

            # Calcul et enregistrement de la prochaine échéance
            prochain_run = compute_next_run(
                tache.frequency,
                from_time=maintenant,
                tz_name=tache.timezone,
                target_hour=tache.target_hour,
                target_minute=tache.target_minute,
                interval_minutes=tache.interval_minutes,
            )
            await self._task_repo.update_run_status(
                task_id=tache.id,
                last_run_at=maintenant,
                next_run_at=prochain_run,
            )

        return nb_enqueued
