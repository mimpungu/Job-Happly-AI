"""Persistance des analyses d'offres (table `job_analyses`). Ne valide jamais la transaction."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.job_intelligence.application.analysis_service import (
    RULES_MODEL,
    StoredAnalysis,
)
from app.modules.job_intelligence.domain.analysis.models import ANALYSIS_VERSION
from app.modules.job_intelligence.domain.enums import AnalysisKind
from app.modules.job_intelligence.infrastructure.models import JobAnalysisModel


def _vue(ligne: JobAnalysisModel, *, reused: bool) -> StoredAnalysis:
    return StoredAnalysis(ligne.id, ligne.content_hash, ligne.result, ligne.created_at, reused)


class SqlAnalysisStore:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _cle(self, owner_id: uuid.UUID, offer_id: uuid.UUID) -> list[Any]:
        return [
            JobAnalysisModel.owner_id == owner_id,
            JobAnalysisModel.offer_id == offer_id,
            JobAnalysisModel.kind == AnalysisKind.REQUIREMENTS.value,
            JobAnalysisModel.prompt_version == ANALYSIS_VERSION,
            JobAnalysisModel.model == RULES_MODEL,
        ]

    async def get_or_create(
        self,
        *,
        owner_id: uuid.UUID,
        offer_id: uuid.UUID,
        content_hash: str,
        result: dict[str, Any],
    ) -> StoredAnalysis:
        existante = await self._session.scalar(
            select(JobAnalysisModel).where(
                *self._cle(owner_id, offer_id), JobAnalysisModel.content_hash == content_hash
            )
        )
        if existante is not None:
            return _vue(existante, reused=True)
        # Insertion idempotente : deux demandes simultanées ne créent qu'une ligne.
        await self._session.execute(
            pg_insert(JobAnalysisModel)
            .values(
                owner_id=owner_id,
                offer_id=offer_id,
                kind=AnalysisKind.REQUIREMENTS.value,
                prompt_version=ANALYSIS_VERSION,
                model=RULES_MODEL,
                content_hash=content_hash,
                result=result,
                # Horodatage par l'application (microsecondes) : l'ordre de l'historique ne dépend
                # pas de l'horloge de transaction de la base, identique pour tout un lot.
                created_at=datetime.now(UTC),
            )
            .on_conflict_do_nothing()
        )
        ligne = await self._session.scalar(
            select(JobAnalysisModel).where(
                *self._cle(owner_id, offer_id), JobAnalysisModel.content_hash == content_hash
            )
        )
        assert ligne is not None  # noqa: S101 - inséré juste avant, dans la même transaction
        return _vue(ligne, reused=False)

    async def history(self, *, owner_id: uuid.UUID, offer_id: uuid.UUID) -> list[StoredAnalysis]:
        lignes = await self._session.scalars(
            select(JobAnalysisModel)
            .where(
                JobAnalysisModel.owner_id == owner_id,
                JobAnalysisModel.offer_id == offer_id,
                JobAnalysisModel.kind == AnalysisKind.REQUIREMENTS.value,
            )
            .order_by(JobAnalysisModel.created_at.desc(), JobAnalysisModel.id)
        )
        return [_vue(ligne, reused=True) for ligne in lignes]
