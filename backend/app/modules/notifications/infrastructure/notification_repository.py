"""Implémentation SQLAlchemy du repository des notifications."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.domain.entities import Notification
from app.modules.notifications.domain.enums import NotificationKind
from app.modules.notifications.domain.exceptions import NotificationNotFoundError
from app.modules.notifications.domain.ports import NotificationRepositoryPort
from app.modules.notifications.infrastructure.models import NotificationModel


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _to_entity(model: NotificationModel) -> Notification:
    return Notification(
        id=model.id,
        owner_id=model.owner_id,
        kind=NotificationKind(model.kind),
        title=model.title,
        body=model.body,
        payload=dict(model.payload or {}),
        read_at=model.read_at,
        created_at=model.created_at,
    )


class SQLAlchemyNotificationRepository(NotificationRepositoryPort):
    """Repository persistant pour la gestion des notifications utilisateur."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        clock: Callable[[], datetime] = _now_utc,
    ) -> None:
        self._session = session
        self._clock = clock

    async def create(
        self,
        *,
        owner_id: uuid.UUID,
        kind: NotificationKind,
        title: str,
        body: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> Notification:
        modele = NotificationModel(
            owner_id=owner_id,
            kind=kind.value,
            title=title,
            body=body,
            payload=payload or {},
            created_at=self._clock(),
        )
        self._session.add(modele)
        await self._session.flush()
        return _to_entity(modele)

    async def get_by_id(
        self,
        *,
        owner_id: uuid.UUID,
        notification_id: uuid.UUID,
    ) -> Notification | None:
        requete = select(NotificationModel).where(
            NotificationModel.id == notification_id,
            NotificationModel.owner_id == owner_id,
        )
        resultat = await self._session.scalar(requete)
        return _to_entity(resultat) if resultat is not None else None

    async def list(
        self,
        *,
        owner_id: uuid.UUID,
        unread_only: bool = False,
        kind: NotificationKind | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Notification], int]:
        criteres = [NotificationModel.owner_id == owner_id]
        if unread_only:
            criteres.append(NotificationModel.read_at.is_(None))
        if kind is not None:
            criteres.append(NotificationModel.kind == kind.value)

        # Comptage total
        total_stmt = select(func.count(NotificationModel.id)).where(*criteres)
        total = (await self._session.scalar(total_stmt)) or 0

        # Liste paginée ordonnée de la plus récente à la plus ancienne
        lignes_stmt = (
            select(NotificationModel)
            .where(*criteres)
            .order_by(NotificationModel.created_at.desc(), NotificationModel.id.desc())
            .limit(limit)
            .offset(offset)
        )
        resultats = (await self._session.scalars(lignes_stmt)).all()
        return [_to_entity(m) for m in resultats], total

    async def count_unread(self, *, owner_id: uuid.UUID) -> int:
        stmt = select(func.count(NotificationModel.id)).where(
            NotificationModel.owner_id == owner_id,
            NotificationModel.read_at.is_(None),
        )
        return (await self._session.scalar(stmt)) or 0

    async def mark_as_read(
        self,
        *,
        owner_id: uuid.UUID,
        notification_id: uuid.UUID,
        read_at: datetime | None = None,
    ) -> Notification:
        maintenant = read_at or self._clock()
        stmt = (
            update(NotificationModel)
            .where(
                NotificationModel.id == notification_id,
                NotificationModel.owner_id == owner_id,
            )
            .values(read_at=maintenant)
            .returning(NotificationModel)
        )
        resultat = await self._session.scalar(stmt)
        if resultat is None:
            raise NotificationNotFoundError(
                f"Notification {notification_id} introuvable pour ce propriétaire."
            )
        return _to_entity(resultat)

    async def mark_all_as_read(
        self,
        *,
        owner_id: uuid.UUID,
        read_at: datetime | None = None,
    ) -> int:
        maintenant = read_at or self._clock()
        stmt = (
            update(NotificationModel)
            .where(
                NotificationModel.owner_id == owner_id,
                NotificationModel.read_at.is_(None),
            )
            .values(read_at=maintenant)
            .returning(NotificationModel.id)
        )
        resultats = (await self._session.scalars(stmt)).all()
        return len(resultats)

    async def delete(
        self,
        *,
        owner_id: uuid.UUID,
        notification_id: uuid.UUID,
    ) -> bool:
        modele = await self._session.get(NotificationModel, notification_id)
        if modele is None or modele.owner_id != owner_id:
            return False
        await self._session.delete(modele)
        await self._session.flush()
        return True
