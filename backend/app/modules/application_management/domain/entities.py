"""Entités et objets-valeurs du domaine de gestion des candidatures (TASK-014-01).

Définit les structures du domaine pur pour le suivi, le cycle de vie,
l'historique, les dossiers de candidature et les métriques de performance.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from app.modules.application_management.domain.enums import ApplicationStatus, EventKind


@dataclass(frozen=True)
class ContactInfo:
    """Coordonnées d'un contact ou recruteur lié à une candidature (TASK-014-05)."""

    id: uuid.UUID
    application_id: uuid.UUID
    name: str
    email: str | None = None
    phone: str | None = None
    role: str | None = None
    created_at: datetime | None = None


@dataclass(frozen=True)
class TimelineEvent:
    """Événement historique horodaté sur une candidature (TASK-014-06 à 08)."""

    id: uuid.UUID
    application_id: uuid.UUID
    kind: EventKind
    occurred_at: datetime
    from_status: ApplicationStatus | None = None
    to_status: ApplicationStatus | None = None
    body: str | None = None


@dataclass(frozen=True)
class AssociatedDocument:
    """Document lié à la candidature (CV ou lettre, version exacte envoyée) (TASK-014-09)."""

    id: uuid.UUID
    application_id: uuid.UUID
    document_version_id: uuid.UUID
    created_at: datetime | None = None


@dataclass(frozen=True)
class OfferSummary:
    """Ce que le CRM affiche de l'offre liée : de quoi reconnaître la candidature."""

    offer_id: uuid.UUID
    title: str
    company_name: str | None
    location: str | None
    country_code: str | None
    application_url: str


@dataclass(frozen=True)
class DocumentVersionInfo:
    """Version de document telle que le CRM la voit (type, rang, qualité mesurée)."""

    version_id: uuid.UUID
    document_id: uuid.UUID
    kind: str  # "cv" | "cover_letter"
    title: str
    version: int
    quality_passed: bool | None
    """Résultat de l'audit stocké avec la version ; None si aucun audit n'a été calculé."""
    quality_score: int | None


@dataclass
class ApplicationAggregate:
    """Agrégat principal représentant une candidature et son cycle de vie (TASK-014-01)."""

    id: uuid.UUID
    owner_id: uuid.UUID
    offer_id: uuid.UUID
    status: ApplicationStatus
    created_at: datetime
    updated_at: datetime
    applied_at: datetime | None = None
    follow_up_at: datetime | None = None
    response_received_at: datetime | None = None
    cv_version_id: uuid.UUID | None = None
    letter_version_id: uuid.UUID | None = None
    contacts: list[ContactInfo] = field(default_factory=list)
    events: list[TimelineEvent] = field(default_factory=list)
    documents: list[AssociatedDocument] = field(default_factory=list)
    offer: OfferSummary | None = None
    """Renseignée par le repository ; absente des agrégats construits dans les tests de règles."""

    @property
    def is_sent(self) -> bool:
        """Indique si la candidature a effectivement été confirmée comme envoyée."""
        return self.applied_at is not None or self.status in {
            ApplicationStatus.SENT,
            ApplicationStatus.PENDING,
            ApplicationStatus.INTERVIEW,
            ApplicationStatus.SECOND_INTERVIEW,
            ApplicationStatus.OFFER_RECEIVED,
            ApplicationStatus.REJECTED,
        }

    @property
    def has_response(self) -> bool:
        """Indique si l'entreprise a répondu (positivement ou négativement)."""
        return self.response_received_at is not None or self.status in {
            ApplicationStatus.INTERVIEW,
            ApplicationStatus.SECOND_INTERVIEW,
            ApplicationStatus.OFFER_RECEIVED,
            ApplicationStatus.REJECTED,
        }


