"""Service applicatif du tableau de bord (TASK-014-21, 22).

Agrège les métriques globales de l'application sur des données 100% réelles :
offres trouvées, candidatures envoyées, taux de réponse réel, budget IA consommé.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.application_management.domain.entities import DashboardMetrics
    from app.modules.application_management.domain.ports import DashboardRepositoryPort


class DashboardService:
    """Service d'agrégation des KPIs pour le tableau de bord de pilotage."""

    def __init__(self, repository: DashboardRepositoryPort) -> None:
        self._repository = repository

    async def get_dashboard(self, *, owner_id: uuid.UUID) -> DashboardMetrics:
        """Calcule et retourne les métriques globales pour l'utilisateur."""
        return await self._repository.get_dashboard_metrics(owner_id)

