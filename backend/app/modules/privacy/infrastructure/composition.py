from __future__ import annotations

import os
from pathlib import Path

from app.core.config import get_settings
from app.core.database.session import UnitOfWork
from app.modules.document_generation.infrastructure.document_storage import LocalDocumentStorage
from app.modules.privacy.application.service import PrivacyService
from app.modules.privacy.infrastructure.sql_store import SqlPersonalData


class _Fichiers:
    """Fichiers générés : réutilise le stockage documentaire (noms sûrs, anti-traversée)."""

    def __init__(self, base: Path) -> None:
        self._stockage = LocalDocumentStorage(base_directory=base)
        self._base = base

    async def size(self, key: str) -> int | None:
        if os.path.basename(key) != key:
            return None  # clé suspecte : jamais de chemin construit à partir d'elle
        chemin = self._base / key
        try:
            return chemin.stat().st_size if chemin.is_file() else None
        except OSError:
            return None

    async def read(self, key: str) -> bytes:
        return await self._stockage.read(key)

    async def delete(self, key: str) -> None:
        await self._stockage.delete(key)


def build_privacy_service(uow: UnitOfWork) -> PrivacyService:
    base = Path(get_settings().storage_dir) / "documents"
    return PrivacyService(uow, SqlPersonalData, _Fichiers(base))
