"""Droits RGPD : transparence, export, effacement, conservation (TASK-018-18 à 018-22)."""

from __future__ import annotations

import asyncio
import io
import json
import logging
import tempfile
import uuid
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import IO, Any

from app.core.database.session import UnitOfWork
from app.modules.privacy.application.ports import FileStore, PersonalDataStore
from app.modules.privacy.domain.categories import (
    BLOCKED_BY,
    CATEGORY_LABELS,
    CATEGORY_TABLES,
    CONFIRMATION_WORD,
    RETENTION_RULES,
    DataCategory,
)
from app.modules.privacy.domain.exceptions import (
    ConfirmationRequiredError,
    DeletionBlockedError,
    UnknownCategoryError,
)

logger = logging.getLogger("happly.privacy")

ALL = "all"
_SPOOL_BYTES = 32 * 1024 * 1024


@dataclass(frozen=True)
class CategorySummary:
    category: DataCategory
    label: str
    rows: int
    file_bytes: int
    tables: dict[str, int]


@dataclass
class ErasureReport:
    scope: str
    rows_deleted: dict[str, int]
    files_deleted: int = 0
    files_failed: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def total_rows(self) -> int:
        return sum(self.rows_deleted.values())


def _serialiser(valeur: object) -> str:
    if isinstance(valeur, datetime | date):
        return valeur.isoformat()
    if isinstance(valeur, uuid.UUID | Decimal):
        return str(valeur)
    if isinstance(valeur, bytes):
        return f"<{len(valeur)} octets non exportés>"
    return str(valeur)


