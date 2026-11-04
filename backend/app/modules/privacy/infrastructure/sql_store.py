"""Accès SQL aux données d'un propriétaire, piloté par les métadonnées du schéma.

Les tables sont résolues depuis `Base.metadata` (jamais de SQL assemblé à partir d'un nom fourni
par le client) et traitées dans l'ordre inverse des dépendances de clés étrangères.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Table, delete, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.registry import metadata
from app.modules.document_generation.infrastructure.models import DocumentVersionModel
from app.modules.privacy.domain.categories import RetentionRule

_ORDRE_SUPPRESSION = {t.name: i for i, t in enumerate(reversed(metadata.sorted_tables))}


def _table(nom: str) -> Table:
    table = metadata.tables.get(nom)
    if table is None or "owner_id" not in table.c:
        raise ValueError(f"Table inconnue ou sans propriétaire : {nom!r}")
    return table


class SqlPersonalData:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def count(self, owner_id: uuid.UUID, tables: tuple[str, ...]) -> dict[str, int]:
        comptes: dict[str, int] = {}
        for nom in tables:
            t = _table(nom)
            comptes[nom] = (
                await self._session.scalar(
                    select(func.count()).select_from(t).where(t.c.owner_id == owner_id)
                )
            ) or 0
        return comptes

    async def rows(self, owner_id: uuid.UUID, table: str) -> list[dict[str, Any]]:
        t = _table(table)
        resultat = await self._session.execute(select(t).where(t.c.owner_id == owner_id))
        return [dict(ligne._mapping) for ligne in resultat]

    async def delete(self, owner_id: uuid.UUID, tables: tuple[str, ...]) -> dict[str, int]:
        supprimees: dict[str, int] = {}
        for nom in sorted(tables, key=lambda n: _ORDRE_SUPPRESSION.get(n, 0)):
            t = _table(nom)
            resultat = await self._session.execute(delete(t).where(t.c.owner_id == owner_id))
            supprimees[nom] = resultat.rowcount  # type: ignore[attr-defined]
        return supprimees

    async def document_file_keys(self, owner_id: uuid.UUID) -> list[str]:
        cles = await self._session.scalars(
            select(DocumentVersionModel.storage_key).where(
                DocumentVersionModel.owner_id == owner_id,
                DocumentVersionModel.storage_key.is_not(None),
            )
        )
        return [c for c in cles if c]

    async def schema_revision(self) -> str | None:
        revision = await self._session.scalar(
            text("SELECT version_num FROM alembic_version LIMIT 1")
        )
        return str(revision) if revision is not None else None

    async def purge(self, owner_id: uuid.UUID, rule: RetentionRule, now: datetime) -> int:
        if rule.days is None:
            return 0
        coupure = now - timedelta(days=rule.days)
        t = metadata.tables[rule.table]
        condition: Any
        if rule.table == "ai_cache_entries":
            condition = or_(t.c.expires_at < now, t.c.created_at < coupure)
        elif rule.table == "notifications":
            condition = t.c.read_at.is_not(None) & (t.c.read_at < coupure)
        elif rule.table == "search_runs":
            condition = t.c.started_at < coupure
        elif rule.table == "jobs":
            condition = t.c.status.in_(("succeeded", "failed", "dead")) & (
                t.c.finished_at < coupure
            )
            # Les tâches système n'ont pas de propriétaire : elles suivent la même rétention.
            resultat = await self._session.execute(
                delete(t).where(condition, or_(t.c.owner_id == owner_id, t.c.owner_id.is_(None)))
            )
            return resultat.rowcount  # type: ignore[attr-defined, no-any-return]
        else:
            condition = t.c.created_at < coupure
        resultat = await self._session.execute(delete(t).where(condition, t.c.owner_id == owner_id))
        return resultat.rowcount  # type: ignore[attr-defined, no-any-return]
