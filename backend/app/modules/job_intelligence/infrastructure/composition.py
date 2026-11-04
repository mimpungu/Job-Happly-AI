"""Assemblage du service de scoring avec ses adaptateurs SQL (utilisé par les routes)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.job_intelligence.application.matching_service import MatchingService
from app.modules.job_intelligence.infrastructure.match_store import SqlMatchStore
from app.modules.job_intelligence.infrastructure.readers import (
    SqlCandidateFactsReader,
    SqlJobOfferReader,
)


def build_matching_service(session: AsyncSession) -> MatchingService:
    return MatchingService(
        SqlCandidateFactsReader(session), SqlJobOfferReader(session), SqlMatchStore(session)
    )
