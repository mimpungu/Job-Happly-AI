"""Schémas Pydantic pour l'API REST de suivi des candidatures et dashboard (EPIC 014)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.application_management.domain.enums import ApplicationStatus, EventKind


class CreateApplicationRequest(BaseModel):
    """Requête de création d'une candidature liée à une offre (TASK-014-01, 02)."""

    offer_id: uuid.UUID
    initial_status: ApplicationStatus = ApplicationStatus.NEW_OFFER


class ChangeStatusRequest(BaseModel):
    """Requête de mise à jour du statut d'une candidature (TASK-014-03)."""

    target_status: ApplicationStatus
    reason: str | None = None


class ConfirmSubmissionRequest(BaseModel):
    """Confirmation manuelle de soumission externe par le candidat (TASK-014-04, 20)."""

    notes: str | None = None


class AddNoteRequest(BaseModel):
    """Ajout d'une note personnelle dans l'historique (TASK-014-07)."""

    body: str = Field(min_length=1, max_length=5000)


class AddInterviewRequest(BaseModel):
    """Ajout d'un événement d'entretien ou d'échange (TASK-014-08)."""

    description: str = Field(min_length=1, max_length=5000)
    interview_time: datetime | None = None


class ScheduleFollowUpRequest(BaseModel):
    """Programmation ou annulation d'une relance (TASK-014-10)."""

    follow_up_at: datetime | None = None
    notes: str | None = None


class AttachDocumentsRequest(BaseModel):
    """Association de versions de CV et/ou lettre (TASK-014-09)."""

    cv_version_id: uuid.UUID | None = None
    letter_version_id: uuid.UUID | None = None


class AddContactRequest(BaseModel):
    """Enregistrement d'un recruteur ou contact (TASK-014-05)."""

    name: str = Field(min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=40)
    role: str | None = Field(default=None, max_length=200)


# Réponses


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
    id: uuid.UUID
    application_id: uuid.UUID
    document_version_id: uuid.UUID
    created_at: datetime | None


class ApplicationResponse(BaseModel):
    """Représentation synthétique d'une candidature (pour liste et cartes)."""

    id: uuid.UUID
    offer_id: uuid.UUID
    status: ApplicationStatus
    created_at: datetime
    updated_at: datetime
    applied_at: datetime | None
    follow_up_at: datetime | None
    response_received_at: datetime | None
    cv_version_id: uuid.UUID | None
    letter_version_id: uuid.UUID | None


class ApplicationDetailResponse(ApplicationResponse):
    """Fiche complète d'une candidature avec contacts, historique et documents (TASK-014-14)."""

    contacts: list[ContactResponse]
    events: list[TimelineEventResponse]
    documents: list[AssociatedDocumentResponse]


class ApplicationListResponse(BaseModel):
    """Réponse paginée pour la vue tableau (TASK-014-11)."""

    items: list[ApplicationResponse]
    total: int
    limit: int
    offset: int


class KanbanColumnResponse(BaseModel):
    status: ApplicationStatus
    count: int
    items: list[ApplicationResponse]


class KanbanViewResponse(BaseModel):
    """Vue Kanban découpée par colonne de statut (TASK-014-12)."""

    columns: list[KanbanColumnResponse]


class ApplicationDossierResponse(BaseModel):
    """Dossier de candidature assemblé et contrôlé (TASK-014-16, 17, 18)."""

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


class ApplicationStatsResponse(BaseModel):
    """Statistiques calculées sur les données réelles de l'utilisateur (TASK-014-15, 22)."""

    total_applications: int
    sent_applications: int
    interviews_count: int
    offers_received_count: int
    rejections_count: int
    response_rate: float
    active_applications: int
    pending_follow_ups_count: int


class DashboardMetricsResponse(BaseModel):
    """Synthèse des indicateurs clés pour le tableau de bord (TASK-014-21)."""

    total_offers_found: int
    new_offers_count: int
    relevant_offers_count: int
    applications_sent_count: int
    interviews_count: int
    response_rate: float
    ai_budget_consumed_cents: int
    ai_budget_limit_cents: int
