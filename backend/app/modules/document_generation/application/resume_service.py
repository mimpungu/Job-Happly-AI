"""Cas d'usage du CV : génération ciblée, recompilation, versions, exports (EPIC 012)."""

from __future__ import annotations

import asyncio
import dataclasses
import uuid
from typing import TYPE_CHECKING, Any

from app.modules.document_generation.application.library import DocumentLibrary
from app.modules.document_generation.application.ports import (
    DocumentRepositoryPort,
    DocumentStoragePort,
    GenerationInputsPort,
    LaTeXCompilerPort,
    OfferContext,
    OfferNotFoundError,
    ResumeRewriterPort,
    RewriterUnavailableError,
)
from app.modules.document_generation.domain.ats_analyzer import (
    DEFAULT_EXPECTED_SECTIONS,
    analyze_pdf_ats,
)
from app.modules.document_generation.domain.content_selection import (
    AdaptedContent,
    adapt_resume_content,
    build_generation_context,
)
from app.modules.document_generation.domain.enums import DocumentKind, LengthTarget, RewriteMode
from app.modules.document_generation.domain.fact_checker import assert_facts_verified
from app.modules.document_generation.domain.latex_escape import sanitize_text
from app.modules.document_generation.domain.models import (
    ATSReport,
    ResumeGenerationOptions,
)
from app.modules.document_generation.domain.prompts import CV_PROMPT_VERSION
from app.modules.document_generation.domain.resume_rewrite import (
    RewriteReport,
    apply_rewrites,
    is_acceptable_rewrite,
    known_terms,
)
from app.modules.document_generation.domain.templates import fits_one_page, render_latex_resume

if TYPE_CHECKING:
    from app.modules.candidate_profile.domain.profile import ProfileDocument
    from app.modules.document_generation.infrastructure.models import (
        DocumentVersionModel,
        GeneratedDocumentModel,
    )

_ONE_PAGE_MAX_ACHIEVEMENTS = 4


