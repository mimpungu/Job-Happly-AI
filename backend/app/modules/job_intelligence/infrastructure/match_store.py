"""Persistance des scores et des pondérations personnalisées."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import delete, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.job_intelligence.application.ports import ScoreRecord
from app.modules.job_intelligence.infrastructure.models import (
    JobMatchScoreModel,
    MatchingSettingsModel,
)


class SqlMatchStore:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_weights(self, *, owner_id: uuid.UUID) -> dict[str, Any]:
        valeurs = await self._session.scalar(
            select(MatchingSettingsModel.weights).where(MatchingSettingsModel.owner_id == owner_id)
        )
        return dict(valeurs or {})

    async def set_weights(
        self, *, owner_id: uuid.UUID, weights: dict[str, Any], now: datetime
    ) -> None:
        instruction = insert(MatchingSettingsModel).values(
            owner_id=owner_id, weights=weights, updated_at=now
        )
        await self._session.execute(
            instruction.on_conflict_do_update(
                index_elements=["owner_id"], set_={"weights": weights, "updated_at": now}
            )
        )

    async def clear_weights(self, *, owner_id: uuid.UUID) -> None:
        await self._session.execute(
            delete(MatchingSettingsModel).where(MatchingSettingsModel.owner_id == owner_id)
        )

    async def save_scores(
        self,
        *,
        owner_id: uuid.UUID,
        profile_id: uuid.UUID,
        records: list[ScoreRecord],
        now: datetime,
    ) -> None:
        if not records:
            return
        instruction = insert(JobMatchScoreModel).values(
            [
                {
                    "owner_id": owner_id,
                    "offer_id": r.offer_id,
                    "profile_id": profile_id,
                    "score": r.score,
                    "breakdown": r.breakdown,
                    "weights_version": r.weights_version,
                    "computed_at": now,
                }
                for r in records
            ]
        )
        # Idempotent : recalculer remplace le score existant (même offre, profil, poids).
        await self._session.execute(
            instruction.on_conflict_do_update(
                index_elements=["offer_id", "profile_id", "weights_version"],
                set_={
                    "score": instruction.excluded.score,
                    "breakdown": instruction.excluded.breakdown,
                    "computed_at": instruction.excluded.computed_at,
                },
            )
        )

    async def prune_scores(
        self, *, owner_id: uuid.UUID, profile_id: uuid.UUID, weights_version: str
    ) -> int:
        resultat = await self._session.execute(
            delete(JobMatchScoreModel).where(
                JobMatchScoreModel.owner_id == owner_id,
                or_(
                    JobMatchScoreModel.profile_id != profile_id,
                    JobMatchScoreModel.weights_version != weights_version,
                ),
            )
        )
        return int(getattr(resultat, "rowcount", 0) or 0)