@dataclass(frozen=True)
class ApplicationDossier:
    """Dossier complet de candidature prêt pour l'envoi ou l'audit (TASK-014-16, 17)."""

    application_id: uuid.UUID
    offer_id: uuid.UUID
    job_title: str
    company_name: str | None
    application_url: str | None
    has_cv: bool
    cv_version_id: uuid.UUID | None
    has_letter: bool
    letter_version_id: uuid.UUID | None
    is_ready_to_send: bool
    missing_elements: tuple[str, ...]
    warnings: tuple[str, ...] = ()
    """Points d'attention non bloquants (audit de qualité d'un document insuffisant…)."""


@dataclass(frozen=True)
class ApplicationStats:
    """Statistiques calculées sur les candidatures réelles de l'utilisateur (TASK-014-15, 22).

    `response_rate` vaut None tant qu'aucune candidature n'a été envoyée : 0 % serait un chiffre
    sans donnée sous-jacente.
    """

    total_applications: int
    sent_applications: int
    interviews_count: int
    offers_received_count: int
    rejections_count: int
    response_rate: float | None
    active_applications: int
    pending_follow_ups_count: int
    due_follow_ups_count: int
    responses_count: int = 0
    """Candidatures envoyées ayant reçu un retour (numérateur du taux de réponse)."""


@dataclass(frozen=True)
class RecentSearch:
    id: uuid.UUID
    started_at: datetime
    status: str
    result_count: int | None
    label: str


@dataclass(frozen=True)
class RecentActivity:
    """Dernier événement de suivi, avec de quoi reconnaître la candidature concernée."""

    application_id: uuid.UUID
    kind: EventKind
    occurred_at: datetime
    body: str | None
    job_title: str
    company_name: str | None


@dataclass(frozen=True)
class AIBudgetSummary:
    """Consommation IA du mois courant face au plafond mensuel global (s'il existe)."""

    spent: Decimal
    limit: Decimal | None
    currency: str | None


@dataclass(frozen=True)
class MonthlyTrend:
    """Un compteur sur le mois courant et sur le mois précédent (mois civils)."""

    current: int
    previous: int

    @property
    def percent(self) -> float | None:
        """Variation en % ; None sans mois précédent (diviser par zéro n'a pas de sens)."""
        if self.previous <= 0:
            return None
        return round((self.current - self.previous) / self.previous * 100.0, 1)


@dataclass(frozen=True)
class TopMatch:
    """Offre parmi les plus compatibles avec le profil validé (score réel du moteur)."""

    offer_id: uuid.UUID
    title: str
    company_name: str | None
    score: Decimal


@dataclass(frozen=True)
class InterviewEvent:
    """Entretien daté enregistré dans l'historique d'une candidature."""

    application_id: uuid.UUID
    occurred_at: datetime
    job_title: str
    company_name: str | None
    description: str | None


@dataclass(frozen=True)
class Funnel:
    """Entonnoir de la recherche ; chaque étape est un sous-ensemble de la précédente."""

    offers: int
    tracked: int
    sent: int
    responses: int
    offers_received: int


@dataclass(frozen=True)
class DashboardMetrics:
    """Indicateurs du tableau de bord (TASK-014-21). Chaque `None` signifie « pas de donnée »."""

    display_name: str | None
    total_offers_found: int
    active_offers_count: int
    active_offers_trend: MonthlyTrend
    new_offers_count: int
    relevant_offers_count: int | None
    """None tant qu'aucun score de correspondance n'existe (pas de profil validé)."""
    relevance_threshold: int
    top_matches: tuple[TopMatch, ...]
    active_applications_count: int
    applications_trend: MonthlyTrend
    applications_sent_count: int
    interviews_count: int
    response_rate: float | None
    funnel: Funnel
    applications_by_status: dict[ApplicationStatus, int]
    interviews: tuple[InterviewEvent, ...]
    ai_budget: AIBudgetSummary
    recent_searches: tuple[RecentSearch, ...] = ()
    recent_activities: tuple[RecentActivity, ...] = ()