class ResumeService:
    """Orchestre le cycle de vie des CV LaTeX : génération, compilation, audit, versions."""

    def __init__(
        self,
        repository: DocumentRepositoryPort,
        storage: DocumentStoragePort,
        compiler: LaTeXCompilerPort,
        inputs: GenerationInputsPort,
        rewriter: ResumeRewriterPort | None = None,
    ) -> None:
        self._rewriter = rewriter
        self._repository = repository
        self._storage = storage
        self._compiler = compiler
        self._inputs = inputs
        self.library = DocumentLibrary(repository, storage, DocumentKind.CV)

    async def generate_tailored_resume(
        self,
        *,
        owner_id: uuid.UUID,
        options: ResumeGenerationOptions,
        offer_id: uuid.UUID | None = None,
    ) -> tuple[GeneratedDocumentModel, DocumentVersionModel, ATSReport]:
        """Génère un CV depuis le profil validé, le compile, l'audite et l'enregistre (v1)."""
        master = await self._inputs.validated_profile(owner_id=owner_id)
        offer = (
            await self._inputs.offer_context(owner_id=owner_id, offer_id=offer_id)
            if offer_id is not None
            else None
        )

        adapted = self._adapt(master, options, offer)
        adapted, rewrites, rewrite_report = await self._rewrite_achievements(
            owner_id, master, adapted, options
        )
        # Aucune invention : tout ce qui est rendu doit exister dans le profil maître.
        assert_facts_verified(
            master,
            adapted.adapted_profile,
            generated_summary=adapted.adapted_summary
            if adapted.summary_is_generated and not options.custom_summary
            else None,
            allowed_rewrites=rewrites,
        )

        target = options.length_target
        latex_source, pdf_bytes, report = await self._render_and_audit(
            adapted, options, offer, target
        )
        if (
            target is LengthTarget.AUTO
            and report.page_count > 1
            and fits_one_page(adapted.adapted_profile)
        ):
            # L'estimation « une page » était optimiste : on repasse en mise en page aérée.
            target = LengthTarget.TWO_PAGES
            latex_source, pdf_bytes, report = await self._render_and_audit(
                adapted, options, offer, target
            )

        storage_key, sha256, size_bytes = await self._storage.store(pdf_bytes, extension="pdf")
        try:
            document = await self._repository.create_document(
                owner_id=owner_id,
                kind=DocumentKind.CV,
                title=options.title or self._default_title(adapted.target_title),
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
                ats_report=self._report_payload(
                    report,
                    {
                        "origin": "generated",
                        "prompt_version": CV_PROMPT_VERSION,
                        "style": options.style.value,
                        "length_target": target.value,
                        "language": options.language,
                    },
                    rewrite_report,
                ),
            )
        except Exception:
            await self._storage.delete(storage_key)  # pas de PDF orphelin si la base échoue
            raise
        return document, version, report

    async def _rewrite_achievements(
        self,
        owner_id: uuid.UUID,
        master: ProfileDocument,
        adapted: AdaptedContent,
        options: ResumeGenerationOptions,
    ) -> tuple[AdaptedContent, dict[str, str], RewriteReport]:
        """Reformulation facultative : tout refus ou toute sortie douteuse garde le texte d'origine.

        L'échec de l'IA n'empêche jamais la génération, mais il est consigné dans la version
        (jamais silencieux).
        """
        mode = options.rewrite_mode
        if mode is RewriteMode.NONE:
            return adapted, {}, RewriteReport(requested=mode.value, status="not_requested")
        originals = list(
            dict.fromkeys(a for e in adapted.adapted_profile.experiences for a in e.achievements)
        )
        if not originals:
            return adapted, {}, RewriteReport(requested=mode.value, status="unchanged")
        if self._rewriter is None:
            return (
                adapted,
                {},
                RewriteReport(
                    requested=mode.value,
                    status="unavailable",
                    reason="Reformulation non disponible sur ce serveur.",
                ),
            )
        try:
            outcome = await self._rewriter.rewrite(
                owner_id=owner_id, achievements=originals, language=options.language, mode=mode
            )
        except RewriterUnavailableError as erreur:
            return (
                adapted,
                {},
                RewriteReport(requested=mode.value, status="unavailable", reason=str(erreur)),
            )
        autorises = known_terms(master)
        retenues = {
            original: texte.strip()
            for original, texte in outcome.proposals.items()
            if original in originals and is_acceptable_rewrite(original, texte, allowed=autorises)
        }
        rejetees = len(
            [o for o, t in outcome.proposals.items() if o in originals and o not in retenues]
        )
        if retenues:
            adapted = dataclasses.replace(
                adapted, adapted_profile=apply_rewrites(adapted.adapted_profile, retenues)
            )
        statut = "unchanged" if not retenues else ("partial" if rejetees else "applied")
        return (
            adapted,
            retenues,
            RewriteReport(
                requested=mode.value,
                status=statut,
                rewritten=len(retenues),
                rejected=rejetees,
                provider=outcome.provider,
                model=outcome.model,
                cache_hit=outcome.cache_hit,
            ),
        )

    @staticmethod
    def _default_title(target_title: str | None) -> str:
        return f"CV - {target_title}" if target_title else "CV"

    @staticmethod
    def _adapt(
        master: ProfileDocument, options: ResumeGenerationOptions, offer: OfferContext | None
    ) -> AdaptedContent:
        context = build_generation_context(
            master,
            offer_title=offer.title if offer else None,
            offer_company=offer.company if offer else None,
            offer_description=offer.description if offer else None,
            required_skills=offer.required_skills if offer else (),
            language=options.language,
        )
        return adapt_resume_content(
            context,
            max_experiences=options.max_experiences,
            max_achievements=(
                _ONE_PAGE_MAX_ACHIEVEMENTS
                if options.length_target is LengthTarget.ONE_PAGE
                else None
            ),
            custom_title=options.target_role,
        )

    async def _render_and_audit(
        self,
        adapted: AdaptedContent,
        options: ResumeGenerationOptions,
        offer: OfferContext | None,
        target: LengthTarget,
    ) -> tuple[str, bytes, ATSReport]:
        latex_source = render_latex_resume(
            adapted.adapted_profile,
            title=adapted.target_title,
            summary=options.custom_summary or adapted.adapted_summary,
            length_target=target,
            style=options.style,
            highlight_skills=adapted.highlight_skills,
            language=options.language,
        )
        pdf_bytes = await self._compiler.compile(latex_source)
        report = await asyncio.to_thread(
            analyze_pdf_ats,
            pdf_bytes,
            expected_keywords=adapted.offer_terms if offer else (),
            expected_phrases=_expected_phrases(adapted.adapted_profile),
            expected_sections=_expected_sections(adapted),
            length_target=target,
        )
        return latex_source, pdf_bytes, report

    async def compile_custom_version(
        self,
        *,
        owner_id: uuid.UUID,
        document_id: uuid.UUID,
        latex_source: str,
        expected_keywords: tuple[str, ...] = (),
    ) -> tuple[DocumentVersionModel, ATSReport]:
        """Compile une source LaTeX modifiée par l'utilisateur : nouvelle version immuable."""
        document = await self.library.get_document(owner_id=owner_id, document_id=document_id)

        mots_cles = expected_keywords or await self._offer_terms(owner_id, document.offer_id)
        pdf_bytes = await self._compiler.compile(latex_source)
        report = await asyncio.to_thread(analyze_pdf_ats, pdf_bytes, expected_keywords=mots_cles)

        storage_key, sha256, size_bytes = await self._storage.store(pdf_bytes, extension="pdf")
        try:
            version = await self._repository.add_version(
                owner_id=owner_id,
                document_id=document_id,
                latex_source=latex_source,
                storage_key=storage_key,
                sha256=sha256,
                size_bytes=size_bytes,
                ats_report=self._report_payload(report, {"origin": "manual_edit"}),
            )
        except Exception:
            await self._storage.delete(storage_key)
            raise
        return version, report

    async def _offer_terms(
        self, owner_id: uuid.UUID, offer_id: uuid.UUID | None
    ) -> tuple[str, ...]:
        if offer_id is None:
            return ()
        try:
            offer = await self._inputs.offer_context(owner_id=owner_id, offer_id=offer_id)
        except OfferNotFoundError:
            return ()  # l'offre a pu être supprimée depuis : le CV reste éditable
        return offer.required_skills

    @staticmethod
    async def audit_pdf(pdf_bytes: bytes, *, expected_keywords: tuple[str, ...] = ()) -> ATSReport:
        """Audite un PDF hors de la boucle d'événements (pypdf est synchrone)."""
        return await asyncio.to_thread(
            analyze_pdf_ats, pdf_bytes, expected_keywords=expected_keywords
        )

    @staticmethod
    def _report_payload(
        report: ATSReport, generation: dict[str, Any], rewrite: RewriteReport | None = None
    ) -> dict[str, Any]:
        if rewrite is not None and rewrite.status != "not_requested":
            generation = {**generation, "ai_rewrite": rewrite.to_dict()}
        return {**report.to_dict(), "generation": generation}


def _expected_phrases(profile: ProfileDocument) -> tuple[str, ...]:
    """Textes du profil qui doivent ressortir intacts de l'extraction (accents compris)."""
    identity = profile.identity
    phrases = [f"{identity.first_name or ''} {identity.last_name or ''}"]
    phrases += [e.company or "" for e in profile.experiences]
    phrases += [e.title or "" for e in profile.experiences]
    phrases += [e.institution or "" for e in profile.educations]
    phrases += [e.degree or "" for e in profile.educations]
    return tuple(dict.fromkeys(sanitize_text(p) for p in phrases if p.strip()))


def _expected_sections(adapted: AdaptedContent) -> tuple[str, ...]:
    """Rubriques que le contenu impose : une rubrique sans donnée n'est pas rendue."""
    profile = adapted.adapted_profile
    sections = list(DEFAULT_EXPECTED_SECTIONS)
    presentes = {
        "summary": bool(adapted.adapted_summary),
        "experience": bool(profile.experiences),
        "skills": bool(profile.skills),
        "education": bool(profile.educations),
        "certifications": bool(profile.certifications),
        "languages": bool(profile.languages),
    }
    return tuple(s for s in (*sections, "summary", "certifications", "languages") if presentes[s])
