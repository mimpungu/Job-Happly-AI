"""Implémentation SQLAlchemy du repository des tâches planifiées."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.domain.entities import ScheduledTask
from app.modules.notifications.domain.enums import ScheduledTaskType, ScheduleFrequency
from app.modules.notifications.domain.exceptions import ScheduledTaskNotFoundError
from app.modules.notifications.domain.ports import ScheduledTaskRepositoryPort
from app.modules.notifications.infrastructure.models import ScheduledTaskModel


def _to_entity(model: ScheduledTaskModel) -> ScheduledTask:
    return ScheduledTask(
        id=model.id,
        owner_id=model.owner_id,
        task_type=ScheduledTaskType(model.task_type),
        frequency=ScheduleFrequency(model.frequency),
        interval_minutes=model.interval_minutes,
        target_hour=model.target_hour,
        target_minute=model.target_minute,
        timezone=model.timezone,
        payload=dict(model.payload or {}),
        enabled=model.enabled,
        last_run_at=model.last_run_at,
        next_run_at=model.next_run_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SQLAlchemyScheduledTaskRepository(ScheduledTaskRepositoryPort):
    """Repository persistant pour les tâches récurrentes du planificateur."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

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
        model = ScheduledTaskModel(
            owner_id=owner_id,
            task_type=task_type.value,
            frequency=frequency.value,
            interval_minutes=interval_minutes,
            target_hour=target_hour,
            target_minute=target_minute,
            timezone=timezone,
            payload=payload or {},
            enabled=enabled,
            next_run_at=next_run_at,
        )
        self._session.add(model)
        await self._session.flush()
        return _to_entity(model)

    async def get_by_id(
        self,
        *,
        task_id: uuid.UUID,
        owner_id: uuid.UUID | None = None,
    ) -> ScheduledTask | None:
        critères = [ScheduledTaskModel.id == task_id]
        if owner_id is not None:
            critères.append(ScheduledTaskModel.owner_id == owner_id)
        stmt = select(ScheduledTaskModel).where(*critères)
        model = await self._session.scalar(stmt)
        return _to_entity(model) if model is not None else None

    async def list_by_owner(
        self,
        *,
        owner_id: uuid.UUID | None,
        enabled_only: bool = False,
    ) -> list[ScheduledTask]:
        critères = []
        if owner_id is not None:
            critères.append(ScheduledTaskModel.owner_id == owner_id)
        if enabled_only:
            critères.append(ScheduledTaskModel.enabled.is_(True))

        stmt = (
            select(ScheduledTaskModel)
            .where(*critères)
            .order_by(ScheduledTaskModel.next_run_at.asc())
        )
        models = (await self._session.scalars(stmt)).all()
        return [_to_entity(m) for m in models]

    async def list_due_tasks(
        self,
        *,
        as_of: datetime,
    ) -> list[ScheduledTask]:
        stmt = (
            select(ScheduledTaskModel)
            .where(
                ScheduledTaskModel.enabled.is_(True),
                ScheduledTaskModel.next_run_at <= as_of,
            )
            .order_by(ScheduledTaskModel.next_run_at.asc())
        )
        models = (await self._session.scalars(stmt)).all()
        return [_to_entity(m) for m in models]

    async def update_run_status(
        self,
        *,
        task_id: uuid.UUID,
        last_run_at: datetime,
        next_run_at: datetime,
    ) -> ScheduledTask:
        stmt = select(ScheduledTaskModel).where(ScheduledTaskModel.id == task_id)
        model = await self._session.scalar(stmt)
        if model is None:
            raise ScheduledTaskNotFoundError(f"Tâche planifiée {task_id} introuvable.")
        model.last_run_at = last_run_at
        model.next_run_at = next_run_at
        await self._session.flush()
        return _to_entity(model)

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
        critères = [ScheduledTaskModel.id == task_id]
        if owner_id is not None:
            critères.append(ScheduledTaskModel.owner_id == owner_id)
        stmt = select(ScheduledTaskModel).where(*critères)
        model = await self._session.scalar(stmt)
        if model is None:
            raise ScheduledTaskNotFoundError(f"Tâche planifiée {task_id} introuvable.")

        if frequency is not None:
            model.frequency = frequency.value
        if interval_minutes is not None:
            model.interval_minutes = interval_minutes
        if target_hour is not None:
            model.target_hour = target_hour
        if target_minute is not None:
            model.target_minute = target_minute
        if timezone is not None:
            model.timezone = timezone
        if payload is not None:
            model.payload = payload
        if enabled is not None:
            model.enabled = enabled
        if next_run_at is not None:
            model.next_run_at = next_run_at

        await self._session.flush()
        return _to_entity(model)

    async def delete(
        self,
        *,
        task_id: uuid.UUID,
        owner_id: uuid.UUID | None = None,
    ) -> bool:
        critères = [ScheduledTaskModel.id == task_id]
        if owner_id is not None:
            critères.append(ScheduledTaskModel.owner_id == owner_id)
        stmt = select(ScheduledTaskModel).where(*critères)
        model = await self._session.scalar(stmt)
        if model is None:
            return False
        await self._session.delete(model)
        await self._session.flush()
        return True
