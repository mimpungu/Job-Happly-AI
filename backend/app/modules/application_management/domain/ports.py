"""Interfaces de persistance (ports) pour le suivi des candidatures (EPIC 014)."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.application_management.domain.entities import (
        ApplicationAggregate,
        ApplicationStats,
        ContactInfo,
        DashboardMetrics,
        TimelineEvent,
    )
    from app.modules.application_management.domain.enums import ApplicationStatus


class ApplicationRepositoryPort(ABC):
    """Port de persistance pour les candidatures, l'historique et les contacts."""

    @abstractmethod
    async def get_by_id(
        self, owner_id: uuid.UUID, application_id: uuid.UUID
    ) -> ApplicationAggregate | None:
        """Récupère une candidature complète par son identifiant et son propriétaire."""

    @abstractmethod
    async def get_by_offer_id(
        self, owner_id: uuid.UUID, offer_id: uuid.UUID
    ) -> ApplicationAggregate | None:
        """Récupère une candidature par son identifiant d'offre et son propriétaire."""

    @abstractmethod
    async def create(
        self,
        owner_id: uuid.UUID,
        offer_id: uuid.UUID,
        status: ApplicationStatus = ...,
    ) -> ApplicationAggregate:
        """Crée une nouvelle candidature associée à une offre."""

    @abstractmethod
    async def update_status(
        self,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        new_status: ApplicationStatus,
        applied_at: datetime | None = None,
        response_received_at: datetime | None = None,
    ) -> ApplicationAggregate:
        """Met à jour le statut d'une candidature."""

    @abstractmethod
    async def update_follow_up(
        self,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        follow_up_at: datetime | None,
    ) -> ApplicationAggregate:
        """Met à jour la date de relance."""

    @abstractmethod
    async def attach_documents(
        self,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        cv_version_id: uuid.UUID | None = None,
        letter_version_id: uuid.UUID | None = None,
    ) -> ApplicationAggregate:
        """Associe les versions de documents (CV et/ou lettre) à la candidature."""

    @abstractmethod
    async def add_event(
        self,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        event: TimelineEvent,
    ) -> TimelineEvent:
        """Ajoute un événement d'historique (changement de statut, note, entretien)."""

    @abstractmethod
    async def add_contact(
        self,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        contact: ContactInfo,
    ) -> ContactInfo:
        """Ajoute ou met à jour les coordonnées d'un contact."""

    @abstractmethod
    async def list_applications(
        self,
        owner_id: uuid.UUID,
        status: ApplicationStatus | None = None,
        company_query: str | None = None,
        title_query: str | None = None,
        has_follow_up_due: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ApplicationAggregate], int]:
        """Liste les candidatures avec filtres et pagination (vue tableau)."""

    @abstractmethod
    async def list_for_kanban(
        self,
        owner_id: uuid.UUID,
    ) -> dict[ApplicationStatus, list[ApplicationAggregate]]:
        """Récupère l'ensemble des candidatures regroupées par statut (vue Kanban)."""

    @abstractmethod
    async def get_stats(
        self,
        owner_id: uuid.UUID,
    ) -> ApplicationStats:
        """Calcule les statistiques consolidées sur données réelles."""


class DashboardRepositoryPort(ABC):
    """Port de persistance pour les métriques de synthèse du tableau de bord (TASK-014-21)."""

    @abstractmethod
    async def get_dashboard_metrics(
        self,
        owner_id: uuid.UUID,
    ) -> DashboardMetrics:
        """Agrège les métriques globales réelles (offres, candidatures, budget IA)."""

