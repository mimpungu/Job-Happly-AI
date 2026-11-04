"""Assemblage des services de génération de documents (utilisé par les routes)."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.document_generation.application.cover_letter_service import CoverLetterService
from app.modules.document_generation.application.resume_service import ResumeService
from app.modules.document_generation.infrastructure.document_repository import SqlDocumentRepository
from app.modules.document_generation.infrastructure.document_storage import LocalDocumentStorage
from app.modules.document_generation.infrastructure.generation_inputs import SqlGenerationInputs
from app.modules.document_generation.infrastructure.latex_compiler import IsolatedLaTeXCompiler


def _compiler() -> IsolatedLaTeXCompiler:
    settings = get_settings()
    return IsolatedLaTeXCompiler(
        pdflatex_path=settings.pdflatex_path,
        timeout_seconds=settings.latex_timeout_seconds,
        memory_limit_mb=settings.latex_memory_limit_mb,
    )


def _storage() -> LocalDocumentStorage:
    return LocalDocumentStorage(base_directory=Path(get_settings().storage_dir) / "documents")


def build_resume_service(session: AsyncSession) -> ResumeService:
    return ResumeService(
        repository=SqlDocumentRepository(session),
        storage=_storage(),
        compiler=_compiler(),
        inputs=SqlGenerationInputs(session),
    )


def build_cover_letter_service(session: AsyncSession) -> CoverLetterService:
    return CoverLetterService(
        repository=SqlDocumentRepository(session),
        storage=_storage(),
        compiler=_compiler(),
        inputs=SqlGenerationInputs(session),
    )
