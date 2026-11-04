"""Adaptateurs de lecture dans les autres modules (CandidateFactsReader, JobOfferReader)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.candidate_profile.domain.enums import ProfileStatus
from app.modules.candidate_profile.domain.profile import DocDate, ProfileDocument
from app.modules.candidate_profile.infrastructure.models import CandidateProfileModel
from app.modules.candidate_profile.infrastructure.profile_repository import SqlProfileRepository
from app.modules.job_discovery.domain.enums import OfferStatus
from app.modules.job_discovery.domain.search import OfferNotFoundError
from app.modules.job_discovery.infrastructure.models import JobOfferModel
from app.modules.job_intelligence.application.ports import ProfileSnapshot
from app.modules.job_intelligence.domain.matching.models import (
    ExperiencePeriod,
    OfferFacts,
    ProfileFacts,
    YearMonth,
)


def _annee_mois(date: DocDate | None) -> YearMonth | None:
    return YearMonth(date.year, date.month) if date else None


def profile_facts(document: ProfileDocument) -> ProfileFacts:
    """Faits utiles au scoring (minimisation : ni identité, ni coordonnées, ni texte libre)."""
    prefs = document.preferences
    titres = [
        *prefs.job_titles,
        *(e.title for e in document.experiences if e.title),
        *([document.identity.headline] if document.identity.headline else []),
    ]
    return ProfileFacts(
        titles=tuple(dict.fromkeys(titres)),
        skills=tuple(s.name for s in document.skills),
        experience_periods=tuple(
            ExperiencePeriod(_annee_mois(e.start), _annee_mois(e.end), e.is_current)
            for e in document.experiences
        ),
        degrees=tuple(
            " ".join(part for part in (f.degree, f.field_of_study) if part)
            for f in document.educations
            if f.degree
        ),
        country_codes=prefs.country_codes,
        cities=prefs.cities,
        remote_types=tuple(r.value for r in prefs.remote_types),
        employment_types=tuple(e.value for e in prefs.employment_types),
        salary_min=prefs.salary_min,
        salary_currency=prefs.salary_currency,
    )


def offer_facts(offre: JobOfferModel) -> OfferFacts:
    return OfferFacts(
        title=offre.title,
        description=offre.description,
        location=offre.location,
        country_code=offre.country_code,
        employment_type=offre.employment_type,
        remote_type=offre.remote_type,
        salary_min=offre.salary_min,
        salary_max=offre.salary_max,
        salary_currency=offre.salary_currency,
        published_at=offre.published_at,
    )


class SqlCandidateFactsReader:
    """Lit la dernière version **validée** : un brouillon n'est jamais une base de score."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def validated_snapshot(self, *, owner_id: uuid.UUID) -> ProfileSnapshot | None:
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
            return None
        stocke = await SqlProfileRepository(self._session).get_version(
            owner_id=owner_id, version=version
        )
        return ProfileSnapshot(stocke.meta.id, stocke.meta.version, profile_facts(stocke.document))


class SqlJobOfferReader:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, *, owner_id: uuid.UUID, offer_id: uuid.UUID) -> OfferFacts:
        offre = await self._session.scalar(
            select(JobOfferModel).where(
                JobOfferModel.id == offer_id, JobOfferModel.owner_id == owner_id
            )
        )
        if offre is None:
            raise OfferNotFoundError(str(offer_id))
        return offer_facts(offre)

    async def active_batch(
        self, *, owner_id: uuid.UUID, after: uuid.UUID | None, limit: int
    ) -> list[tuple[uuid.UUID, OfferFacts]]:
        requete = (
            select(JobOfferModel)
            .where(
                JobOfferModel.owner_id == owner_id,
                JobOfferModel.status == OfferStatus.ACTIVE.value,
            )
            .order_by(JobOfferModel.id)
            .limit(limit)
        )
        if after is not None:
            requete = requete.where(JobOfferModel.id > after)
        return [(o.id, offer_facts(o)) for o in await self._session.scalars(requete)]
