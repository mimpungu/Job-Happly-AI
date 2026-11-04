"""Repository SQLAlchemy pour les documents générés et leurs versions immuables."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.document_generation.application.ports import DocumentRepositoryPort
from app.modules.document_generation.domain.enums import DocumentKind
from app.modules.document_generation.infrastructure.models import (
    DocumentVersionModel,
    GeneratedDocumentModel,
)


class SqlDocumentRepository(DocumentRepositoryPort):
    """Implémentation PostgreSQL / SQLAlchemy du repository de documents."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_document(
        self,
        *,
        owner_id: uuid.UUID,
        kind: DocumentKind,
        title: str,
        language: str,
        offer_id: uuid.UUID | None,
    ) -> GeneratedDocumentModel:
        document = GeneratedDocumentModel(
            owner_id=owner_id,
            kind=kind.value,
            title=title,
            language=language,
            offer_id=offer_id,
        )
        self._session.add(document)
        await self._session.flush()
        return document

    async def get_document(
        self, *, owner_id: uuid.UUID, document_id: uuid.UUID
    ) -> GeneratedDocumentModel | None:
        stmt = select(GeneratedDocumentModel).where(
            GeneratedDocumentModel.id == document_id,
            GeneratedDocumentModel.owner_id == owner_id,
        )
        return await self._session.scalar(stmt)

    async def list_documents(
        self,
        *,
        owner_id: uuid.UUID,
        kind: DocumentKind | None = None,
        offer_id: uuid.UUID | None = None,
    ) -> Sequence[GeneratedDocumentModel]:
        stmt = (
            select(GeneratedDocumentModel)
            .where(GeneratedDocumentModel.owner_id == owner_id)
            .order_by(GeneratedDocumentModel.created_at.desc())
        )
        if kind is not None:
            stmt = stmt.where(GeneratedDocumentModel.kind == kind.value)
        if offer_id is not None:
            stmt = stmt.where(GeneratedDocumentModel.offer_id == offer_id)

        result = await self._session.scalars(stmt)
        return result.all()

    async def add_version(
        self,
        *,
        owner_id: uuid.UUID,
        document_id: uuid.UUID,
        latex_source: str,
        storage_key: str,
        sha256: str,
        size_bytes: int,
        ats_report: dict[str, Any] | None,
    ) -> DocumentVersionModel:
        # Calcul du numéro de version suivant
        max_v_stmt = select(func.coalesce(func.max(DocumentVersionModel.version), 0)).where(
            DocumentVersionModel.document_id == document_id,
            DocumentVersionModel.owner_id == owner_id,
        )
        derniere_version = (await self._session.scalar(max_v_stmt)) or 0
        nouvelle_version = derniere_version + 1

        version_model = DocumentVersionModel(
            owner_id=owner_id,
            document_id=document_id,
            version=nouvelle_version,
            latex_source=latex_source,
            storage_key=storage_key,
            sha256=sha256,
            size_bytes=size_bytes,
            ats_report=ats_report,
        )
        self._session.add(version_model)
        await self._session.flush()
        return version_model

    async def get_version(
        self, *, owner_id: uuid.UUID, document_id: uuid.UUID, version: int
    ) -> DocumentVersionModel | None:
        stmt = select(DocumentVersionModel).where(
            DocumentVersionModel.document_id == document_id,
            DocumentVersionModel.version == version,
            DocumentVersionModel.owner_id == owner_id,
        )
        return await self._session.scalar(stmt)

    async def list_versions(
        self, *, owner_id: uuid.UUID, document_id: uuid.UUID
    ) -> Sequence[DocumentVersionModel]:
        stmt = (
            select(DocumentVersionModel)
            .where(
                DocumentVersionModel.document_id == document_id,
                DocumentVersionModel.owner_id == owner_id,
            )
            .order_by(DocumentVersionModel.version.asc())
        )
        result = await self._session.scalars(stmt)
        return result.all()

