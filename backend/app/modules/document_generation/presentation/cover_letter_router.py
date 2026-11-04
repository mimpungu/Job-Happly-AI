"""Routes de l'API REST pour la génération de lettres de motivation (EPIC 013)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select

from app.core.api.dependencies import SessionDep, get_owner_id
from app.modules.candidate_profile.infrastructure.profile_repository import SqlProfileRepository
from app.modules.document_generation.application.ports import (
    CompilationTimeoutError,
    LaTeXCompilationError,
    LaTeXSourceTooLargeError,
)
from app.modules.document_generation.domain.cover_letter_models import CoverLetterOptions
from app.modules.document_generation.domain.enums import DocumentKind
from app.modules.document_generation.domain.fact_checker import UnverifiedFactError
from app.modules.document_generation.infrastructure.composition import build_cover_letter_service
from app.modules.document_generation.presentation.cover_letter_schemas import (
    GenerateCoverLetterRequest,
)
from app.modules.document_generation.presentation.schemas import (
    ComparisonResponse,
    CompileVersionRequest,
    DocumentVersionResponse,
    GeneratedDocumentResponse,
)
from app.modules.job_discovery.infrastructure.models import JobOfferModel
from app.modules.job_intelligence.infrastructure.models import JobAnalysisModel

router = APIRouter(prefix="/api/v1/cover-letters", tags=["cover-letter-generator"])
Owner = Annotated[uuid.UUID, Depends(get_owner_id)]


@router.post("/generate", response_model=GeneratedDocumentResponse, status_code=201)
async def generate_cover_letter(
    body: GenerateCoverLetterRequest,
    session: SessionDep,
    owner_id: Owner,
) -> GeneratedDocumentResponse:
    """Génère une lettre de motivation ciblée sur une offre d'emploi, compilée en PDF."""
    # 1. Chargement du profil maître du candidat
    profile_repo = SqlProfileRepository(session)
    stored_profile = await profile_repo.latest(owner_id=owner_id)
    if stored_profile is None:
        raise HTTPException(
            status_code=400,
            detail="Aucun profil candidat trouvé. Renseignez d'abord votre profil maître.",
        )

    # 2. Chargement de l'offre d'emploi cible
    offer = await session.scalar(
        select(JobOfferModel).where(
            JobOfferModel.id == body.offer_id, JobOfferModel.owner_id == owner_id
        )
    )
    if offer is None:
        raise HTTPException(status_code=404, detail="Offre d'emploi introuvable.")

    required_skills: tuple[str, ...] = ()
    analysis = await session.scalar(
        select(JobAnalysisModel).where(
            JobAnalysisModel.offer_id == body.offer_id,
            JobAnalysisModel.owner_id == owner_id,
        )
    )
    if analysis is not None and isinstance(analysis.result, dict):
        skills_data = analysis.result.get("skills") or analysis.result.get("required_skills") or []
        if isinstance(skills_data, list):
            required_skills = tuple(str(s) for s in skills_data)

    cover_letter_service = build_cover_letter_service(session)
    options = CoverLetterOptions(
        language=body.language,
        country_code=body.country_code or offer.country_code,
        recipient_name=body.recipient_name,
        recipient_department=body.recipient_department,
        custom_opening=body.custom_opening,
    )

    try:
        doc, ver, _content, _audit = await cover_letter_service.generate_tailored_letter(
            owner_id=owner_id,
            master_profile=stored_profile.document,
            options=options,
            offer_id=body.offer_id,
            job_title=offer.title,
            company_name=offer.company_name,
            offer_description=offer.description,
            company_location=offer.location,
            required_skills=required_skills,
        )
    except UnverifiedFactError as err:
        raise HTTPException(status_code=422, detail=str(err)) from err
    except (LaTeXCompilationError, CompilationTimeoutError, LaTeXSourceTooLargeError) as err:
        raise HTTPException(status_code=422, detail=f"Erreur de compilation : {err}") from err

    return GeneratedDocumentResponse(
        id=doc.id,
        kind=doc.kind,
        title=doc.title,
        language=doc.language,
        offer_id=doc.offer_id,
        created_at=doc.created_at,
        versions=[
            DocumentVersionResponse(
                id=ver.id,
                version=ver.version,
                created_at=ver.created_at,
                size_bytes=ver.size_bytes,
                sha256=ver.sha256,
            )
        ],
    )


