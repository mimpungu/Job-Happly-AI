"""Persistance de l'état des sources (activation, santé). Ne valide jamais la transaction."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.job_discovery.domain.connector import (
    HealthState,
    HealthStatus,
    JobSourceConnector,
)
from app.modules.job_discovery.domain.enums import SourceKind
from app.modules.job_discovery.infrastructure.models import JobSourceModel

MANUAL_SOURCE_KEY = "manual"


class SqlJobSourceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def sync_from_connector(
        self, owner_id: uuid.UUID, connector: JobSourceConnector
    ) -> JobSourceModel:
        """Crée la source si besoin ; ne change jamais son activation (choix de l'utilisateur)."""
        modele = await self._by_key(owner_id, connector.key)
        capacites = connector.get_capabilities()
        if modele is None:
            modele = JobSourceModel(owner_id=owner_id, key=connector.key, enabled=False)
            self._session.add(modele)
        modele.name = connector.name
        modele.kind = connector.kind.value
        modele.countries = sorted(capacites.countries)
        modele.requires_api_key = capacites.requires_credentials
        await self._session.flush()
        return modele

    async def ensure_manual(self, owner_id: uuid.UUID) -> JobSourceModel:
        """Source des offres saisies à la main : créée une fois, toujours active."""
        modele = await self._by_key(owner_id, MANUAL_SOURCE_KEY)
        if modele is None:
            modele = JobSourceModel(
                owner_id=owner_id,
                key=MANUAL_SOURCE_KEY,
                name="Saisie manuelle",
                kind=SourceKind.MANUAL.value,
                enabled=True,
            )
            self._session.add(modele)
            await self._session.flush()
        return modele

    async def set_enabled(self, owner_id: uuid.UUID, key: str, enabled: bool) -> None:
        modele = await self._require(owner_id, key)
        modele.enabled = enabled
        await self._session.flush()

    async def record_health(self, owner_id: uuid.UUID, key: str, status: HealthStatus) -> None:
        modele = await self._require(owner_id, key)
        modele.last_checked_at = status.checked_at
        if status.state is HealthState.OK:
            modele.last_success_at = status.checked_at
            modele.last_error = None
        else:
            modele.last_error = f"{status.state.value}: {status.detail or 'sans détail'}"
        await self._session.flush()

    async def last_checked_at(self, owner_id: uuid.UUID, key: str) -> datetime | None:
        return (await self._require(owner_id, key)).last_checked_at

    async def _by_key(self, owner_id: uuid.UUID, key: str) -> JobSourceModel | None:
        requete = select(JobSourceModel).where(
            JobSourceModel.owner_id == owner_id, JobSourceModel.key == key
        )
        return (await self._session.execute(requete)).scalar_one_or_none()

    async def _require(self, owner_id: uuid.UUID, key: str) -> JobSourceModel:
        modele = await self._by_key(owner_id, key)
        if modele is None:
            raise LookupError(f"Source inconnue : {key!r}")
        return modele
