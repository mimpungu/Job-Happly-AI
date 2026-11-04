"""Persistance des préférences. Ne valide jamais la transaction (rôle de l'unité de travail)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.localization.domain.preferences import Preferences
from app.modules.localization.infrastructure.models import UserPreferencesModel


class SqlPreferencesRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, owner_id: uuid.UUID) -> Preferences:
        """Préférences enregistrées, ou valeurs neutres si l'utilisateur n'a rien réglé."""
        modele = await self._modele(owner_id)
        if modele is None:
            return Preferences()
        return Preferences(
            ui_language=modele.ui_language,
            country_code=modele.country_code,
            currency=modele.currency,
            timezone=modele.timezone,
            willing_to_relocate=modele.willing_to_relocate,
            target_countries=tuple(modele.target_countries),
            work_permit_countries=tuple(modele.work_permit_countries),
            needs_sponsorship=modele.needs_sponsorship,
        )

    async def save(self, owner_id: uuid.UUID, prefs: Preferences) -> None:
        modele = await self._modele(owner_id)
        if modele is None:
            modele = UserPreferencesModel(owner_id=owner_id)
            self._session.add(modele)
        modele.ui_language = prefs.ui_language
        modele.country_code = prefs.country_code
        modele.currency = prefs.currency
        modele.timezone = prefs.timezone
        modele.willing_to_relocate = prefs.willing_to_relocate
        modele.target_countries = list(prefs.target_countries)
        modele.work_permit_countries = list(prefs.work_permit_countries)
        modele.needs_sponsorship = prefs.needs_sponsorship
        await self._session.flush()

    async def _modele(self, owner_id: uuid.UUID) -> UserPreferencesModel | None:
        return (
            await self._session.execute(
                select(UserPreferencesModel).where(UserPreferencesModel.owner_id == owner_id)
            )
        ).scalar_one_or_none()
