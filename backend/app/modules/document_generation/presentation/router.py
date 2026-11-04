"""Routes de l'API REST pour la génération de CV LaTeX et le contrôle ATS (EPIC 012)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from sqlalchemy import select

from app.core.api.dependencies import SessionDep, get_owner_id
from app.modules.candidate_profile.infrastructure.profile_repository import SqlProfileRepository
from app.modules.document_generation.application.ports import (
    CompilationTimeoutError,
    LaTeXCompilationError,
    LaTeXSourceTooLargeError,
)
from app.modules.document_generation.domain.ats_analyzer import analyze_pdf_ats
from app.modules.document_generation.domain.enums import DocumentKind
from app.modules.document_generation.domain.fact_checker import UnverifiedFactError
from app.modules.document_generation.domain.models import ResumeGenerationOptions
from app.modules.document_generation.infrastructure.composition import build_resume_service
from app.modules.document_generation.presentation.schemas import (
    ATSReportResponse,
    ComparisonResponse,
    CompileVersionRequest,
    DocumentVersionResponse,
    GeneratedDocumentResponse,
    GenerateResumeRequest,
)
from app.modules.job_discovery.infrastructure.models import JobOfferModel
from app.modules.job_intelligence.infrastructure.models import JobAnalysisModel

router = APIRouter(prefix="/api/v1/resumes", tags=["resume-generator"])
Owner = Annotated[uuid.UUID, Depends(get_owner_id)]


@router.post("/generate", response_model=GeneratedDocumentResponse, status_code=201)
async def generate_resume(
    body: GenerateResumeRequest,
    session: SessionDep,
    owner_id: Owner,
) -> GeneratedDocumentResponse:
    """Génère un CV personnalisé ciblé, compilé en PDF et audité pour les ATS."""
    profile_repo = SqlProfileRepository(session)
    stored_profile = await profile_repo.latest(owner_id=owner_id)
    if stored_profile is None:
        raise HTTPException(
            status_code=400,
            detail="Aucun profil candidat trouvé. Renseignez d'abord votre profil maître.",
        )

    offer_title: str | None = None
    offer_company: str | None = None
    offer_description: str | None = None
    required_skills: tuple[str, ...] = ()

    if body.offer_id is not None:
        offer = await session.scalar(
            select(JobOfferModel).where(
                JobOfferModel.id == body.offer_id, JobOfferModel.owner_id == owner_id
            )
        )
        if offer is None:
            raise HTTPException(status_code=404, detail="Offre d'emploi introuvable.")
        offer_title = offer.title
        offer_company = offer.company_name
        offer_description = offer.description
        analysis = await session.scalar(
            select(JobAnalysisModel).where(
                JobAnalysisModel.offer_id == body.offer_id,
                JobAnalysisModel.owner_id == owner_id,
            )
        )
        if analysis is not None and isinstance(analysis.result, dict):
            skills_data = (
                analysis.result.get("skills") or analysis.result.get("required_skills") or []
            )
            if isinstance(skills_data, list):
                required_skills = tuple(str(s) for s in skills_data)

    resume_service = build_resume_service(session)
    options = ResumeGenerationOptions(
        title=body.title,
        target_role=body.target_role,
        language=body.language,
        style=body.style,
        length_target=body.length_target,
        max_experiences=body.max_experiences,
        custom_summary=body.custom_summary,
    )

    try:
        doc, ver, ats = await resume_service.generate_tailored_resume(
            owner_id=owner_id,
            master_profile=stored_profile.document,
            options=options,
            offer_id=body.offer_id,
            offer_title=offer_title,
            offer_company=offer_company,
            offer_description=offer_description,
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
                ats_report=ATSReportResponse.model_validate(ats.to_dict()) if ats else None,
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
    """Compile une source LaTeX modifiée et enregistre une nouvelle version immuable."""
    resume_service = build_resume_service(session)
    try:
        ver, ats = await resume_service.compile_custom_version(
            owner_id=owner_id,
            document_id=document_id,
            latex_source=body.latex_source,
            expected_keywords=tuple(body.expected_keywords),
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
        ats_report=ATSReportResponse.model_validate(ats.to_dict()),
    )


@router.get("", response_model=list[GeneratedDocumentResponse])
async def list_resumes(
    session: SessionDep,
    owner_id: Owner,
    offer_id: Annotated[uuid.UUID | None, Query()] = None,
) -> list[GeneratedDocumentResponse]:
    """Liste les CV du candidat."""
    resume_service = build_resume_service(session)
    docs = await resume_service.list_documents(
        owner_id=owner_id, kind=DocumentKind.CV, offer_id=offer_id
    )

    reponses: list[GeneratedDocumentResponse] = []
    for d in docs:
        versions = await resume_service.list_versions(owner_id=owner_id, document_id=d.id)
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
                        ats_report=(
                            ATSReportResponse.model_validate(v.ats_report) if v.ats_report else None
                        ),
                    )
                    for v in versions
                ],
            )
        )
    return reponses


@router.get("/{document_id}", response_model=GeneratedDocumentResponse)
async def get_resume(
    document_id: uuid.UUID,
    session: SessionDep,
    owner_id: Owner,
) -> GeneratedDocumentResponse:
    """Consulte le détail d'un CV et l'historique complet de ses versions."""
    resume_service = build_resume_service(session)
    doc = await resume_service.get_document(owner_id=owner_id, document_id=document_id)
    if doc is None or doc.kind != DocumentKind.CV.value:
        raise HTTPException(status_code=404, detail="Document introuvable.")

    versions = await resume_service.list_versions(owner_id=owner_id, document_id=doc.id)
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
                ats_report=(
                    ATSReportResponse.model_validate(v.ats_report) if v.ats_report else None
                ),
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
    """Télécharge le fichier binaire PDF d'une version de CV (TASK-012-24)."""
    resume_service = build_resume_service(session)
    try:
        pdf_bytes, filename = await resume_service.download_pdf(
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
    """Télécharge le code source LaTeX (.tex) d'une version de CV (TASK-012-25)."""
    resume_service = build_resume_service(session)
    try:
        latex_str, filename = await resume_service.download_latex(
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
    """Compare deux versions d'un CV : diff LaTeX et score ATS (TASK-012-26)."""
    resume_service = build_resume_service(session)
    try:
        comp = await resume_service.compare_versions(
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


@router.post("/audit-ats", response_model=ATSReportResponse)
async def audit_ats(
    file: Annotated[UploadFile, File()],
) -> ATSReportResponse:
    """Audite directement un fichier PDF uploadé pour vérifier sa conformité ATS."""
    contenu = await file.read()
    if not contenu:
        raise HTTPException(status_code=400, detail="Fichier PDF vide.")

    report = analyze_pdf_ats(contenu)
    return ATSReportResponse.model_validate(report.to_dict())
