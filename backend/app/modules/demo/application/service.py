"""Mode démonstration (TASK-002-10) : données fictives, explicites et jamais mêlées au réel."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from app.modules.demo.application.ports import DemoRepositoryPort, FileDeleterPort
from app.modules.demo.domain.catalogue import DEMO_OFFERS
from app.modules.demo.domain.exceptions import DemoModeActiveError, RealDataPresentError

logger = logging.getLogger("happly.demo")


@dataclass(frozen=True)
class DemoStatus:
    enabled: bool
    offers: int
    applications: int


class DemoService:
    def __init__(
        self,
        repository: DemoRepositoryPort,
        files: FileDeleterPort,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repository = repository
        self._files = files
        self._clock = clock

    async def status(self, owner_id: uuid.UUID) -> DemoStatus:
        compte = await self._repository.demo_counts(owner_id)
        return DemoStatus(compte.offers > 0, compte.offers, compte.applications)

    async def enable(self, owner_id: uuid.UUID) -> DemoStatus:
        """Idempotent. Refusé si des données réelles existent : on ne mélange jamais."""
        if (await self.status(owner_id)).enabled:
            return await self.status(owner_id)
        reel = await self._repository.real_counts(owner_id)
        if reel.offers or reel.applications:
            raise RealDataPresentError(
                "Le mode démonstration n'est disponible que sans offre ni candidature réelle : "
                "il ne se mélange jamais à vos données."
            )
        await self._repository.add_offers(owner_id, DEMO_OFFERS, now=self._clock())
        logger.info("demo.enable", extra={"offers": len(DEMO_OFFERS)})
        return await self.status(owner_id)

    async def disable(self, owner_id: uuid.UUID) -> DemoStatus:
        """Retire toutes les données fictives (et ce qui en dérive), sans toucher au réel."""
        retrait = await self._repository.remove_all(owner_id)
        for cle in retrait.file_keys:
            try:
                await self._files.delete(cle)
            except (OSError, ValueError):
                logger.warning("demo.file_not_deleted")
        logger.info(
            "demo.disable", extra={"offers": retrait.offers, "applications": retrait.applications}
        )
        return await self.status(owner_id)

    async def ensure_inactive(self, owner_id: uuid.UUID) -> None:
        """Garde des routes qui créeraient des données réelles pendant la démonstration."""
        if (await self.status(owner_id)).enabled:
            raise DemoModeActiveError(
                "Le mode démonstration est actif : désactivez-le avant d'ajouter des données "
                "réelles."
            )
