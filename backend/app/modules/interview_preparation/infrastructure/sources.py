"""Lecture SQL des sources d'une préparation : profil validé, candidature, offre analysée."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.application_management.domain.exceptions import ApplicationNotFoundError
from app.modules.application_management.infrastructure.models import ApplicationModel
from app.modules.candidate_profile.domain.profile import ProfileDocument
from app.modules.document_generation.application.ports import NoValidatedProfileError as _NoProfile
from app.modules.document_generation.infrastructure.generation_inputs import SqlGenerationInputs
from app.modules.interview_preparation.application.ports import ApplicationContext
from app.modules.interview_preparation.domain.exceptions import NoValidatedProfileError
from app.modules.interview_preparation.domain.models import OfferFacts


class SqlInterviewSources:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._inputs = SqlGenerationInputs(session)

    async def validated_profile(self, *, owner_id: uuid.UUID) -> ProfileDocument:
        try:
            return await self._inputs.validated_profile(owner_id=owner_id)
        except _NoProfile as erreur:
            raise NoValidatedProfileError(
                "Aucun profil validé : validez votre profil maître avant de préparer un entretien."
            ) from erreur

    async def application_context(
        self, *, owner_id: uuid.UUID, application_id: uuid.UUID
    ) -> ApplicationContext:
        candidature = await self._session.scalar(
            select(ApplicationModel).where(
                ApplicationModel.id == application_id, ApplicationModel.owner_id == owner_id
            )
        )
        if candidature is None:
            raise ApplicationNotFoundError("Candidature introuvable.")
        offre = await self._inputs.offer_context(owner_id=owner_id, offer_id=candidature.offer_id)
        return ApplicationContext(
            application_id=application_id,
            offer=OfferFacts(
                title=offre.title,
                company=offre.company,
                description=offre.description or "",
                required_skills=tuple(offre.required_skills),
            ),
            status=candidature.status,
            cv_version_id=candidature.cv_version_id,
        )
