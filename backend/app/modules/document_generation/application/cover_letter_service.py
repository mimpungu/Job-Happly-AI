"""Cas d'usage de la lettre de motivation : génération, édition, versions (EPIC 013)."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from datetime import date
from typing import TYPE_CHECKING, Any

from app.modules.document_generation.application.library import DocumentLibrary
from app.modules.document_generation.application.ports import (
    DocumentRepositoryPort,
    DocumentStoragePort,
    GenerationInputsPort,
    LaTeXCompilerPort,
    NoValidatedProfileError,
    OfferContext,
    OfferNotFoundError,
)
from app.modules.document_generation.domain.ats_analyzer import read_pdf_text
from app.modules.document_generation.domain.cover_letter_audit import (
    audit_letter,
    audit_letter_text,
    verify_letter_facts,
)
from app.modules.document_generation.domain.cover_letter_generator import (
    extract_company_offer_context,
    generate_cover_letter_content,
)
from app.modules.document_generation.domain.cover_letter_models import (
    CompanyOfferContext,
    CoverLetterAudit,
    CoverLetterContent,
    CoverLetterOptions,
)
from app.modules.document_generation.domain.cover_letter_prompts import (
    COVER_LETTER_PROMPT_VERSION,
)
from app.modules.document_generation.domain.cover_letter_templates import (
    render_latex_cover_letter,
)
from app.modules.document_generation.domain.enums import DocumentKind
from app.modules.document_generation.domain.fact_checker import UnverifiedFactError
from app.modules.document_generation.domain.spelling import SpellingChecker

if TYPE_CHECKING:
    from app.modules.document_generation.infrastructure.models import (
        DocumentVersionModel,
        GeneratedDocumentModel,
    )

_MAX_PAGES = 1


class CoverLetterService:
    """Orchestre la lettre : profil validé + offre → texte factuel → PDF → audit → version."""

    def __init__(
        self,
        repository: DocumentRepositoryPort,
        storage: DocumentStoragePort,
        compiler: LaTeXCompilerPort,
        inputs: GenerationInputsPort,
        *,
        today: Callable[[], date] = date.today,
        spelling: SpellingChecker | None = None,
    ) -> None:
        self._spelling = spelling
        self._repository = repository
        self._storage = storage
        self._compiler = compiler
        self._inputs = inputs
        self._today = today
        self.library = DocumentLibrary(repository, storage, DocumentKind.COVER_LETTER)

    async def generate_tailored_letter(
        self, *, owner_id: uuid.UUID, offer_id: uuid.UUID, options: CoverLetterOptions
    ) -> tuple[GeneratedDocumentModel, DocumentVersionModel, CoverLetterContent, CoverLetterAudit]:
        """Génère la lettre depuis le profil validé et l'offre, la compile et l'enregistre (v1)."""
        profile = await self._inputs.validated_profile(owner_id=owner_id)
        offer = await self._inputs.offer_context(owner_id=owner_id, offer_id=offer_id)
        context = _to_context(offer)
        aujourdhui = self._today()

        # Le pays de l'offre guide les usages (date, salutation) sauf indication contraire.
        if options.country_code is None and offer.country_code:
            options = options.model_copy(update={"country_code": offer.country_code.upper()})

        content = generate_cover_letter_content(profile, context, options, today=aujourdhui)
        faits = verify_letter_facts(content, profile, context, today=aujourdhui)
        if faits:  # TASK-013-09/10 : jamais de lettre qui contredit le CV
            raise UnverifiedFactError(
                "La lettre générée contient des faits non prouvés : " + "; ".join(faits)
            )

        latex_source, pdf_bytes, pages = await self._compile(content, compact=False)
        if pages > _MAX_PAGES:
            # Resserrer la mise en page plutôt que couper le texte de l'utilisateur.
            latex_source, pdf_bytes, pages = await self._compile(content, compact=True)
        audit = audit_letter(
            content, profile, context, today=aujourdhui, page_count=pages, spelling=self._spelling
        )

        storage_key, sha256, size_bytes = await self._storage.store(pdf_bytes, extension="pdf")
        try:
            document = await self._repository.create_document(
                owner_id=owner_id,
                kind=DocumentKind.COVER_LETTER,
                title=_title(context),
                language=options.language,
                offer_id=offer_id,
            )
            version = await self._repository.add_version(
                owner_id=owner_id,
                document_id=document.id,
                latex_source=latex_source,
                storage_key=storage_key,
                sha256=sha256,
                size_bytes=size_bytes,
                ats_report={
                    **audit.to_dict(),
                    "generation": {
                        "origin": "generated",
                        "prompt_version": COVER_LETTER_PROMPT_VERSION,
                        "language": options.language,
                        "country_code": options.country_code,
                    },
                },
            )
        except Exception:
            await self._storage.delete(storage_key)  # pas de PDF orphelin si la base échoue
            raise
        return document, version, content, audit

    async def _compile(
        self, content: CoverLetterContent, *, compact: bool
    ) -> tuple[str, bytes, int]:
        latex_source = render_latex_cover_letter(content, compact=compact)
        pdf_bytes = await self._compiler.compile(latex_source)
        lecture = await asyncio.to_thread(read_pdf_text, pdf_bytes)
        return latex_source, pdf_bytes, lecture[1] if lecture else 0

    async def compile_custom_version(
        self, *, owner_id: uuid.UUID, document_id: uuid.UUID, latex_source: str
    ) -> tuple[DocumentVersionModel, CoverLetterAudit]:
        """Compile une version éditée et l'audite réellement (jamais de score fabriqué)."""
        document = await self.library.get_document(owner_id=owner_id, document_id=document_id)
        pdf_bytes = await self._compiler.compile(latex_source)

        lecture = await asyncio.to_thread(read_pdf_text, pdf_bytes)
        texte, pages = lecture if lecture else ("", 0)
        profile, context = await self._references(owner_id, document.offer_id)
        audit = audit_letter_text(
            texte,
            language=document.language,
            profile=profile,
            context=context,
            today=self._today(),
            page_count=pages,
            spelling=self._spelling,
        )

        storage_key, sha256, size_bytes = await self._storage.store(pdf_bytes, extension="pdf")
        try:
            version = await self._repository.add_version(
                owner_id=owner_id,
                document_id=document_id,
                latex_source=latex_source,
                storage_key=storage_key,
                sha256=sha256,
                size_bytes=size_bytes,
                ats_report={**audit.to_dict(), "generation": {"origin": "manual_edit"}},
            )
        except Exception:
            await self._storage.delete(storage_key)
            raise
        return version, audit

    async def _references(
        self, owner_id: uuid.UUID, offer_id: uuid.UUID | None
    ) -> tuple[Any, CompanyOfferContext | None]:
        """Profil validé et offre servant de référence à l'audit ; None si disparus."""
        try:
            profile = await self._inputs.validated_profile(owner_id=owner_id)
        except NoValidatedProfileError:
            profile = None
        context = None
        if offer_id is not None:
            try:
                context = _to_context(
                    await self._inputs.offer_context(owner_id=owner_id, offer_id=offer_id)
                )
            except OfferNotFoundError:
                context = None  # offre supprimée depuis : la lettre reste éditable
        return profile, context


def _to_context(offer: OfferContext) -> CompanyOfferContext:
    return extract_company_offer_context(
        job_title=offer.title,
        company_name=offer.company,
        offer_description=offer.description,
        company_location=offer.location,
        required_skills=offer.required_skills,
    )


def _title(context: CompanyOfferContext) -> str:
    entreprise = f" ({context.company_name})" if context.company_name else ""
    return f"Lettre - {context.job_title}{entreprise}"