class PrivacyService:
    def __init__(
        self,
        uow: UnitOfWork,
        store_factory: Callable[[Any], PersonalDataStore],
        files: FileStore,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._uow = uow
        self._store_factory = store_factory
        self._files = files
        self._clock = clock

    # ------------------------------------------------------------ transparence

    async def summary(self, *, owner_id: uuid.UUID) -> list[CategorySummary]:
        """Ce qui est stocké, par catégorie : on ne contrôle que ce que l'on voit."""
        async with self._uow.begin() as session:
            store = self._store_factory(session)
            cles = await store.document_file_keys(owner_id)
            resumes = []
            for categorie, tables in CATEGORY_TABLES.items():
                comptes = await store.count(owner_id, tables)
                taille = 0
                if categorie is DataCategory.DOCUMENTS:
                    taille = sum([(await self._files.size(k)) or 0 for k in cles])
                resumes.append(
                    CategorySummary(
                        category=categorie,
                        label=CATEGORY_LABELS[categorie],
                        rows=sum(comptes.values()),
                        file_bytes=taille,
                        tables=comptes,
                    )
                )
            return resumes

    # ------------------------------------------------------------ export

    async def export_zip(self, *, owner_id: uuid.UUID) -> IO[bytes]:
        """Archive ZIP : un JSON par table, les PDF générés et un manifeste. Fichier temporaire
        (en mémoire jusqu'à 32 Mo puis sur disque) : le client le lit puis le ferme."""
        donnees: dict[str, list[dict[str, Any]]] = {}
        async with self._uow.begin() as session:
            store = self._store_factory(session)
            for categorie, tables in CATEGORY_TABLES.items():
                for table in tables:
                    donnees[f"data/{categorie.value}/{table}.json"] = await store.rows(
                        owner_id, table
                    )
            cles = await store.document_file_keys(owner_id)
            revision = await store.schema_revision()
        fichiers: dict[str, bytes] = {}
        manquants: list[str] = []
        for cle in cles:
            try:
                fichiers[f"files/documents/{cle}"] = await self._files.read(cle)
            except (FileNotFoundError, ValueError):
                manquants.append(cle)
        manifeste = {
            "exported_at": self._clock().isoformat(),
            "schema_revision": revision,
            "format": "happly-export-v1",
            "tables": {chemin: len(lignes) for chemin, lignes in donnees.items()},
            "files": sorted(fichiers),
            "missing_files": manquants,
            "notes": [
                "Les clés d'API et mots de passe ne sont jamais stockés en base : "
                "ils n'apparaissent pas ici.",
                "Les dates sont au format ISO 8601 (UTC ou avec fuseau).",
            ],
        }
        return await asyncio.to_thread(self._assembler, manifeste, donnees, fichiers)

    @staticmethod
    def _assembler(
        manifeste: dict[str, Any],
        donnees: dict[str, list[dict[str, Any]]],
        fichiers: dict[str, bytes],
    ) -> IO[bytes]:
        tampon = tempfile.SpooledTemporaryFile(max_size=_SPOOL_BYTES)  # noqa: SIM115 - rendu à l'appelant
        with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifeste, ensure_ascii=False, indent=2))
            for chemin, lignes in donnees.items():
                archive.writestr(
                    chemin,
                    json.dumps(lignes, ensure_ascii=False, indent=2, default=_serialiser),
                )
            for chemin, contenu in fichiers.items():
                archive.writestr(chemin, io.BytesIO(contenu).getvalue())
        tampon.seek(0)
        return tampon

    # ------------------------------------------------------------ effacement

    async def erase(self, *, owner_id: uuid.UUID, scope: str, confirmation: str) -> ErasureReport:
        """Supprime une catégorie ou tout. Irréversible : la confirmation doit être exacte."""
        if confirmation.strip() != CONFIRMATION_WORD:
            raise ConfirmationRequiredError(
                f"Saisissez « {CONFIRMATION_WORD} » pour confirmer : la suppression est définitive."
            )
        if scope == ALL:
            categories = list(DataCategory)
        else:
            try:
                categories = [DataCategory(scope)]
            except ValueError as erreur:
                raise UnknownCategoryError(f"Catégorie inconnue : {scope!r}.") from erreur

        tables = tuple(t for c in categories for t in CATEGORY_TABLES[c])
        if scope == ALL:
            tables += ("jobs",)  # tâches de fond de l'utilisateur (file technique)
        async with self._uow.begin() as session:
            store = self._store_factory(session)
            if scope != ALL:
                bloquante = BLOCKED_BY.get(categories[0])
                if bloquante and sum(
                    (await store.count(owner_id, CATEGORY_TABLES[bloquante])).values()
                ):
                    raise DeletionBlockedError(
                        f"Supprimez d'abord « {CATEGORY_LABELS[bloquante]} » : "
                        "elles dépendent de cette catégorie."
                    )
            cles: list[str] = []
            if DataCategory.DOCUMENTS in categories:
                cles = await store.document_file_keys(owner_id)
            supprimees = await store.delete(owner_id, tables)
        # Lignes validées : on retire les fichiers (au pire, un fichier orphelin reste).
        rapport = ErasureReport(scope=scope, rows_deleted=supprimees)
        for cle in cles:
            try:
                await self._files.delete(cle)
                rapport.files_deleted += 1
            except (OSError, ValueError):
                rapport.files_failed += 1
        if rapport.files_failed:
            rapport.notes.append(f"{rapport.files_failed} fichier(s) n'ont pas pu être supprimés.")
        logger.info(
            "privacy.erase",
            extra={"scope": scope, "rows": rapport.total_rows, "files": rapport.files_deleted},
        )
        return rapport

    # ------------------------------------------------------------ conservation

    async def purge_expired(self, *, owner_id: uuid.UUID) -> dict[str, int]:
        """Applique la politique de conservation automatique ; renvoie les lignes purgées."""
        maintenant = self._clock()
        async with self._uow.begin() as session:
            store = self._store_factory(session)
            purge = {
                r.table: await store.purge(owner_id, r, maintenant)
                for r in RETENTION_RULES
                if r.automatic
            }
        logger.info("privacy.purge", extra={"rows": sum(purge.values())})
        return purge
