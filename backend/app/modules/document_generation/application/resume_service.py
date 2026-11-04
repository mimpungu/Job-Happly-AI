"""Service applicatif pour la génération, la compilation et la gestion des versions de CV."""

from __future__ import annotations

import difflib
import uuid
from typing import TYPE_CHECKING

from app.modules.document_generation.application.ports import (
    DocumentRepositoryPort,
    DocumentStoragePort,
    LaTeXCompilerPort,
)
from app.modules.document_generation.domain.ats_analyzer import analyze_pdf_ats
from app.modules.document_generation.domain.content_selection import (
    adapt_resume_content,
    build_generation_context,
)
from app.modules.document_generation.domain.enums import DocumentKind
from app.modules.document_generation.domain.fact_checker import assert_facts_verified
from app.modules.document_generation.domain.models import (
    ATSReport,
    DocumentComparison,
    ResumeGenerationOptions,
)
from app.modules.document_generation.domain.templates import render_latex_resume

if TYPE_CHECKING:
    from app.modules.candidate_profile.domain.profile import ProfileDocument
    from app.modules.document_generation.infrastructure.models import (
        DocumentVersionModel,
        GeneratedDocumentModel,
    )


class ResumeService:
    """Orchestrateur du cycle de vie des CV LaTeX : compilation, versionnage et export."""

    def __init__(
        self,
        repository: DocumentRepositoryPort,
        storage: DocumentStoragePort,
        compiler: LaTeXCompilerPort,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._compiler = compiler

    async def generate_tailored_resume(
        self,
        *,
        owner_id: uuid.UUID,
        master_profile: ProfileDocument,
        options: ResumeGenerationOptions,
        offer_id: uuid.UUID | None = None,
        offer_title: str | None = None,
        offer_company: str | None = None,
        offer_description: str | None = None,
        required_skills: tuple[str, ...] = (),
    ) -> tuple[GeneratedDocumentModel, DocumentVersionModel, ATSReport]:
        """Génère un CV personnalisé ciblé, le compile, l'audite et l'enregistre (version 1)."""
        # 1. Construction du contexte et sélection déterministe (TASK-012-06, 07, 08, 09)
        context = build_generation_context(
            profile=master_profile,
            offer_title=offer_title,
            offer_company=offer_company,
            offer_description=offer_description,
            required_skills=required_skills,
        )

        adapted = adapt_resume_content(
            context,
            max_experiences=options.max_experiences,
            custom_title=options.target_role,
        )

        # 2. Contrôle strict des faits : aucune invention autorisée (TASK-012-10)
        assert_facts_verified(master_profile, adapted.adapted_profile)

        # 3. Rendu du code source LaTeX mono-colonne (TASK-012-01 à 05, TASK-012-11)
        latex_source = render_latex_resume(
            adapted.adapted_profile,
            title=adapted.target_title,
            summary=options.custom_summary or adapted.adapted_summary,
            length_target=options.length_target,
            style=options.style,
            highlight_skills=adapted.highlight_skills,
        )

        # 4. Compilation isolée en PDF (TASK-012-12 à 16)
        pdf_bytes = await self._compiler.compile(latex_source)

        # 5. Audit qualité ATS du PDF compilé (TASK-012-17 à 21)
        ats_report = analyze_pdf_ats(
            pdf_bytes,
            expected_keywords=adapted.matched_keywords,
        )

        # 6. Stockage de l'artefact PDF (ADR-0007 / TASK-012-22)
        storage_key, sha256, size_bytes = await self._storage.store(pdf_bytes, extension="pdf")

        # 7. Enregistrement en base de données du document et de sa version 1 (TASK-012-22, 23)
        doc_title = options.title or f"CV - {adapted.target_title}"
        document = await self._repository.create_document(
            owner_id=owner_id,
            kind=DocumentKind.CV,
            title=doc_title,
            language=options.language,
            offer_id=offer_id,
        )

        version_model = await self._repository.add_version(
            owner_id=owner_id,
            document_id=document.id,
            latex_source=latex_source,
            storage_key=storage_key,
            sha256=sha256,
            size_bytes=size_bytes,
            ats_report=ats_report.to_dict(),
        )

        return document, version_model, ats_report

    async def compile_custom_version(
        self,
        *,
        owner_id: uuid.UUID,
        document_id: uuid.UUID,
        latex_source: str,
        expected_keywords: tuple[str, ...] = (),
    ) -> tuple[DocumentVersionModel, ATSReport]:
        """Compile une source LaTeX modifiée et enregistre une nouvelle version immuable."""
        document = await self._repository.get_document(owner_id=owner_id, document_id=document_id)
        if document is None:
            raise ValueError(f"Document introuvable : {document_id}")

        # Compilation isolée (FEATURE 012.3)
        pdf_bytes = await self._compiler.compile(latex_source)

        # Audit ATS du nouveau PDF (FEATURE 012.4)
        ats_report = analyze_pdf_ats(pdf_bytes, expected_keywords=expected_keywords)

        # Sauvegarde de l'artefact PDF
        storage_key, sha256, size_bytes = await self._storage.store(pdf_bytes, extension="pdf")

        # Ajout de la nouvelle version immuable (TASK-012-22)
        version_model = await self._repository.add_version(
            owner_id=owner_id,
            document_id=document_id,
            latex_source=latex_source,
            storage_key=storage_key,
            sha256=sha256,
            size_bytes=size_bytes,
            ats_report=ats_report.to_dict(),
        )

        return version_model, ats_report

    async def get_document(
        self, *, owner_id: uuid.UUID, document_id: uuid.UUID
    ) -> GeneratedDocumentModel | None:
        return await self._repository.get_document(owner_id=owner_id, document_id=document_id)

    async def list_documents(
        self,
        *,
        owner_id: uuid.UUID,
        kind: DocumentKind | None = None,
        offer_id: uuid.UUID | None = None,
    ) -> list[GeneratedDocumentModel]:
        docs = await self._repository.list_documents(
            owner_id=owner_id, kind=kind, offer_id=offer_id
        )
        return list(docs)

    async def list_versions(
        self, *, owner_id: uuid.UUID, document_id: uuid.UUID
    ) -> list[DocumentVersionModel]:
        versions = await self._repository.list_versions(owner_id=owner_id, document_id=document_id)
        return list(versions)

    async def download_pdf(
        self, *, owner_id: uuid.UUID, document_id: uuid.UUID, version: int
    ) -> tuple[bytes, str]:
        """Retourne les octets du PDF et le nom de fichier suggéré pour l'export."""
        doc = await self._repository.get_document(owner_id=owner_id, document_id=document_id)
        ver = await self._repository.get_version(
            owner_id=owner_id, document_id=document_id, version=version
        )
        if doc is None or ver is None:
            raise FileNotFoundError("Version ou document introuvable.")

        pdf_bytes = await self._storage.read(ver.storage_key)
        safe_title = "".join(c for c in doc.title if c.isalnum() or c in ("-", "_", " ")).strip()
        filename = f"{safe_title}_v{version}.pdf"
        return pdf_bytes, filename

    async def download_latex(
        self, *, owner_id: uuid.UUID, document_id: uuid.UUID, version: int
    ) -> tuple[str, str]:
        """Retourne le code source LaTeX et le nom suggéré (TASK-012-25)."""
        doc = await self._repository.get_document(owner_id=owner_id, document_id=document_id)
        ver = await self._repository.get_version(
            owner_id=owner_id, document_id=document_id, version=version
        )
        if doc is None or ver is None or not ver.latex_source:
            raise FileNotFoundError("Code LaTeX introuvable pour cette version.")

        safe_title = "".join(c for c in doc.title if c.isalnum() or c in ("-", "_", " ")).strip()
        filename = f"{safe_title}_v{version}.tex"
        return ver.latex_source, filename

    async def compare_versions(
        self, *, owner_id: uuid.UUID, document_id: uuid.UUID, version_a: int, version_b: int
    ) -> DocumentComparison:
        """Compare deux versions d'un même document (diff LaTeX et ATS) (TASK-012-26)."""
        ver_a = await self._repository.get_version(
            owner_id=owner_id, document_id=document_id, version=version_a
        )
        ver_b = await self._repository.get_version(
            owner_id=owner_id, document_id=document_id, version=version_b
        )
        if ver_a is None or ver_b is None:
            raise ValueError("L'une des versions à comparer n'existe pas.")

        source_a = (ver_a.latex_source or "").splitlines(keepends=True)
        source_b = (ver_b.latex_source or "").splitlines(keepends=True)

        diff = difflib.unified_diff(
            source_a,
            source_b,
            fromfile=f"v{version_a}.tex",
            tofile=f"v{version_b}.tex",
        )
        diff_text = "".join(diff)

        score_a = ver_a.ats_report.get("score") if ver_a.ats_report else None
        score_b = ver_b.ats_report.get("score") if ver_b.ats_report else None
        size_diff = ver_b.size_bytes - ver_a.size_bytes

        return DocumentComparison(
            document_id=document_id,
            version_a=version_a,
            version_b=version_b,
            diff_latex=diff_text,
            score_a=score_a,
            score_b=score_b,
            size_diff_bytes=size_diff,
        )

    def audit_pdf(self, pdf_bytes: bytes, *, expected_keywords: tuple[str, ...] = ()) -> ATSReport:
        """Audite directement un PDF (TASK-012-17 à 21)."""
        return analyze_pdf_ats(pdf_bytes, expected_keywords=expected_keywords)
