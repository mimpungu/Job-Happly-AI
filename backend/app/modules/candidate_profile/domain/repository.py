"""Contrat de persistance du profil maître et erreurs métier associées."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from app.modules.candidate_profile.domain.enums import ProfileStatus
from app.modules.candidate_profile.domain.profile import Change, Issue, ProfileDocument


class ProfileNotFoundError(LookupError):
    """Aucun profil (ou aucune version) pour ce propriétaire."""


class NoDraftError(RuntimeError):
    """La dernière version est validée : créez d'abord une nouvelle version pour la modifier."""


class DraftExistsError(RuntimeError):
    """Un brouillon est déjà en cours : on ne crée pas une seconde version."""


class UnknownItemError(ValueError):
    """Un `id` d'élément ne correspond à aucun élément de ce brouillon."""


class ProfileIncompleteError(ValueError):
    """Le profil ne peut pas être enregistré ou validé tel quel."""

    def __init__(self, issues: list[Issue]) -> None:
        super().__init__("Profil incomplet.")
        self.issues = issues


@dataclass(frozen=True, slots=True)
class ProfileMeta:
    id: uuid.UUID
    version: int
    status: ProfileStatus
    created_at: datetime
    updated_at: datetime
    validated_at: datetime | None


@dataclass(frozen=True, slots=True)
class StoredProfile:
    meta: ProfileMeta
    document: ProfileDocument


@dataclass(frozen=True, slots=True)
class ChangeRecord:
    id: uuid.UUID
    profile_version: int
    created_at: datetime
    entity_type: str
    entity_id: uuid.UUID | None
    action: str
    label: str | None
    changes: dict[str, Any]


class ProfileRepository(Protocol):
    async def latest(self, *, owner_id: uuid.UUID) -> StoredProfile | None: ...

    async def get_version(self, *, owner_id: uuid.UUID, version: int) -> StoredProfile: ...

    async def list_versions(self, *, owner_id: uuid.UUID) -> tuple[ProfileMeta, ...]: ...

    async def create_version(
        self, *, owner_id: uuid.UUID, document: ProfileDocument, version: int, now: datetime
    ) -> StoredProfile:
        """Crée un brouillon ; tous les éléments reçoivent de nouveaux identifiants."""
        ...

    async def replace_content(
        self,
        *,
        owner_id: uuid.UUID,
        profile_id: uuid.UUID,
        document: ProfileDocument,
        now: datetime,
    ) -> StoredProfile:
        """Remplace le contenu d'un brouillon, élément par élément (appariés par `id`)."""
        ...

    async def mark_validated(
        self, *, owner_id: uuid.UUID, profile_id: uuid.UUID, now: datetime
    ) -> StoredProfile: ...

    async def record_changes(
        self,
        *,
        owner_id: uuid.UUID,
        profile_id: uuid.UUID,
        changes: list[Change],
        now: datetime,
    ) -> None: ...

    async def list_changes(
        self, *, owner_id: uuid.UUID, limit: int
    ) -> tuple[ChangeRecord, ...]: ...
