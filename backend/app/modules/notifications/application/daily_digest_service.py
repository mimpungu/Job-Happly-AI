"""Service de consolidation et génération du résumé quotidien (Daily Digest)."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai_management.infrastructure.models import AIUsageModel
from app.modules.application_management.domain.enums import ApplicationStatus
from app.modules.application_management.infrastructure.models import ApplicationModel
from app.modules.job_discovery.infrastructure.models import JobOfferModel
from app.modules.notifications.application.notification_service import NotificationService
from app.modules.notifications.domain.entities import DailyDigestSummary
from app.modules.notifications.domain.enums import NotificationKind

logger = logging.getLogger("happly.notifications.digest")


def _now() -> datetime:
    return datetime.now(UTC)


class DailyDigestService:
    """Consolide l'activité des dernières 24 heures et génère le résumé quotidien."""

    def __init__(
        self,
        session: AsyncSession,
        notification_service: NotificationService,
        *,
        clock: Callable[[], datetime] = _now,
    ) -> None:
        self._session = session
        self._notification_service = notification_service
        self._clock = clock

    async def generate_digest(self, *, owner_id: uuid.UUID) -> DailyDigestSummary:
        maintenant = self._clock()
        hier = maintenant - timedelta(days=1)
        aujourdhui_date = maintenant.date()

        # 1. Nouvelles offres découvertes dans les dernières 24h
        nouvelles_offres_stmt = select(func.count(JobOfferModel.id)).where(
            JobOfferModel.owner_id == owner_id,
            JobOfferModel.first_seen_at >= hier,
        )
        nb_nouvelles_offres = (await self._session.scalar(nouvelles_offres_stmt)) or 0

        # Échantillon des 3 dernières offres
        offres_stmt = (
            select(JobOfferModel.title, JobOfferModel.company_name, JobOfferModel.id)
            .where(
                JobOfferModel.owner_id == owner_id,
                JobOfferModel.first_seen_at >= hier,
            )
            .limit(3)
        )
        lignes_offres = (await self._session.execute(offres_stmt)).all()
        sample_offers: list[dict[str, Any]] = [
            {
                "title": ligne.title,
                "company": ligne.company_name or "Entreprise",
                "id": str(ligne.id),
            }
            for ligne in lignes_offres
        ]

        # 2. Relances dues (candidatures avec follow_up_at <= maintenant et statuts actifs)
        relances_stmt = select(func.count(ApplicationModel.id)).where(
            ApplicationModel.owner_id == owner_id,
            ApplicationModel.follow_up_at.is_not(None),
            ApplicationModel.follow_up_at <= maintenant,
            ApplicationModel.status.in_(
                [
                    ApplicationStatus.SENT.value,
                    ApplicationStatus.PENDING.value,
                    ApplicationStatus.INTERVIEW.value,
                    ApplicationStatus.SECOND_INTERVIEW.value,
                ]
            ),
        )
        nb_relances = (await self._session.scalar(relances_stmt)) or 0

        # 3. Candidatures actives totales (non rejetées ni abandonnées)
        actives_stmt = select(func.count(ApplicationModel.id)).where(
            ApplicationModel.owner_id == owner_id,
            ApplicationModel.status.not_in(
                [
                    ApplicationStatus.REJECTED.value,
                    ApplicationStatus.ABANDONED.value,
                ]
            ),
        )
        nb_actives = (await self._session.scalar(actives_stmt)) or 0

        # 4. Dépenses IA du jour
        debut_journee = datetime(
            aujourdhui_date.year, aujourdhui_date.month, aujourdhui_date.day, tzinfo=UTC
        )
        ia_stmt = select(
            func.coalesce(
                func.sum(AIUsageModel.actual_cost),
                func.sum(AIUsageModel.estimated_cost),
                0,
            )
        ).where(
            AIUsageModel.owner_id == owner_id,
            AIUsageModel.created_at >= debut_journee,
        )
        somme_ia = await self._session.scalar(ia_stmt)
        depenses_ia = Decimal(str(somme_ia)) if somme_ia is not None else Decimal("0.0000")

        summary = DailyDigestSummary(
            date=maintenant.strftime("%Y-%m-%d"),
            new_offers_count=nb_nouvelles_offres,
            top_offers_count=len(sample_offers),
            follow_ups_due_count=nb_relances,
            active_applications_count=nb_actives,
            ai_spent_today=depenses_ia,
            sample_offers=tuple(sample_offers),
        )

        # Construction du texte du résumé
        titre = f"Résumé quotidien Happly AI — {maintenant.strftime('%d/%m/%Y')}"
        corps = (
            f"Aujourd'hui : {nb_nouvelles_offres} nouvelle(s) offre(s), "
            f"{nb_relances} relance(s) de candidature à effectuer, "
            f"{nb_actives} candidature(s) active(s). "
            f"Dépenses IA du jour : {depenses_ia:.4f} EUR."
        )

        payload: dict[str, Any] = {
            "date": summary.date,
            "new_offers_count": nb_nouvelles_offres,
            "follow_ups_due_count": nb_relances,
            "active_applications_count": nb_actives,
            "ai_spent_today": float(depenses_ia),
            "sample_offers": list(sample_offers),
        }

        # Émission de la notification correspondante
        await self._notification_service.notify(
            owner_id=owner_id,
            kind=NotificationKind.DAILY_DIGEST,
            title=titre,
            body=corps,
            payload=payload,
        )

        return summary