@router.post("/{document_id}/compile", response_model=DocumentVersionResponse, status_code=201)
async def compile_custom_version(
    document_id: uuid.UUID,
    body: CompileVersionRequest,
    session: SessionDep,
    owner_id: Owner,
) -> DocumentVersionResponse:
    """Compile une version éditée de la lettre et crée une nouvelle version immuable."""
    cover_letter_service = build_cover_letter_service(session)
    try:
        ver = await cover_letter_service.compile_custom_version(
            owner_id=owner_id,
            document_id=document_id,
            latex_source=body.latex_source,
        )
    except (LaTeXCompilationError, CompilationTimeoutError, LaTeXSourceTooLargeError) as err:
        raise HTTPException(status_code=422, detail=f"Erreur de compilation LaTeX : {err}") from err
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err

    return DocumentVersionResponse(
        id=ver.id,
        version=ver.version,
        created_at=ver.created_at,
        size_bytes=ver.size_bytes,
        sha256=ver.sha256,
    )


@router.get("", response_model=list[GeneratedDocumentResponse])
async def list_cover_letters(
    session: SessionDep,
    owner_id: Owner,
    offer_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[GeneratedDocumentResponse]:
    """Liste les lettres de motivation du candidat."""
    cover_letter_service = build_cover_letter_service(session)
    docs = await cover_letter_service.list_documents(owner_id=owner_id, offer_id=offer_id)

    reponses: list[GeneratedDocumentResponse] = []
    for d in docs:
        versions = await cover_letter_service.list_versions(owner_id=owner_id, document_id=d.id)
        reponses.append(
            GeneratedDocumentResponse(
                id=d.id,
                kind=d.kind,
                title=d.title,
                language=d.language,
                offer_id=d.offer_id,
                created_at=d.created_at,
                versions=[
                    DocumentVersionResponse(
                        id=v.id,
                        version=v.version,
                        created_at=v.created_at,
                        size_bytes=v.size_bytes,
                        sha256=v.sha256,
                    )
                    for v in versions
                ],
            )
        )
    return reponses


@router.get("/{document_id}", response_model=GeneratedDocumentResponse)
async def get_cover_letter(
    document_id: uuid.UUID,
    session: SessionDep,
    owner_id: Owner,
) -> GeneratedDocumentResponse:
    """Consulte le détail d'une lettre et l'historique complet de ses versions."""
    cover_letter_service = build_cover_letter_service(session)
    doc = await cover_letter_service.get_document(owner_id=owner_id, document_id=document_id)
    if doc is None or doc.kind != DocumentKind.COVER_LETTER.value:
        raise HTTPException(status_code=404, detail="Document introuvable.")

    versions = await cover_letter_service.list_versions(owner_id=owner_id, document_id=doc.id)
    return GeneratedDocumentResponse(
        id=doc.id,
        kind=doc.kind,
        title=doc.title,
        language=doc.language,
        offer_id=doc.offer_id,
        created_at=doc.created_at,
        versions=[
            DocumentVersionResponse(
                id=v.id,
                version=v.version,
                created_at=v.created_at,
                size_bytes=v.size_bytes,
                sha256=v.sha256,
            )
            for v in versions
        ],
    )


@router.get("/{document_id}/versions/{version}/pdf")
async def download_pdf(
    document_id: uuid.UUID,
    version: int,
    session: SessionDep,
    owner_id: Owner,
) -> Response:
    """Télécharge le fichier PDF d'une lettre de motivation (TASK-013-13)."""
    cover_letter_service = build_cover_letter_service(session)
    try:
        pdf_bytes, filename = await cover_letter_service.download_pdf(
            owner_id=owner_id, document_id=document_id, version=version
        )
    except FileNotFoundError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{document_id}/versions/{version}/latex")
async def download_latex(
    document_id: uuid.UUID,
    version: int,
    session: SessionDep,
    owner_id: Owner,
) -> Response:
    """Télécharge le code source LaTeX (.tex) d'une lettre de motivation."""
    cover_letter_service = build_cover_letter_service(session)
    try:
        latex_str, filename = await cover_letter_service.download_latex(
            owner_id=owner_id, document_id=document_id, version=version
        )
    except FileNotFoundError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err

    return Response(
        content=latex_str,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{document_id}/compare", response_model=ComparisonResponse)
async def compare_versions(
    document_id: uuid.UUID,
    session: SessionDep,
    owner_id: Owner,
    version_a: Annotated[int, Query(ge=1)],
    version_b: Annotated[int, Query(ge=1)],
) -> ComparisonResponse:
    """Compare deux versions d'une lettre de motivation : diff LaTeX et score (TASK-013-15)."""
    cover_letter_service = build_cover_letter_service(session)
    try:
        comp = await cover_letter_service.compare_versions(
            owner_id=owner_id,
            document_id=document_id,
            version_a=version_a,
            version_b=version_b,
        )
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err

    return ComparisonResponse(
        document_id=comp.document_id,
        version_a=comp.version_a,
        version_b=comp.version_b,
        diff_latex=comp.diff_latex,
        score_a=comp.score_a,
        score_b=comp.score_b,
        size_diff_bytes=comp.size_diff_bytes,
    )
