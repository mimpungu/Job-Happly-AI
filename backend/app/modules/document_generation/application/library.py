"""Consultation, export et comparaison des documents générés, communes au CV et à la lettre."""

from __future__ import annotations

import difflib
import uuid
from typing import TYPE_CHECKING

from app.modules.document_generation.application.ports import (
    DocumentNotFoundError,
    DocumentRepositoryPort,
    DocumentStoragePort,
    DocumentVersionNotFoundError,
)
from app.modules.document_generation.domain.enums import DocumentKind
from app.modules.document_generation.domain.models import DocumentComparison

if TYPE_CHECKING:
    from app.modules.document_generation.infrastructure.models import (
        DocumentVersionModel,
        GeneratedDocumentModel,
    )


class DocumentLibrary:
    """Accès aux documents d'un seul type : un CV n'est jamais servi comme une lettre."""

    def __init__(
        self, repository: DocumentRepositoryPort, storage: DocumentStoragePort, kind: DocumentKind
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._kind = kind

    async def get_document(
        self, *, owner_id: uuid.UUID, document_id: uuid.UUID
    ) -> GeneratedDocumentModel:
        document = await self._repository.get_document(owner_id=owner_id, document_id=document_id)
        if document is None or document.kind != self._kind.value:
            raise DocumentNotFoundError(str(document_id))
        return document

    async def list_documents(
        self, *, owner_id: uuid.UUID, offer_id: uuid.UUID | None = None
    ) -> list[GeneratedDocumentModel]:
        documents = await self._repository.list_documents(
            owner_id=owner_id, kind=self._kind, offer_id=offer_id
        )
        return list(documents)

    async def list_versions(
        self, *, owner_id: uuid.UUID, document_id: uuid.UUID
    ) -> list[DocumentVersionModel]:
        versions = await self._repository.list_versions(owner_id=owner_id, document_id=document_id)
        return list(versions)

    async def get_version(
        self, *, owner_id: uuid.UUID, document_id: uuid.UUID, version: int
    ) -> tuple[GeneratedDocumentModel, DocumentVersionModel]:
        document = await self.get_document(owner_id=owner_id, document_id=document_id)
        found = await self._repository.get_version(
            owner_id=owner_id, document_id=document_id, version=version
        )
        if found is None:
            raise DocumentVersionNotFoundError(f"{document_id} v{version}")
        return document, found

    async def download_pdf(
        self, *, owner_id: uuid.UUID, document_id: uuid.UUID, version: int
    ) -> tuple[bytes, str]:
        """Octets du PDF et nom de fichier suggéré."""
        document, found = await self.get_version(
            owner_id=owner_id, document_id=document_id, version=version
        )
        try:
            pdf_bytes = await self._storage.read(found.storage_key)
        except FileNotFoundError as err:
            raise DocumentVersionNotFoundError(f"PDF absent du stockage : {document_id}") from err
        return pdf_bytes, f"{safe_stem(document.title)}_v{version}.pdf"

    async def download_latex(
        self, *, owner_id: uuid.UUID, document_id: uuid.UUID, version: int
    ) -> tuple[str, str]:
        """Source LaTeX et nom de fichier suggéré."""
        document, found = await self.get_version(
            owner_id=owner_id, document_id=document_id, version=version
        )
        if not found.latex_source:
            raise DocumentVersionNotFoundError(f"Source LaTeX absente : {document_id} v{version}")
        return found.latex_source, f"{safe_stem(document.title)}_v{version}.tex"

    async def compare_versions(
        self, *, owner_id: uuid.UUID, document_id: uuid.UUID, version_a: int, version_b: int
    ) -> DocumentComparison:
        """Diff LaTeX et écart de score entre deux versions."""
        _, ver_a = await self.get_version(
            owner_id=owner_id, document_id=document_id, version=version_a
        )
        _, ver_b = await self.get_version(
            owner_id=owner_id, document_id=document_id, version=version_b
        )
        diff = difflib.unified_diff(
            (ver_a.latex_source or "").splitlines(keepends=True),
            (ver_b.latex_source or "").splitlines(keepends=True),
            fromfile=f"v{version_a}.tex",
            tofile=f"v{version_b}.tex",
        )
        return DocumentComparison(
            document_id=document_id,
            version_a=version_a,
            version_b=version_b,
            diff_latex="".join(diff),
            score_a=ver_a.ats_report.get("score") if ver_a.ats_report else None,
            score_b=ver_b.ats_report.get("score") if ver_b.ats_report else None,
            size_diff_bytes=ver_b.size_bytes - ver_a.size_bytes,
        )


def safe_stem(title: str) -> str:
    """Nom de fichier : lettres, chiffres, tirets et espaces ; jamais vide."""
    nettoye = "".join(c for c in title if c.isalnum() or c in "-_ ").strip()
    return nettoye or "Document"
