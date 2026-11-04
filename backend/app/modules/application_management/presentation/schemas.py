"""Schémas de l'API de suivi des candidatures et du tableau de bord (EPIC 014)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, StringConstraints

from app.modules.application_management.domain.enums import ApplicationStatus, EventKind

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
# Les dates sans fuseau sont refusées : « 9 h » ne veut rien dire sans lui.


class CreateApplicationRequest(BaseModel):
    offer_id: uuid.UUID
    initial_status: ApplicationStatus = ApplicationStatus.NEW_OFFER


class ChangeStatusRequest(BaseModel):
    target_status: ApplicationStatus
    reason: ShortText | None = None


class ConfirmSubmissionRequest(BaseModel):
    """Trace d'un envoi fait par l'utilisateur lui-même ; rien n'est envoyé par l'application."""

    notes: ShortText | None = None
    applied_at: AwareDatetime | None = None
    """Date réelle d'envoi si elle précède l'enregistrement (défaut : maintenant)."""


class AddNoteRequest(BaseModel):
    body: Text


class AddInterviewRequest(BaseModel):
    description: Text
    interview_time: AwareDatetime | None = None


class ScheduleFollowUpRequest(BaseModel):
    follow_up_at: AwareDatetime | None = None
    notes: ShortText | None = None


class AttachDocumentsRequest(BaseModel):
    cv_version_id: uuid.UUID | None = None
    letter_version_id: uuid.UUID | None = None


class AddContactRequest(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    email: Annotated[
        str | None,
        StringConstraints(
            strip_whitespace=True, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
        ),
    ] = None
    phone: Annotated[
        str | None,
        StringConstraints(strip_whitespace=True, max_length=40, pattern=r"^[0-9+().\-\s]{3,40}$"),
    ] = None
    role: Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=200)] = None


# ------------------------------------------------------------------ réponses


class OfferSummaryResponse(BaseModel):
    offer_id: uuid.UUID
    title: str
    company_name: str | None
    location: str | None
    country_code: str | None
    application_url: str


class ContactResponse(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    name: str
    email: str | None
    phone: str | None
    role: str | None
    created_at: datetime | None


class TimelineEventResponse(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    kind: EventKind
    occurred_at: datetime
    from_status: ApplicationStatus | None
    to_status: ApplicationStatus | None
    body: str | None


class AssociatedDocumentResponse(BaseModel):
    document_version_id: uuid.UUID
    document_id: uuid.UUID
    kind: str
    title: str
    version: int
    quality_passed: bool | None
    quality_score: int | None
    is_current: bool
    """Vrai pour la version actuellement retenue pour cette candidature."""


class ApplicationResponse(BaseModel):
    """Candidature pour les listes et les cartes : l'offre liée permet de la reconnaître."""

    id: uuid.UUID
    offer_id: uuid.UUID
    offer: OfferSummaryResponse | None
    status: ApplicationStatus
    created_at: datetime
    updated_at: datetime
    applied_at: datetime | None
    follow_up_at: datetime | None
    response_received_at: datetime | None
    cv_version_id: uuid.UUID | None
    letter_version_id: uuid.UUID | None


class ApplicationDetailResponse(ApplicationResponse):
    """Fiche complète (TASK-014-14)."""

    contacts: list[ContactResponse]
    events: list[TimelineEventResponse]
    documents: list[AssociatedDocumentResponse]
    allowed_transitions: list[ApplicationStatus]
    """Statuts atteignables depuis le statut courant (hors envoi, qui se confirme à part)."""
    can_confirm_submission: bool


class ApplicationListResponse(BaseModel):
    items: list[ApplicationResponse]
    total: int
    limit: int
    offset: int


class KanbanColumnResponse(BaseModel):
    status: ApplicationStatus
    count: int
    """Total réel de la colonne, même quand `items` n'en montre qu'une partie."""
    items: list[ApplicationResponse]
    has_more: bool


class KanbanViewResponse(BaseModel):
    columns: list[KanbanColumnResponse]


class ApplicationDossierResponse(BaseModel):
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
    missing_elements: list[str]
    warnings: list[str]


class OpenUrlResponse(BaseModel):
    application_url: str


class ApplicationStatsResponse(BaseModel):
    responses_count: int
    total_applications: int
    sent_applications: int
    interviews_count: int
    offers_received_count: int
    rejections_count: int
    response_rate: float | None
    """None tant qu'aucune candidature n'est envoyée : pas de taux sans donnée."""
    active_applications: int
    pending_follow_ups_count: int
    due_follow_ups_count: int


class AIBudgetResponse(BaseModel):
    spent: Decimal
    limit: Decimal | None
    currency: str | None
    period: str = "monthly"


class RecentSearchResponse(BaseModel):
    id: uuid.UUID
    started_at: datetime
    status: str
    result_count: int | None
    label: str


class RecentActivityResponse(BaseModel):
    application_id: uuid.UUID
    kind: EventKind
    occurred_at: datetime
    body: str | None
    job_title: str
    company_name: str | None


class MonthlyTrendResponse(BaseModel):
    current: int
    previous: int
    percent: float | None
    """Variation en % ; `None` sans mois précédent."""


class TopMatchResponse(BaseModel):
    offer_id: uuid.UUID
    title: str
    company_name: str | None
    score: float
    """Score de compatibilité sur 100 calculé par le moteur de correspondance."""


class InterviewEventResponse(BaseModel):
    application_id: uuid.UUID
    occurred_at: datetime
    job_title: str
    company_name: str | None
    description: str | None


class FunnelResponse(BaseModel):
    """Chaque étape est un sous-ensemble de la précédente."""

    offers: int
    tracked: int
    sent: int
    responses: int
    offers_received: int


class DashboardMetricsResponse(BaseModel):
    """Chaque `None` signifie « pas de donnée », et non zéro (TASK-014-22)."""

    display_name: str | None
    total_offers_found: int
    active_offers_count: int
    active_offers_trend: MonthlyTrendResponse
    new_offers_count: int
    relevant_offers_count: int | None
    relevance_threshold: int
    top_matches: list[TopMatchResponse]
    active_applications_count: int
    applications_trend: MonthlyTrendResponse
    applications_sent_count: int
    interviews_count: int
    response_rate: float | None
    funnel: FunnelResponse
    applications_by_status: dict[ApplicationStatus, int]
    interviews: list[InterviewEventResponse]
    ai_budget: AIBudgetResponse
    recent_searches: list[RecentSearchResponse]
    recent_activities: list[RecentActivityResponse]
