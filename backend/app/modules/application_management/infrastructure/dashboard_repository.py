"""Lecture des indicateurs du tableau de bord (TASK-014-21, 22).

Modèle de lecture transverse : il croise offres, scores, candidatures, budget IA et recherches
sans rien écrire. Règle de fond : un indicateur sans donnée sous-jacente vaut `None`, jamais 0
ni le total d'une autre mesure.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import desc, exists, func, select
from sqlalchemy.dialects.postgresql import distinct_on

from app.modules.ai_management.domain.enums import BudgetPeriod
from app.modules.ai_management.infrastructure.models import AIBudgetModel, AIUsageModel
from app.modules.ai_management.infrastructure.repositories import SqlAIUsageRepository
from app.modules.application_management.domain.entities import (
    AIBudgetSummary,
    DashboardMetrics,
    Funnel,
    InterviewEvent,
    MonthlyTrend,
    RecentActivity,
    RecentSearch,
    TopMatch,
)
from app.modules.application_management.domain.enums import ApplicationStatus, EventKind
from app.modules.application_management.domain.ports import DashboardRepositoryPort
from app.modules.application_management.domain.rules import compute_application_stats
from app.modules.application_management.infrastructure.models import (
    ApplicationEventModel,
    ApplicationModel,
)
from app.modules.application_management.infrastructure.repository import (
    SQLAlchemyApplicationRepository,
)
from app.modules.candidate_profile.infrastructure.profile_repository import SqlProfileRepository
from app.modules.job_discovery.domain.enums import OfferState, OfferStatus
from app.modules.job_discovery.infrastructure.models import (
    JobOfferModel,
    JobOfferStateModel,
    SavedSearchModel,
    SearchRunModel,
)
from app.modules.job_intelligence.infrastructure.models import JobMatchScoreModel
from app.modules.notifications.infrastructure.models import NotificationPreferenceModel

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# Une offre est « nouvelle » 7 jours après sa première apparition, tant que l'utilisateur ne l'a
# ni sauvegardée, ni ignorée, ni transformée en candidature.
NEW_OFFER_DAYS = 7
# Seuil de pertinence : celui que l'utilisateur a choisi pour ses notifications (défaut du schéma).
DEFAULT_RELEVANCE_THRESHOLD = 70
_RECENT_SEARCHES = 5
_RECENT_ACTIVITIES = 10
_TOP_MATCHES = 3
# Fenêtre des entretiens renvoyés : de quoi remplir la semaine courante, la précédente (pour la
# comparaison) et le mois à venir.
_INTERVIEWS_PAST_DAYS = 14
_INTERVIEWS_FUTURE_DAYS = 30
_MAX_INTERVIEWS = 100


def _month_bounds(now: datetime) -> tuple[datetime, datetime]:
    """Début du mois courant et début du mois précédent (mois civils, même fuseau que `now`)."""
    debut = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    precedent = (debut - timedelta(days=1)).replace(day=1)
    return debut, precedent


def _latest_scores(owner_id: uuid.UUID) -> Any:
    """Dernier score connu de chaque offre (sous-requête `offer_id`, `score`)."""
    return (
        select(
            JobMatchScoreModel.offer_id.label("offer_id"),
            JobMatchScoreModel.score.label("score"),
        )
        .where(JobMatchScoreModel.owner_id == owner_id)
        .ext(distinct_on(JobMatchScoreModel.offer_id))
        .order_by(JobMatchScoreModel.offer_id, desc(JobMatchScoreModel.computed_at))
        .subquery()
    )


def _search_label(criteres: dict[str, object], nom_enregistre: str | None) -> str:
    if nom_enregistre:
        return nom_enregistre
    mots = criteres.get("keywords")
    morceaux = [
        str(criteres.get("text") or ""),
        ", ".join(str(m) for m in mots) if isinstance(mots, list) else "",
        str(criteres.get("company") or ""),
        str(criteres.get("city") or ""),
    ]
    return " · ".join(m for m in morceaux if m) or "Recherche sans critère"


class SQLAlchemyDashboardRepository(DashboardRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_dashboard_metrics(
        self, owner_id: uuid.UUID, *, now: datetime
    ) -> DashboardMetrics:
        seuil = await self._threshold(owner_id)
        applications = await SQLAlchemyApplicationRepository(self._session).list_for_stats(owner_id)
        stats = compute_application_stats(applications, now=now)
        debut_mois, debut_precedent = _month_bounds(now)
        total_offres = await self._count_offers(owner_id)
        par_statut = {s: sum(1 for a in applications if a.status is s) for s in ApplicationStatus}

        return DashboardMetrics(
            display_name=await self._display_name(owner_id),
            total_offers_found=total_offres,
            active_offers_count=await self._count_offers(owner_id, only_active=True),
            active_offers_trend=MonthlyTrend(
                current=await self._count_first_seen(owner_id, debut_mois, None),
                previous=await self._count_first_seen(owner_id, debut_precedent, debut_mois),
            ),
            new_offers_count=await self._count_new_offers(owner_id, now),
            relevant_offers_count=await self._count_relevant(owner_id, seuil),
            relevance_threshold=seuil,
            top_matches=await self._top_matches(owner_id),
            active_applications_count=stats.active_applications,
            applications_trend=MonthlyTrend(
                current=sum(1 for a in applications if a.created_at >= debut_mois),
                previous=sum(
                    1 for a in applications if debut_precedent <= a.created_at < debut_mois
                ),
            ),
            applications_sent_count=stats.sent_applications,
            interviews_count=stats.interviews_count,
            response_rate=stats.response_rate,
            funnel=Funnel(
                offers=total_offres,
                tracked=stats.total_applications,
                sent=stats.sent_applications,
                responses=stats.responses_count,
                offers_received=stats.offers_received_count,
            ),
            applications_by_status=par_statut,
            interviews=await self._interviews(owner_id, now),
            ai_budget=await self._ai_budget(owner_id, now),
            recent_searches=await self._recent_searches(owner_id),
            recent_activities=await self._recent_activities(owner_id),
        )

    async def _display_name(self, owner_id: uuid.UUID) -> str | None:
        profil = await SqlProfileRepository(self._session).latest(owner_id=owner_id)
        prenom = profil.document.identity.first_name if profil else None
        return (prenom or "").strip() or None

    async def _count_first_seen(
        self, owner_id: uuid.UUID, depuis: datetime, jusqu_a: datetime | None
    ) -> int:
        requete = (
            select(func.count())
            .select_from(JobOfferModel)
            .where(JobOfferModel.owner_id == owner_id, JobOfferModel.first_seen_at >= depuis)
        )
        if jusqu_a is not None:
            requete = requete.where(JobOfferModel.first_seen_at < jusqu_a)
        return int(await self._session.scalar(requete) or 0)

    async def _top_matches(self, owner_id: uuid.UUID) -> tuple[TopMatch, ...]:
        """Offres actives les mieux notées, hors offres ignorées ou déjà suivies."""
        dernier_score = _latest_scores(owner_id)
        suivie = exists().where(
            ApplicationModel.offer_id == JobOfferModel.id, ApplicationModel.owner_id == owner_id
        )
        ignoree = exists().where(
            JobOfferStateModel.offer_id == JobOfferModel.id,
            JobOfferStateModel.owner_id == owner_id,
            JobOfferStateModel.state == OfferState.IGNORED.value,
        )
        lignes = await self._session.execute(
            select(
                JobOfferModel.id,
                JobOfferModel.title,
                JobOfferModel.company_name,
                dernier_score.c.score,
            )
            .join(dernier_score, dernier_score.c.offer_id == JobOfferModel.id)
            .where(JobOfferModel.status == OfferStatus.ACTIVE.value, ~suivie, ~ignoree)
            .order_by(desc(dernier_score.c.score), JobOfferModel.title)
            .limit(_TOP_MATCHES)
        )
        return tuple(
            TopMatch(offer_id=ligne[0], title=ligne[1], company_name=ligne[2], score=ligne[3])
            for ligne in lignes.all()
        )

    async def _interviews(self, owner_id: uuid.UUID, now: datetime) -> tuple[InterviewEvent, ...]:
        lignes = await self._session.execute(
            select(ApplicationEventModel, JobOfferModel.title, JobOfferModel.company_name)
            .join(ApplicationModel, ApplicationEventModel.application_id == ApplicationModel.id)
            .join(JobOfferModel, ApplicationModel.offer_id == JobOfferModel.id)
            .where(
                ApplicationEventModel.owner_id == owner_id,
                ApplicationEventModel.kind == EventKind.INTERVIEW.value,
                ApplicationEventModel.occurred_at >= now - timedelta(days=_INTERVIEWS_PAST_DAYS),
                ApplicationEventModel.occurred_at <= now + timedelta(days=_INTERVIEWS_FUTURE_DAYS),
            )
            .order_by(ApplicationEventModel.occurred_at)
            .limit(_MAX_INTERVIEWS)
        )
        return tuple(
            InterviewEvent(
                application_id=ev.application_id,
                occurred_at=ev.occurred_at,
                job_title=titre,
                company_name=entreprise,
                description=ev.body,
            )
            for ev, titre, entreprise in lignes.all()
        )

    async def _count_offers(self, owner_id: uuid.UUID, *, only_active: bool = False) -> int:
        requete = (
            select(func.count())
            .select_from(JobOfferModel)
            .where(JobOfferModel.owner_id == owner_id)
        )
        if only_active:
            requete = requete.where(JobOfferModel.status == OfferStatus.ACTIVE.value)
        return int(await self._session.scalar(requete) or 0)

    async def _count_new_offers(self, owner_id: uuid.UUID, now: datetime) -> int:
        suivie = exists().where(
            ApplicationModel.offer_id == JobOfferModel.id, ApplicationModel.owner_id == owner_id
        )
        triee = exists().where(
            JobOfferStateModel.offer_id == JobOfferModel.id, JobOfferStateModel.owner_id == owner_id
        )
        return int(
            await self._session.scalar(
                select(func.count())
                .select_from(JobOfferModel)
                .where(
                    JobOfferModel.owner_id == owner_id,
                    JobOfferModel.status == OfferStatus.ACTIVE.value,
                    JobOfferModel.first_seen_at >= now - timedelta(days=NEW_OFFER_DAYS),
                    ~suivie,
                    ~triee,
                )
            )
            or 0
        )

    async def _threshold(self, owner_id: uuid.UUID) -> int:
        choisi = await self._session.scalar(
            select(NotificationPreferenceModel.min_relevance_score).where(
                NotificationPreferenceModel.owner_id == owner_id
            )
        )
        return int(choisi) if choisi is not None else DEFAULT_RELEVANCE_THRESHOLD

    async def _count_relevant(self, owner_id: uuid.UUID, seuil: int) -> int | None:
        """Offres actives dont le dernier score atteint le seuil ; None si rien n'est scoré."""
        dernier_score = _latest_scores(owner_id)
        base = (
            select(func.count(), func.count().filter(dernier_score.c.score >= seuil))
            .select_from(dernier_score)
            .join(JobOfferModel, JobOfferModel.id == dernier_score.c.offer_id)
            .where(JobOfferModel.status == OfferStatus.ACTIVE.value)
        )
        evaluees, pertinentes = (await self._session.execute(base)).one()
        return int(pertinentes) if evaluees else None

    async def _ai_budget(self, owner_id: uuid.UUID, now: datetime) -> AIBudgetSummary:
        debut = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        fin = (debut + timedelta(days=32)).replace(day=1)
        depense = await SqlAIUsageRepository(self._session).total_cost(
            owner_id=owner_id, since=debut, until=fin
        )
        plafond = (
            await self._session.execute(
                select(AIBudgetModel.amount, AIBudgetModel.currency).where(
                    AIBudgetModel.owner_id == owner_id,
                    AIBudgetModel.period == BudgetPeriod.MONTHLY.value,
                    AIBudgetModel.provider.is_(None),
                )
            )
        ).first()
        if plafond is not None:
            return AIBudgetSummary(spent=depense, limit=Decimal(plafond[0]), currency=plafond[1])
        devise = await self._session.scalar(
            select(AIUsageModel.currency)
            .where(AIUsageModel.owner_id == owner_id)
            .order_by(desc(AIUsageModel.created_at))
            .limit(1)
        )
        return AIBudgetSummary(spent=depense, limit=None, currency=devise)

    async def _recent_searches(self, owner_id: uuid.UUID) -> tuple[RecentSearch, ...]:
        lignes = await self._session.execute(
            select(SearchRunModel, SavedSearchModel.name)
            .outerjoin(SavedSearchModel, SearchRunModel.saved_search_id == SavedSearchModel.id)
            .where(SearchRunModel.owner_id == owner_id)
            .order_by(desc(SearchRunModel.started_at))
            .limit(_RECENT_SEARCHES)
        )
        return tuple(
            RecentSearch(
                id=run.id,
                started_at=run.started_at,
                status=run.status,
                result_count=run.result_count,
                label=_search_label(run.criteria, nom),
            )
            for run, nom in lignes.all()
        )

    async def _recent_activities(self, owner_id: uuid.UUID) -> tuple[RecentActivity, ...]:
        lignes = await self._session.execute(
            select(ApplicationEventModel, JobOfferModel.title, JobOfferModel.company_name)
            .join(ApplicationModel, ApplicationEventModel.application_id == ApplicationModel.id)
            .join(JobOfferModel, ApplicationModel.offer_id == JobOfferModel.id)
            .where(ApplicationEventModel.owner_id == owner_id)
            .order_by(
                desc(ApplicationEventModel.occurred_at), desc(ApplicationEventModel.created_at)
            )
            .limit(_RECENT_ACTIVITIES)
        )
        return tuple(
            RecentActivity(
                application_id=ev.application_id,
                kind=EventKind(ev.kind),
                occurred_at=ev.occurred_at,
                body=ev.body,
                job_title=titre,
                company_name=entreprise,
            )
            for ev, titre, entreprise in lignes.all()
        )
