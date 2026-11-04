"""Tests unitaires du service de planification (SchedulerService)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.modules.notifications.application.scheduler_service import SchedulerService
from app.modules.notifications.domain.entities import ScheduledTask
from app.modules.notifications.domain.enums import (
    ScheduledTaskType,
    ScheduleFrequency,
)
from app.modules.notifications.domain.exceptions import (
    InvalidTimezoneError,
    ScheduledTaskNotFoundError,
)
from app.modules.notifications.domain.ports import ScheduledTaskRepositoryPort
from app.modules.platform.infrastructure.job_queue import EnqueueResult

T0 = datetime(2026, 11, 4, 10, 0, 0, tzinfo=UTC)


class InMemoryTaskRepository(ScheduledTaskRepositoryPort):
    def __init__(self) -> None:
        self._tasks: dict[uuid.UUID, ScheduledTask] = {}

    async def create(
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
        next_run_at: datetime,
    ) -> ScheduledTask:
        task_id = uuid.uuid4()
        task = ScheduledTask(
            id=task_id,
            owner_id=owner_id,
            task_type=task_type,
            frequency=frequency,
            interval_minutes=interval_minutes,
            target_hour=target_hour,
            target_minute=target_minute,
            timezone=timezone,
            payload=payload or {},
            enabled=enabled,
            last_run_at=None,
            next_run_at=next_run_at,
            created_at=T0,
            updated_at=T0,
        )
        self._tasks[task_id] = task
        return task

    async def get_by_id(
        self,
        *,
        task_id: uuid.UUID,
        owner_id: uuid.UUID | None = None,
    ) -> ScheduledTask | None:
        task = self._tasks.get(task_id)
        if task and (owner_id is None or task.owner_id == owner_id):
            return task
        return None

    async def list_by_owner(
        self,
        *,
        owner_id: uuid.UUID | None,
        enabled_only: bool = False,
    ) -> list[ScheduledTask]:
        res = [t for t in self._tasks.values() if owner_id is None or t.owner_id == owner_id]
        if enabled_only:
            res = [t for t in res if t.enabled]
        return res

    async def list_due_tasks(self, *, as_of: datetime) -> list[ScheduledTask]:
        return [t for t in self._tasks.values() if t.enabled and t.next_run_at <= as_of]

    async def update_run_status(
        self,
        *,
        task_id: uuid.UUID,
        last_run_at: datetime,
        next_run_at: datetime,
    ) -> ScheduledTask:
        task = self._tasks[task_id]
        updated = ScheduledTask(
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
            last_run_at=last_run_at,
            next_run_at=next_run_at,
            created_at=task.created_at,
            updated_at=T0,
        )
        self._tasks[task_id] = updated
        return updated

    async def update(
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
        next_run_at: datetime | None = None,
    ) -> ScheduledTask:
        task = self._tasks.get(task_id)
        if task is None or (owner_id is not None and task.owner_id != owner_id):
            raise ScheduledTaskNotFoundError("Tâche introuvable.")
        updated = ScheduledTask(
            id=task.id,
            owner_id=task.owner_id,
            task_type=task.task_type,
            frequency=frequency or task.frequency,
            interval_minutes=(
                interval_minutes if interval_minutes is not None else task.interval_minutes
            ),
            target_hour=target_hour if target_hour is not None else task.target_hour,
            target_minute=target_minute if target_minute is not None else task.target_minute,
            timezone=timezone or task.timezone,
            payload=payload if payload is not None else task.payload,
            enabled=enabled if enabled is not None else task.enabled,
            last_run_at=task.last_run_at,
            next_run_at=next_run_at or task.next_run_at,
            created_at=task.created_at,
            updated_at=T0,
        )
        self._tasks[task_id] = updated
        return updated

    async def delete(
        self,
        *,
        task_id: uuid.UUID,
        owner_id: uuid.UUID | None = None,
    ) -> bool:
        task = self._tasks.get(task_id)
        if task and (owner_id is None or task.owner_id == owner_id):
            del self._tasks[task_id]
            return True
        return False


class FakeJobQueue:
    def __init__(self) -> None:
        self.enqueued: list[dict[str, Any]] = []

    async def enqueue(
        self,
        *,
        kind: str,
        idempotency_key: str,
        payload: dict[str, Any] | None = None,
        owner_id: uuid.UUID | None = None,
        run_at: datetime | None = None,
        max_attempts: int = 3,
    ) -> EnqueueResult:
        # Vérification d'idempotence
        for e in self.enqueued:
            if e["kind"] == kind and e["idempotency_key"] == idempotency_key:
                return EnqueueResult(job_id=e["job_id"], created=False)

        job_id = uuid.uuid4()
        self.enqueued.append(
            {
                "job_id": job_id,
                "kind": kind,
                "idempotency_key": idempotency_key,
                "payload": payload or {},
                "owner_id": owner_id,
                "run_at": run_at,
            }
        )
        return EnqueueResult(job_id=job_id, created=True)


class TestSchedulerService:
    @pytest.fixture
    def owner_id(self) -> uuid.UUID:
        return uuid.uuid4()

    @pytest.fixture
    def repo(self) -> InMemoryTaskRepository:
        return InMemoryTaskRepository()

    @pytest.fixture
    def queue(self) -> FakeJobQueue:
        return FakeJobQueue()

    @pytest.fixture
    def service(self, repo: InMemoryTaskRepository, queue: FakeJobQueue) -> SchedulerService:
        return SchedulerService(
            task_repo=repo,
            job_queue=queue,  # type: ignore[arg-type]
            clock=lambda: T0,
        )

    async def test_cree_tache_avec_calcul_prochaine_echeance(
        self,
        service: SchedulerService,
        owner_id: uuid.UUID,
    ) -> None:
        tache = await service.create_task(
            owner_id=owner_id,
            task_type=ScheduledTaskType.RECURRING_SEARCH,
            frequency=ScheduleFrequency.HOURLY,
            timezone="Europe/Paris",
            payload={"saved_search_id": "test-123"},
        )
        assert tache.task_type == ScheduledTaskType.RECURRING_SEARCH
        assert tache.frequency == ScheduleFrequency.HOURLY
        assert tache.enabled is True
        assert tache.next_run_at == T0 + timedelta(hours=1)

    async def test_rejette_timezone_inconnue(
        self,
        service: SchedulerService,
        owner_id: uuid.UUID,
    ) -> None:
        with pytest.raises(InvalidTimezoneError):
            await service.create_task(
                owner_id=owner_id,
                task_type=ScheduledTaskType.DAILY_DIGEST,
                frequency=ScheduleFrequency.DAILY,
                timezone="Invalide/Zone",
            )

    async def test_enqueue_due_tasks_planifie_dans_file_et_avance_echeance(
        self,
        service: SchedulerService,
        repo: InMemoryTaskRepository,
        queue: FakeJobQueue,
        owner_id: uuid.UUID,
    ) -> None:
        # Tâche dont next_run_at est déjà échu (T0 - 5 minutes)
        tache = await service.create_task(
            owner_id=owner_id,
            task_type=ScheduledTaskType.FOLLOW_UP_CHECK,
            frequency=ScheduleFrequency.EVERY_6_HOURS,
            first_run_at=T0 - timedelta(minutes=5),
        )

        assert len(queue.enqueued) == 0

        nb = await service.enqueue_due_tasks()
        assert nb == 1
        assert len(queue.enqueued) == 1
        assert queue.enqueued[0]["kind"] == ScheduledTaskType.FOLLOW_UP_CHECK.value

        # La tâche a avancé de 6 heures à partir de T0
        rechargee = await repo.get_by_id(task_id=tache.id)
        assert rechargee is not None
        assert rechargee.last_run_at == T0
        assert rechargee.next_run_at == T0 + timedelta(hours=6)

    async def test_trigger_task_now_insere_immediatement_dans_file(
        self,
        service: SchedulerService,
        queue: FakeJobQueue,
        owner_id: uuid.UUID,
    ) -> None:
        tache = await service.create_task(
            owner_id=owner_id,
            task_type=ScheduledTaskType.RECURRING_SEARCH,
            frequency=ScheduleFrequency.DAILY,
        )

        job_id = await service.trigger_task_now(task_id=tache.id, owner_id=owner_id)
        assert len(queue.enqueued) == 1
        assert queue.enqueued[0]["job_id"] == job_id
        assert queue.enqueued[0]["payload"]["manual"] is True
