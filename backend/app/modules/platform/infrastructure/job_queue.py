"""File de tâches adossée à PostgreSQL (ADR-0009).

- Réservation par `SELECT … FOR UPDATE SKIP LOCKED` : plusieurs workers ne prennent jamais la
  même tâche.
- Idempotence : une seule tâche active (en attente ou en cours) par (type, clé d'idempotence).
- Reprise : une tâche « en cours » dont le verrou a expiré (worker mort) est remise en attente.
- Nouvelles tentatives avec attente croissante ; au-delà du maximum la tâche est « morte »
  et reste consultable (jamais supprimée silencieusement).

Chaque opération ouvre sa propre transaction : l'état est visible immédiatement des autres workers.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from app.core.database.session import UnitOfWork
from app.modules.platform.infrastructure.models import JobModel, JobStatus

MAX_ERROR_LENGTH = 500


@dataclass(frozen=True, slots=True)
class ReservedJob:
    id: uuid.UUID
    kind: str
    payload: dict[str, Any]
    owner_id: uuid.UUID | None
    attempts: int
    max_attempts: int


@dataclass(frozen=True, slots=True)
class EnqueueResult:
    job_id: uuid.UUID
    created: bool
    """Faux si une tâche active équivalente existait déjà (aucun doublon n'est créé)."""


class PostgresJobQueue:
    def __init__(
        self,
        uow: UnitOfWork,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._uow = uow
        self._clock = clock

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
        if max_attempts < 1:
            raise ValueError("max_attempts doit être strictement positif.")
        async with self._uow.begin() as session:
            insertion = (
                insert(JobModel)
                .values(
                    kind=kind,
                    idempotency_key=idempotency_key,
                    payload=payload or {},
                    owner_id=owner_id,
                    run_at=run_at or self._clock(),
                    max_attempts=max_attempts,
                )
                .on_conflict_do_nothing(
                    index_elements=["kind", "idempotency_key"],
                    index_where=JobModel.status.in_(
                        [JobStatus.QUEUED.value, JobStatus.RUNNING.value]
                    ),
                )
                .returning(JobModel.id)
            )
            cree = (await session.execute(insertion)).scalar_one_or_none()
            if cree is not None:
                return EnqueueResult(job_id=cree, created=True)
            existant = await session.scalar(
                select(JobModel.id).where(
                    JobModel.kind == kind,
                    JobModel.idempotency_key == idempotency_key,
                    JobModel.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value]),
                )
            )
            if existant is None:  # pragma: no cover - terminée entre les deux requêtes
                raise RuntimeError("Tâche active introuvable après conflit d'idempotence.")
            return EnqueueResult(job_id=existant, created=False)

    async def reserve(self, *, worker_id: str) -> ReservedJob | None:
        """Réserve la plus ancienne tâche prête, ou `None` s'il n'y en a pas."""
        maintenant = self._clock()
        async with self._uow.begin() as session:
            prochaine = (
                select(JobModel.id)
                .where(JobModel.status == JobStatus.QUEUED.value, JobModel.run_at <= maintenant)
                .order_by(JobModel.run_at, JobModel.created_at)
                .limit(1)
                .with_for_update(skip_locked=True)
                .scalar_subquery()
            )
            ligne = (
                await session.execute(
                    update(JobModel)
                    .where(JobModel.id == prochaine)
                    .values(
                        status=JobStatus.RUNNING.value,
                        attempts=JobModel.attempts + 1,
                        locked_at=maintenant,
                        locked_by=worker_id,
                    )
                    .returning(
                        JobModel.id,
                        JobModel.kind,
                        JobModel.payload,
                        JobModel.owner_id,
                        JobModel.attempts,
                        JobModel.max_attempts,
                    )
                )
            ).first()
        if ligne is None:
            return None
        return ReservedJob(
            id=ligne.id,
            kind=ligne.kind,
            payload=ligne.payload,
            owner_id=ligne.owner_id,
            attempts=ligne.attempts,
            max_attempts=ligne.max_attempts,
        )

    async def complete(self, job_id: uuid.UUID) -> None:
        async with self._uow.begin() as session:
            await session.execute(
                update(JobModel)
                .where(JobModel.id == job_id, JobModel.status == JobStatus.RUNNING.value)
                .values(
                    status=JobStatus.SUCCEEDED.value,
                    finished_at=self._clock(),
                    locked_at=None,
                    locked_by=None,
                    last_error=None,
                )
            )

    async def fail(
        self,
        job_id: uuid.UUID,
        *,
        error: str,
        retry_delay: timedelta | None,
    ) -> JobStatus:
        """Échec d'une tâche. `retry_delay=None` : échec définitif (non rejouable).

        Retourne le nouvel état : `QUEUED` (sera rejouée), `DEAD` (tentatives épuisées)
        ou `FAILED` (échec définitif demandé).
        """
        maintenant = self._clock()
        message = error[:MAX_ERROR_LENGTH]
        async with self._uow.begin() as session:
            job = (
                await session.execute(
                    select(JobModel).where(JobModel.id == job_id).with_for_update()
                )
            ).scalar_one()
            if job.status != JobStatus.RUNNING.value:
                return JobStatus(job.status)
            job.last_error = message
            job.locked_at = None
            job.locked_by = None
            if retry_delay is None:
                job.status = JobStatus.FAILED.value
                job.finished_at = maintenant
            elif job.attempts >= job.max_attempts:
                job.status = JobStatus.DEAD.value
                job.finished_at = maintenant
            else:
                job.status = JobStatus.QUEUED.value
                job.run_at = maintenant + retry_delay
            return JobStatus(job.status)

    async def recover_stale(self, *, lock_timeout: timedelta) -> int:
        """Remet en attente les tâches dont le worker a disparu (verrou expiré)."""
        maintenant = self._clock()
        async with self._uow.begin() as session:
            perimees = (
                (
                    await session.execute(
                        select(JobModel)
                        .where(
                            JobModel.status == JobStatus.RUNNING.value,
                            JobModel.locked_at < maintenant - lock_timeout,
                        )
                        .with_for_update(skip_locked=True)
                    )
                )
                .scalars()
                .all()
            )
            for job in perimees:
                job.locked_at = None
                job.locked_by = None
                job.last_error = "Verrou expiré : worker interrompu."
                if job.attempts >= job.max_attempts:
                    job.status = JobStatus.DEAD.value
                    job.finished_at = maintenant
                else:
                    job.status = JobStatus.QUEUED.value
                    job.run_at = maintenant
            return len(perimees)
