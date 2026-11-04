"""Service de consolidation et génération du résumé quotidien (Daily Digest)."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from app.modules.notifications.application.notification_service import NotificationService
from app.modules.notifications.application.ports import AutomationFactsPort
from app.modules.notifications.domain.entities import DailyDigestSummary
from app.modules.notifications.domain.enums import NotificationKind

logger = logging.getLogger("happly.notifications.digest")


def _now() -> datetime:
    return datetime.now(UTC)


class DailyDigestService:
    """Consolide l'activité des dernières 24 heures et génère le résumé quotidien."""

    def __init__(
        self,
        facts: AutomationFactsPort,
        notification_service: NotificationService,
        *,
        clock: Callable[[], datetime] = _now,
    ) -> None:
        self._facts = facts
        self._notification_service = notification_service
        self._clock = clock

    async def generate_digest(self, *, owner_id: uuid.UUID) -> DailyDigestSummary:
        maintenant = self._clock()
        faits = await self._facts.digest_facts(owner_id, now=maintenant)
        nb_nouvelles_offres = faits.new_offers_count
        nb_relances = faits.follow_ups_due
        nb_actives = faits.active_applications
        depenses_ia = faits.ai_spent_today
        sample_offers = list(faits.sample_offers)

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
