"""Stockage documentaire sur le système de fichiers local (ADR-0007).

- Noms de fichiers générés (UUID), jamais le nom fourni par l'utilisateur.
- Protection stricte contre les attaques par traversée de chemin.
- Calcul systématique de l'empreinte SHA-256 et de la taille en octets.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import uuid
from pathlib import Path

from app.modules.document_generation.application.ports import DocumentStoragePort


class LocalDocumentStorage(DocumentStoragePort):
    """Implémentation locale de DocumentStoragePort sous un dossier dédié."""

    def __init__(self, base_directory: Path | str = "storage/documents") -> None:
        self._base_directory = Path(base_directory).resolve()
        self._base_directory.mkdir(parents=True, exist_ok=True)

    def _resolve_safe_path(self, storage_key: str) -> Path:
        """Résout le chemin et vérifie l'absence de traversée de répertoire."""
        safe_key = os.path.basename(storage_key)
        if safe_key != storage_key or ".." in storage_key:
            raise ValueError(f"Clé invalide ou tentative de traversée : {storage_key!r}")

        path = (self._base_directory / safe_key).resolve()
        if not path.is_relative_to(self._base_directory):
            raise ValueError(f"Accès hors du répertoire de stockage interdit : {storage_key!r}")
        return path

    async def store(self, content: bytes, *, extension: str = "pdf") -> tuple[str, str, int]:
        """Écrit les octets sous un identifiant unique généré et calcule l'empreinte."""
        cle = f"{uuid.uuid4().hex}.{extension.lstrip('.')}"
        chemin = self._resolve_safe_path(cle)

        sha256 = hashlib.sha256(content).hexdigest()
        taille = len(content)

        await asyncio.to_thread(chemin.write_bytes, content)
        return cle, sha256, taille

    async def read(self, storage_key: str) -> bytes:
        """Lit un artefact existant."""
        chemin = self._resolve_safe_path(storage_key)
        if not chemin.is_file():
            raise FileNotFoundError(f"Fichier introuvable dans le stockage : {storage_key}")
        return await asyncio.to_thread(chemin.read_bytes)

    async def delete(self, storage_key: str) -> None:
        """Supprime un artefact s'il existe."""
        chemin = self._resolve_safe_path(storage_key)
        if chemin.is_file():
            await asyncio.to_thread(chemin.unlink, missing_ok=True)
