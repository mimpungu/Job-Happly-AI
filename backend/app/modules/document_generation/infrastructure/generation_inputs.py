"""Lecture SQL des données sources d'un document : profil validé et offre analysée."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.candidate_profile.domain.enums import ProfileStatus
from app.modules.candidate_profile.domain.profile import ProfileDocument
from app.modules.candidate_profile.infrastructure.models import CandidateProfileModel
from app.modules.candidate_profile.infrastructure.profile_repository import SqlProfileRepository
from app.modules.document_generation.application.ports import (
    NoValidatedProfileError,
    OfferContext,
    OfferNotFoundError,
)
from app.modules.job_discovery.infrastructure.models import JobOfferModel
from app.modules.job_intelligence.infrastructure.models import JobAnalysisModel

# Clés de l'analyse d'offre (job_intelligence), de la plus à la moins exigée.
_SKILL_KEYS = ("mandatory_skills", "expected_skills", "desired_skills", "technologies")


class SqlGenerationInputs:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def validated_profile(self, *, owner_id: uuid.UUID) -> ProfileDocument:
        version = await self._session.scalar(
            select(CandidateProfileModel.version)
            .where(
                CandidateProfileModel.owner_id == owner_id,
                CandidateProfileModel.status == ProfileStatus.VALIDATED.value,
            )
            .order_by(CandidateProfileModel.version.desc())
            .limit(1)
        )
        if version is None:
            raise NoValidatedProfileError
        stocke = await SqlProfileRepository(self._session).get_version(
            owner_id=owner_id, version=version
        )
        return stocke.document

    async def offer_context(self, *, owner_id: uuid.UUID, offer_id: uuid.UUID) -> OfferContext:
        offre = await self._session.scalar(
            select(JobOfferModel).where(
                JobOfferModel.id == offer_id, JobOfferModel.owner_id == owner_id
            )
        )
        if offre is None:
            raise OfferNotFoundError(str(offer_id))

        analyse = await self._session.scalar(
            select(JobAnalysisModel)
            .where(JobAnalysisModel.offer_id == offer_id, JobAnalysisModel.owner_id == owner_id)
            .order_by(JobAnalysisModel.created_at.desc())
            .limit(1)
        )
        competences: list[str] = []
        if analyse is not None and isinstance(analyse.result, dict):
            for cle in _SKILL_KEYS:
                valeurs = analyse.result.get(cle)
                if isinstance(valeurs, list):
                    competences.extend(str(v) for v in valeurs if str(v).strip())
        return OfferContext(
            title=offre.title,
            company=offre.company_name,
            description=offre.description,
            required_skills=tuple(dict.fromkeys(competences)),
            location=offre.location,
            country_code=offre.country_code,
        )
