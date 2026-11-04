"""Assemblage du service de génération de documents (utilisé par les routes)."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.document_generation.application.cover_letter_service import CoverLetterService
from app.modules.document_generation.application.resume_service import ResumeService
from app.modules.document_generation.infrastructure.document_repository import SqlDocumentRepository
from app.modules.document_generation.infrastructure.document_storage import LocalDocumentStorage
from app.modules.document_generation.infrastructure.latex_compiler import IsolatedLaTeXCompiler


def build_resume_service(session: AsyncSession) -> ResumeService:
    settings = get_settings()
    repository = SqlDocumentRepository(session)
    storage = LocalDocumentStorage(base_directory=Path(settings.storage_dir) / "documents")
    compiler = IsolatedLaTeXCompiler(
        pdflatex_path=settings.pdflatex_path,
        timeout_seconds=settings.latex_timeout_seconds,
    )
    return ResumeService(repository=repository, storage=storage, compiler=compiler)


def build_cover_letter_service(session: AsyncSession) -> CoverLetterService:
    settings = get_settings()
    repository = SqlDocumentRepository(session)
    storage = LocalDocumentStorage(base_directory=Path(settings.storage_dir) / "documents")
    compiler = IsolatedLaTeXCompiler(
        pdflatex_path=settings.pdflatex_path,
        timeout_seconds=settings.latex_timeout_seconds,
    )
    return CoverLetterService(repository=repository, storage=storage, compiler=compiler)
