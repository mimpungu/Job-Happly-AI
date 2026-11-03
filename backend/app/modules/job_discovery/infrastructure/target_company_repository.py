"""Persistance des entreprises suivies. Ne valide jamais la transaction."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.job_discovery.domain.target_company import (
    AtsKind,
    DetectedSource,
    DetectionStatus,
    detect_from_url,
)
from app.modules.job_discovery.infrastructure.models import TargetCompanyModel


class TargetCompanyError(ValueError):
    """Opération refusée sur une entreprise suivie."""


class TargetCompanyNotFoundError(LookupError):
    """Entreprise suivie inexistante (ou appartenant à un autre utilisateur)."""


class SqlTargetCompanyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self, owner_id: uuid.UUID, *, name: str, careers_url: str | None, now: datetime
    ) -> TargetCompanyModel:
        """Ajoute une entreprise (désactivée) et tente de reconnaître sa source publique."""
        nom = name.strip()
        if not nom:
            raise TargetCompanyError("Le nom de l'entreprise est obligatoire.")
        entreprise = TargetCompanyModel(
            owner_id=owner_id, name=nom, careers_url=(careers_url or "").strip() or None
        )
        if entreprise.careers_url and (detectee := detect_from_url(entreprise.careers_url)):
            self._appliquer(entreprise, detectee, now)
        try:
            # Point de sauvegarde : un doublon ne doit pas invalider la transaction de la requête.
            async with self._session.begin_nested():
                self._session.add(entreprise)
        except IntegrityError as erreur:
            raise TargetCompanyError("Cette entreprise est déjà suivie.") from erreur
        return entreprise

    async def get(self, owner_id: uuid.UUID, company_id: uuid.UUID) -> TargetCompanyModel:
        requete = select(TargetCompanyModel).where(
            TargetCompanyModel.owner_id == owner_id, TargetCompanyModel.id == company_id
        )
        entreprise = (await self._session.execute(requete)).scalar_one_or_none()
        if entreprise is None:
            raise TargetCompanyNotFoundError(str(company_id))
        return entreprise

    async def list(self, owner_id: uuid.UUID) -> list[TargetCompanyModel]:
        requete = (
            select(TargetCompanyModel)
            .where(TargetCompanyModel.owner_id == owner_id)
            .order_by(TargetCompanyModel.name)
        )
        return list((await self._session.execute(requete)).scalars())

    async def set_enabled(self, entreprise: TargetCompanyModel, enabled: bool) -> None:
        if enabled and entreprise.detection_status != DetectionStatus.SUPPORTED.value:
            raise TargetCompanyError(
                "Source non supportée ou non détectée : impossible d'activer cette entreprise."
            )
        if (
            enabled
            and entreprise.ats_kind == AtsKind.CAREERS_PAGE.value
            and entreprise.tos_verified_at is None
        ):
            raise TargetCompanyError(
                "Les conditions d'utilisation du site doivent être vérifiées avant activation."
            )
        entreprise.enabled = enabled
        await self._session.flush()

    async def mark_unsupported(
        self, entreprise: TargetCompanyModel, reason: str, now: datetime
    ) -> None:
        """Une source qui refuse l'accès devient « non supportée » : jamais contournée."""
        entreprise.ats_kind = AtsKind.UNSUPPORTED.value
        entreprise.detection_status = DetectionStatus.UNSUPPORTED.value
        entreprise.detection_method = reason[:40]
        entreprise.detected_at = now
        entreprise.enabled = False
        await self._session.flush()

    @staticmethod
    def _appliquer(entreprise: TargetCompanyModel, source: DetectedSource, now: datetime) -> None:
        entreprise.ats_kind = source.ats_kind.value
        entreprise.ats_token = source.token
        entreprise.ats_region = source.region
        entreprise.detection_method = source.method
        entreprise.detection_status = DetectionStatus.SUPPORTED.value
        entreprise.detected_at = now
