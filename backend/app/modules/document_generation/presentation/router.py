"""Routes de génération de CV LaTeX et de contrôle ATS (EPIC 012). Routes minces : tout passe
par `ResumeService` ; les erreurs métier sont traduites par `presentation/errors.py`."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile

from app.core.api.dependencies import SessionDep, get_owner_id
from app.modules.document_generation.application.resume_service import ResumeService
from app.modules.document_generation.domain.models import ResumeGenerationOptions
from app.modules.document_generation.infrastructure.composition import build_resume_service
from app.modules.document_generation.infrastructure.models import (
    DocumentVersionModel,
    GeneratedDocumentModel,
)
from app.modules.document_generation.presentation.downloads import attachment_headers
from app.modules.document_generation.presentation.schemas import (
    ATSReportResponse,
    ComparisonResponse,
    CompileVersionRequest,
    DocumentVersionResponse,
    GeneratedDocumentResponse,
    GenerateResumeRequest,
    GenerationMetaResponse,
)

router = APIRouter(prefix="/api/v1/resumes", tags=["resume-generator"])
Owner = Annotated[uuid.UUID, Depends(get_owner_id)]

MAX_AUDIT_PDF_BYTES = 5 * 1024 * 1024
_PDF_MAGIC = b"%PDF-"


def _version_response(version: DocumentVersionModel) -> DocumentVersionResponse:
    rapport = version.ats_report
    meta = rapport.get("generation") if rapport else None
    return DocumentVersionResponse(
        id=version.id,
        version=version.version,
        created_at=version.created_at,
        size_bytes=version.size_bytes,
        sha256=version.sha256,
        ats_report=ATSReportResponse.model_validate(rapport) if rapport else None,
        generation=GenerationMetaResponse.model_validate(meta) if meta else None,
    )


def _document_response(
    document: GeneratedDocumentModel, versions: list[DocumentVersionModel]
) -> GeneratedDocumentResponse:
    return GeneratedDocumentResponse(
        id=document.id,
        kind=document.kind,
        title=document.title,
        language=document.language,
        offer_id=document.offer_id,
        created_at=document.created_at,
        versions=[_version_response(v) for v in versions],
    )


@router.post("/generate", response_model=GeneratedDocumentResponse, status_code=201)
async def generate_resume(
    body: GenerateResumeRequest, session: SessionDep, owner_id: Owner
) -> GeneratedDocumentResponse:
    """Génère un CV depuis le profil validé, compilé en PDF et audité pour les ATS."""
    document, version, _ = await build_resume_service(session).generate_tailored_resume(
        owner_id=owner_id,
        offer_id=body.offer_id,
        options=ResumeGenerationOptions(
            title=body.title,
            target_role=body.target_role,
            language=body.language,
            style=body.style,
            length_target=body.length_target,
            max_experiences=body.max_experiences,
            custom_summary=body.custom_summary,
        ),
    )
    return _document_response(document, [version])


@router.post("/{document_id}/compile", response_model=DocumentVersionResponse, status_code=201)
async def compile_custom_version(
    document_id: uuid.UUID, body: CompileVersionRequest, session: SessionDep, owner_id: Owner
) -> DocumentVersionResponse:
    """Compile une source LaTeX modifiée et enregistre une nouvelle version immuable."""
    version, _ = await build_resume_service(session).compile_custom_version(
        owner_id=owner_id,
        document_id=document_id,
        latex_source=body.latex_source,
        expected_keywords=tuple(body.expected_keywords),
    )
    return _version_response(version)


@router.get("", response_model=list[GeneratedDocumentResponse])
async def list_resumes(
    session: SessionDep, owner_id: Owner, offer_id: Annotated[uuid.UUID | None, Query()] = None
) -> list[GeneratedDocumentResponse]:
    """Liste les CV du candidat."""
    library = build_resume_service(session).library
    documents = await library.list_documents(owner_id=owner_id, offer_id=offer_id)
    return [
        _document_response(d, await library.list_versions(owner_id=owner_id, document_id=d.id))
        for d in documents
    ]


@router.get("/{document_id}", response_model=GeneratedDocumentResponse)
async def get_resume(
    document_id: uuid.UUID, session: SessionDep, owner_id: Owner
) -> GeneratedDocumentResponse:
    """Détail d'un CV et historique de ses versions."""
    library = build_resume_service(session).library
    document = await library.get_document(owner_id=owner_id, document_id=document_id)
    versions = await library.list_versions(owner_id=owner_id, document_id=document.id)
    return _document_response(document, versions)


@router.get("/{document_id}/versions/{version}/pdf")
async def download_pdf(
    document_id: uuid.UUID, version: int, session: SessionDep, owner_id: Owner
) -> Response:
    """Télécharge le PDF d'une version (TASK-012-24)."""
    contenu, nom = await build_resume_service(session).library.download_pdf(
        owner_id=owner_id, document_id=document_id, version=version
    )
    return Response(content=contenu, media_type="application/pdf", headers=attachment_headers(nom))


@router.get("/{document_id}/versions/{version}/latex")
async def download_latex(
    document_id: uuid.UUID, version: int, session: SessionDep, owner_id: Owner
) -> Response:
    """Télécharge le source LaTeX d'une version (TASK-012-25)."""
    source, nom = await build_resume_service(session).library.download_latex(
        owner_id=owner_id, document_id=document_id, version=version
    )
    return Response(
        content=source, media_type="text/plain; charset=utf-8", headers=attachment_headers(nom)
    )


@router.get("/{document_id}/compare", response_model=ComparisonResponse)
async def compare_versions(
    document_id: uuid.UUID,
    session: SessionDep,
    owner_id: Owner,
    version_a: Annotated[int, Query(ge=1)],
    version_b: Annotated[int, Query(ge=1)],
) -> ComparisonResponse:
    """Diff LaTeX et écart de score ATS entre deux versions (TASK-012-26)."""
    comparaison = await build_resume_service(session).library.compare_versions(
        owner_id=owner_id, document_id=document_id, version_a=version_a, version_b=version_b
    )
    return ComparisonResponse(
        document_id=comparaison.document_id,
        version_a=comparaison.version_a,
        version_b=comparaison.version_b,
        diff_latex=comparaison.diff_latex,
        score_a=comparaison.score_a,
        score_b=comparaison.score_b,
        size_diff_bytes=comparaison.size_diff_bytes,
    )


@router.post("/audit-ats", response_model=ATSReportResponse)
async def audit_ats(file: Annotated[UploadFile, File()]) -> ATSReportResponse:
    """Audite un PDF importé (5 Mo maximum, signature PDF vérifiée)."""
    contenu = await file.read(MAX_AUDIT_PDF_BYTES + 1)
    if not contenu:
        raise HTTPException(status_code=400, detail="Fichier PDF vide.")
    if len(contenu) > MAX_AUDIT_PDF_BYTES:
        raise HTTPException(status_code=413, detail="PDF trop volumineux (5 Mo maximum).")
    if not contenu.startswith(_PDF_MAGIC):
        raise HTTPException(status_code=415, detail="Le fichier n'est pas un PDF.")

    rapport = await ResumeService.audit_pdf(contenu)
    return ATSReportResponse.model_validate(rapport.to_dict())
