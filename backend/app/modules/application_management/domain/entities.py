"""Entités et objets-valeurs du domaine de gestion des candidatures (TASK-014-01).

Définit les structures du domaine pur pour le suivi, le cycle de vie,
l'historique, les dossiers de candidature et les métriques de performance.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

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


@dataclass(frozen=True)
class ApplicationStats:
    """Statistiques calculées sur les candidatures réelles de l'utilisateur (TASK-014-15, 22)."""

    total_applications: int
    sent_applications: int
    interviews_count: int
    offers_received_count: int
    rejections_count: int
    response_rate: float
    active_applications: int
    pending_follow_ups_count: int


@dataclass(frozen=True)
class DashboardMetrics:
    """Métriques globales pour le tableau de bord de pilotage (TASK-014-21)."""

    total_offers_found: int
    new_offers_count: int
    relevant_offers_count: int
    applications_sent_count: int
    interviews_count: int
    response_rate: float
    ai_budget_consumed_cents: int
    ai_budget_limit_cents: int

