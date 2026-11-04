"""Ports (interfaces abstraites) pour la génération, la compilation et le stockage de documents."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from app.modules.document_generation.domain.enums import DocumentKind

if TYPE_CHECKING:
    from app.modules.candidate_profile.domain.profile import ProfileDocument
    from app.modules.document_generation.infrastructure.models import (
        DocumentVersionModel,
        GeneratedDocumentModel,
    )


class LaTeXCompilationError(Exception):
    """Erreur survenue pendant la compilation LaTeX."""

    def __init__(self, message: str, log_snippet: str | None = None) -> None:
        super().__init__(message)
        self.log_snippet = log_snippet


class CompilationTimeoutError(LaTeXCompilationError):
    """La compilation a dépassé le délai limite alloué (TASK-012-15)."""


class LaTeXSourceTooLargeError(ValueError):
    """Le fichier LaTeX dépasse la taille maximale autorisée (TASK-012-15)."""


class UnsafeLaTeXSourceError(LaTeXCompilationError):
    """La source contient une commande interdite (lecture de fichier, exécution…)."""


class CompilerUnavailableError(Exception):
    """pdfLaTeX n'est pas installé ou introuvable : erreur d'environnement, pas de saisie."""


class DocumentNotFoundError(LookupError):
    """Le document demandé n'existe pas ou n'appartient pas à l'utilisateur."""


class DocumentVersionNotFoundError(LookupError):
    """La version demandée n'existe pas pour ce document."""


class NoValidatedProfileError(Exception):
    """Aucun profil maître validé : un CV ne peut être généré que depuis des données confirmées."""


class OfferNotFoundError(LookupError):
    """L'offre ciblée n'existe pas ou n'appartient pas à l'utilisateur."""


@dataclass(frozen=True)
class OfferContext:
    """Ce que la génération de document a besoin de savoir d'une offre."""

    title: str
    company: str | None
    description: str
    required_skills: tuple[str, ...]
    """Compétences issues de l'analyse de l'offre, de la plus à la moins exigée."""
    location: str | None = None
    country_code: str | None = None


class GenerationInputsPort(Protocol):
    """Lecture des données sources d'un document : profil validé et offre analysée."""

    async def validated_profile(self, *, owner_id: uuid.UUID) -> ProfileDocument:
        """Dernier profil validé. Lève `NoValidatedProfileError` s'il n'y en a pas."""
        ...

    async def offer_context(self, *, owner_id: uuid.UUID, offer_id: uuid.UUID) -> OfferContext:
        """Offre et compétences analysées. Lève `OfferNotFoundError`."""
        ...


class LaTeXCompilerPort(Protocol):
    """Contrat de compilation pdfLaTeX isolé (FEATURE 012.3)."""

    async def compile(self, latex_source: str) -> bytes:
        """Compile une source LaTeX en binaire PDF dans un environnement isolé."""
        ...


class DocumentStoragePort(Protocol):
    """Stockage persistant des artefacts documentaires (PDF, LaTeX) (ADR-0007)."""

    async def store(self, content: bytes, *, extension: str = "pdf") -> tuple[str, str, int]:
        """Écrit le contenu sur disque, retourne (storage_key, sha256, size_bytes)."""
        ...

    async def read(self, storage_key: str) -> bytes:
        """Lit un artefact à partir de sa clé de stockage."""
        ...

    async def delete(self, storage_key: str) -> None:
        """Supprime un artefact."""
        ...


class DocumentRepositoryPort(Protocol):
    """Persistance des métadonnées de documents et de leurs versions."""

    async def create_document(
        self,
        *,
        owner_id: uuid.UUID,
        kind: DocumentKind,
        title: str,
        language: str,
        offer_id: uuid.UUID | None,
    ) -> GeneratedDocumentModel: ...

    async def get_document(
        self, *, owner_id: uuid.UUID, document_id: uuid.UUID
    ) -> GeneratedDocumentModel | None: ...

    async def list_documents(
        self,
        *,
        owner_id: uuid.UUID,
        kind: DocumentKind | None = None,
        offer_id: uuid.UUID | None = None,
    ) -> Sequence[GeneratedDocumentModel]: ...

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
    ) -> DocumentVersionModel: ...

    async def get_version(
        self, *, owner_id: uuid.UUID, document_id: uuid.UUID, version: int
    ) -> DocumentVersionModel | None: ...

    async def list_versions(
        self, *, owner_id: uuid.UUID, document_id: uuid.UUID
    ) -> Sequence[DocumentVersionModel]: ...
