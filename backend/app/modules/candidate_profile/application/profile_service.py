"""Cas d'usage du profil maître : brouillon, validation, versions et journal."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from app.modules.candidate_profile.domain.enums import DataOrigin, ProfileStatus
from app.modules.candidate_profile.domain.profile import (
    Change,
    ProfileDocument,
    diff_documents,
    item_issues,
    validation_issues,
)
from app.modules.candidate_profile.domain.repository import (
    ChangeRecord,
    DraftExistsError,
    NoDraftError,
    ProfileIncompleteError,
    ProfileMeta,
    ProfileNotFoundError,
    ProfileRepository,
    StoredProfile,
)


def _maintenant() -> datetime:
    return datetime.now(UTC)


def _compte(document: ProfileDocument) -> dict[str, int]:
    return {
        "experiences": len(document.experiences),
        "educations": len(document.educations),
        "skills": len(document.skills),
        "languages": len(document.languages),
        "certifications": len(document.certifications),
    }


def _contient_import(document: ProfileDocument) -> bool:
    elements = (
        *document.experiences,
        *document.educations,
        *document.skills,
        *document.languages,
        *document.certifications,
    )
    return any(e.origin is DataOrigin.IMPORTED for e in elements)


class ProfileService:
    def __init__(
        self, repository: ProfileRepository, *, clock: Callable[[], datetime] = _maintenant
    ) -> None:
        self._repo = repository
        self._clock = clock

    async def current(self, *, owner_id: uuid.UUID) -> StoredProfile | None:
        return await self._repo.latest(owner_id=owner_id)

    async def save_draft(self, *, owner_id: uuid.UUID, document: ProfileDocument) -> StoredProfile:
        """Enregistre le brouillon (le crée à la première sauvegarde).

        Un élément marqué « validé » doit être complet : on ne peut pas confirmer une donnée
        inexploitable. Les autres éléments restent libres tant que le profil n'est pas validé.
        """
        problemes = item_issues(document, only_validated=True)
        if problemes:
            raise ProfileIncompleteError(problemes)
        maintenant = self._clock()
        courant = await self._repo.latest(owner_id=owner_id)

        if courant is None:
            stocke = await self._repo.create_version(
                owner_id=owner_id, document=document, version=1, now=maintenant
            )
            action = "import" if _contient_import(document) else "create"
            label = (
                "Brouillon créé à partir d'un CV importé"
                if action == "import"
                else "Brouillon créé"
            )
            changement = Change(
                entity_type="profile",
                entity_id=None,
                action=action,
                label=label,
                changes={"items": [None, _compte(document)]},
            )
            await self._repo.record_changes(
                owner_id=owner_id, profile_id=stocke.meta.id, changes=[changement], now=maintenant
            )
            return stocke

        if courant.meta.status is not ProfileStatus.DRAFT:
            raise NoDraftError(
                "La version actuelle est validée : créez une nouvelle version pour la modifier."
            )
        stocke = await self._repo.replace_content(
            owner_id=owner_id, profile_id=courant.meta.id, document=document, now=maintenant
        )
        await self._repo.record_changes(
            owner_id=owner_id,
            profile_id=courant.meta.id,
            changes=diff_documents(courant.document, document),
            now=maintenant,
        )
        return stocke

    async def start_new_version(self, *, owner_id: uuid.UUID) -> StoredProfile:
        """Ouvre un nouveau brouillon copié de la dernière version validée (jamais écrasée)."""
        courant = await self._repo.latest(owner_id=owner_id)
        if courant is None:
            raise ProfileNotFoundError("Aucun profil à versionner.")
        if courant.meta.status is ProfileStatus.DRAFT:
            raise DraftExistsError("Un brouillon est déjà en cours.")
        maintenant = self._clock()
        nouvelle = courant.meta.version + 1
        stocke = await self._repo.create_version(
            owner_id=owner_id, document=courant.document, version=nouvelle, now=maintenant
        )
        await self._repo.record_changes(
            owner_id=owner_id,
            profile_id=stocke.meta.id,
            changes=[
                Change(
                    entity_type="profile",
                    entity_id=None,
                    action="create",
                    label=f"Version {nouvelle} créée à partir de la version {courant.meta.version}",
                    changes={},
                )
            ],
            now=maintenant,
        )
        return stocke

    async def validate(self, *, owner_id: uuid.UUID) -> StoredProfile:
        """Valide le brouillon : identité complète et tous les éléments confirmés."""
        courant = await self._repo.latest(owner_id=owner_id)
        if courant is None:
            raise ProfileNotFoundError("Aucun profil à valider.")
        if courant.meta.status is not ProfileStatus.DRAFT:
            raise NoDraftError("Cette version est déjà validée.")
        problemes = validation_issues(courant.document)
        if problemes:
            raise ProfileIncompleteError(problemes)
        maintenant = self._clock()
        stocke = await self._repo.mark_validated(
            owner_id=owner_id, profile_id=courant.meta.id, now=maintenant
        )
        await self._repo.record_changes(
            owner_id=owner_id,
            profile_id=courant.meta.id,
            changes=[
                Change(
                    entity_type="profile",
                    entity_id=None,
                    action="validate",
                    label=f"Version {courant.meta.version} validée",
                    changes={},
                )
            ],
            now=maintenant,
        )
        return stocke

    async def versions(self, *, owner_id: uuid.UUID) -> tuple[ProfileMeta, ...]:
        return await self._repo.list_versions(owner_id=owner_id)

    async def version(self, *, owner_id: uuid.UUID, version: int) -> StoredProfile:
        return await self._repo.get_version(owner_id=owner_id, version=version)

    async def history(self, *, owner_id: uuid.UUID, limit: int = 100) -> tuple[ChangeRecord, ...]:
        return await self._repo.list_changes(owner_id=owner_id, limit=limit)
