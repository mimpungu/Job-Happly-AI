"""Interfaces de persistance et de lecture (ports) du suivi des candidatures (EPIC 014)."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.application_management.domain.entities import (
        ApplicationAggregate,
        ContactInfo,
        DashboardMetrics,
        DocumentVersionInfo,
        OfferSummary,
        TimelineEvent,
    )
    from app.modules.application_management.domain.enums import ApplicationStatus


@dataclass(frozen=True)
class ApplicationFilter:
    """Critères de la vue tableau (TASK-014-13)."""

    status: ApplicationStatus | None = None
    company_query: str | None = None
    title_query: str | None = None
    follow_up_due: bool = False
    """Relance échue : date de relance atteinte, candidature envoyée ou en attente."""
    has_follow_up: bool = False
    """Une relance est planifiée (échue ou non)."""


@dataclass(frozen=True)
class KanbanColumn:
    """Une colonne du Kanban : total réel et cartes les plus récemment modifiées."""

    count: int
    items: list[ApplicationAggregate]


class ApplicationRepositoryPort(ABC):
    """Persistance des candidatures, de leur historique et de leurs contacts."""

    @abstractmethod
    async def get_by_id(
        self, owner_id: uuid.UUID, application_id: uuid.UUID, *, for_update: bool = False
    ) -> ApplicationAggregate | None:
        """Candidature complète (offre, contacts, historique, documents).

        `for_update` verrouille la ligne : deux changements de statut simultanés se suivent.
        """

    @abstractmethod
    async def get_by_offer_id(
        self, owner_id: uuid.UUID, offer_id: uuid.UUID
    ) -> ApplicationAggregate | None:
        """Candidature liée à une offre, s'il y en a une."""

    @abstractmethod
    async def create(
        self, owner_id: uuid.UUID, offer_id: uuid.UUID, status: ApplicationStatus
    ) -> ApplicationAggregate:
        """Crée la candidature. Lève `DuplicateApplicationError` si l'offre est déjà suivie."""

    @abstractmethod
    async def update_status(
        self,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        new_status: ApplicationStatus,
        applied_at: datetime | None = None,
        response_received_at: datetime | None = None,
    ) -> None:
        """Change le statut ; les dates déjà connues ne sont jamais effacées."""

    @abstractmethod
    async def delete(self, owner_id: uuid.UUID, application_id: uuid.UUID) -> None:
        """Supprime la candidature avec son historique, ses contacts et ses documents associés.

        L'offre n'est jamais supprimée : seule la décision de la suivre est annulée.
        """

    @abstractmethod
    async def update_follow_up(
        self, owner_id: uuid.UUID, application_id: uuid.UUID, follow_up_at: datetime | None
    ) -> None:
        """Définit ou retire la date de relance."""

    @abstractmethod
    async def attach_documents(
        self,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        cv_version_id: uuid.UUID | None = None,
        letter_version_id: uuid.UUID | None = None,
    ) -> None:
        """Associe les versions exactes ; réassocier une version déjà liée est sans effet."""

    @abstractmethod
    async def add_event(
        self, owner_id: uuid.UUID, application_id: uuid.UUID, event: TimelineEvent
    ) -> TimelineEvent:
        """Ajoute un événement à l'historique (jamais modifié ni supprimé ensuite)."""

    @abstractmethod
    async def add_contact(
        self, owner_id: uuid.UUID, application_id: uuid.UUID, contact: ContactInfo
    ) -> ContactInfo:
        """Enregistre un contact."""

    @abstractmethod
    async def list_applications(
        self, owner_id: uuid.UUID, criteria: ApplicationFilter, limit: int, offset: int
    ) -> tuple[list[ApplicationAggregate], int]:
        """Vue tableau : une page, le total, l'offre liée ; sans historique ni contacts."""

    @abstractmethod
    async def list_for_kanban(
        self, owner_id: uuid.UUID, per_column_limit: int
    ) -> dict[ApplicationStatus, KanbanColumn]:
        """Vue Kanban : par statut, le total réel et les `per_column_limit` plus récentes."""

    @abstractmethod
    async def list_for_stats(self, owner_id: uuid.UUID) -> list[ApplicationAggregate]:
        """Candidatures sans relations, pour les statistiques."""


class OfferReaderPort(ABC):
    """Lecture des offres (module de découverte) : le CRM n'accède pas à ses tables."""

    @abstractmethod
    async def get_summary(self, owner_id: uuid.UUID, offer_id: uuid.UUID) -> OfferSummary | None:
        """Résumé de l'offre, ou None si elle n'existe pas pour cet utilisateur."""


class DocumentVersionReaderPort(ABC):
    """Lecture des versions de documents générés (module de génération)."""

    @abstractmethod
    async def get_info(
        self, owner_id: uuid.UUID, version_id: uuid.UUID
    ) -> DocumentVersionInfo | None:
        """Type, titre, rang et audit d'une version, ou None si elle n'est pas à l'utilisateur."""


class DashboardRepositoryPort(ABC):
    """Agrégation des indicateurs du tableau de bord."""

    @abstractmethod
    async def get_dashboard_metrics(
        self, owner_id: uuid.UUID, *, now: datetime
    ) -> DashboardMetrics:
        """Indicateurs réels : offres, candidatures, budget IA, recherches et activités récentes."""
