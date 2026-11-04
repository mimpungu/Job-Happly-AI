"""Lecture SQL des faits d'automatisation (résumé quotidien, relances, budget IA)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai_management.infrastructure.models import AISettingsModel, AIUsageModel
from app.modules.application_management.domain.enums import ApplicationStatus
from app.modules.application_management.infrastructure.models import ApplicationModel
from app.modules.job_discovery.infrastructure.models import JobOfferModel, SavedSearchModel
from app.modules.notifications.application.ports import DigestFacts, DueFollowUp, SavedSearchInfo

_STATUTS_A_RELANCER = [
    ApplicationStatus.SENT.value,
    ApplicationStatus.PENDING.value,
    ApplicationStatus.INTERVIEW.value,
    ApplicationStatus.SECOND_INTERVIEW.value,
]
_STATUTS_CLOS = [ApplicationStatus.REJECTED.value, ApplicationStatus.ABANDONED.value]


class SqlAutomationFacts:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def digest_facts(self, owner_id: uuid.UUID, *, now: datetime) -> DigestFacts:
        hier = now - timedelta(days=1)
        nouvelles = (
            await self._session.scalar(
                select(func.count(JobOfferModel.id)).where(
                    JobOfferModel.owner_id == owner_id, JobOfferModel.first_seen_at >= hier
                )
            )
        ) or 0
        lignes = (
            await self._session.execute(
                select(JobOfferModel.title, JobOfferModel.company_name, JobOfferModel.id)
                .where(JobOfferModel.owner_id == owner_id, JobOfferModel.first_seen_at >= hier)
                .limit(3)
            )
        ).all()
        relances = (
            await self._session.scalar(
                select(func.count(ApplicationModel.id)).where(
                    ApplicationModel.owner_id == owner_id,
                    ApplicationModel.follow_up_at.is_not(None),
                    ApplicationModel.follow_up_at <= now,
                    ApplicationModel.status.in_(_STATUTS_A_RELANCER),
                )
            )
        ) or 0
        actives = (
            await self._session.scalar(
                select(func.count(ApplicationModel.id)).where(
                    ApplicationModel.owner_id == owner_id,
                    ApplicationModel.status.not_in(_STATUTS_CLOS),
                )
            )
        ) or 0
        debut_journee = datetime(now.year, now.month, now.day, tzinfo=UTC)
        return DigestFacts(
            new_offers_count=nouvelles,
            sample_offers=tuple(
                {"title": l.title, "company": l.company_name or "Entreprise", "id": str(l.id)}
                for l in lignes  # noqa: E741
            ),
            follow_ups_due=relances,
            active_applications=actives,
            ai_spent_today=await self.ai_spent_since(owner_id, debut_journee),
        )

    async def saved_search(
        self, owner_id: uuid.UUID, saved_search_id: uuid.UUID
    ) -> SavedSearchInfo | None:
        recherche = await self._session.scalar(
            select(SavedSearchModel).where(
                SavedSearchModel.id == saved_search_id, SavedSearchModel.owner_id == owner_id
            )
        )
        return SavedSearchInfo(recherche.name, recherche.active) if recherche else None

    async def offers_created_since(self, owner_id: uuid.UUID, since: datetime) -> int:
        return (
            await self._session.scalar(
                select(func.count(JobOfferModel.id)).where(
                    JobOfferModel.owner_id == owner_id, JobOfferModel.created_at >= since
                )
            )
        ) or 0

    async def due_follow_ups(self, owner_id: uuid.UUID, now: datetime) -> list[DueFollowUp]:
        lignes = (
            await self._session.execute(
                select(
                    ApplicationModel.id,
                    ApplicationModel.offer_id,
                    JobOfferModel.title,
                    JobOfferModel.company_name,
                )
                .outerjoin(JobOfferModel, JobOfferModel.id == ApplicationModel.offer_id)
                .where(
                    ApplicationModel.owner_id == owner_id,
                    ApplicationModel.follow_up_at.is_not(None),
                    ApplicationModel.follow_up_at <= now,
                    ApplicationModel.status.in_(_STATUTS_A_RELANCER),
                )
            )
        ).all()
        return [
            DueFollowUp(
                application_id=ligne.id,
                offer_id=ligne.offer_id,
                title=ligne.title or "Poste candidaté",
                company=ligne.company_name or "Entreprise",
            )
            for ligne in lignes
        ]

    async def ai_spent_since(self, owner_id: uuid.UUID, since: datetime) -> Decimal:
        somme = await self._session.scalar(
            select(
                func.coalesce(
                    func.sum(AIUsageModel.actual_cost), func.sum(AIUsageModel.estimated_cost), 0
                )
            ).where(AIUsageModel.owner_id == owner_id, AIUsageModel.created_at >= since)
        )
        return Decimal(str(somme)) if somme is not None else Decimal("0.0000")

    async def ai_currency(self, owner_id: uuid.UUID) -> str:
        reglages = await self._session.scalar(
            select(AISettingsModel).where(AISettingsModel.owner_id == owner_id)
        )
        return reglages.currency if reglages else "EUR"
