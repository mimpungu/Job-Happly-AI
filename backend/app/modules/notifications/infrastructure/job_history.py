"""Historique d'exécution des tâches de fond (TASK-015-10) : lecture de la table `jobs`."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.platform.infrastructure.models import JobModel


async def list_job_history(
    session: AsyncSession,
    *,
    owner_id: uuid.UUID | None = None,
    status: str | None = None,
    kind: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    criteres = []
    if owner_id is not None:
        criteres.append(JobModel.owner_id == owner_id)
    if status is not None:
        criteres.append(JobModel.status == status)
    if kind is not None:
        criteres.append(JobModel.kind == kind)

    total = (await session.scalar(select(func.count(JobModel.id)).where(*criteres))) or 0
    jobs = (
        await session.scalars(
            select(JobModel)
            .where(*criteres)
            .order_by(JobModel.created_at.desc(), JobModel.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
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
