"""Routes de génération de lettres de motivation (EPIC 013). Routes minces : tout passe par
`CoverLetterService` ; les erreurs métier sont traduites par `presentation/errors.py`."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.core.api.dependencies import SessionDep, get_owner_id
from app.modules.document_generation.domain.cover_letter_models import (
    CoverLetterContent,
    CoverLetterOptions,
)
from app.modules.document_generation.infrastructure.composition import build_cover_letter_service
from app.modules.document_generation.infrastructure.models import (
    DocumentVersionModel,
    GeneratedDocumentModel,
)
from app.modules.document_generation.presentation.cover_letter_schemas import (
    CoverLetterAuditResponse,
    CoverLetterContentResponse,
    CoverLetterGenerationMeta,
    CoverLetterResponse,
    CoverLetterVersionResponse,
    GenerateCoverLetterRequest,
)
from app.modules.document_generation.presentation.downloads import attachment_headers
from app.modules.document_generation.presentation.schemas import (
    ComparisonResponse,
    CompileVersionRequest,
)

router = APIRouter(prefix="/api/v1/cover-letters", tags=["cover-letter-generator"])
Owner = Annotated[uuid.UUID, Depends(get_owner_id)]


def _version_response(version: DocumentVersionModel) -> CoverLetterVersionResponse:
    rapport = version.ats_report
    meta = rapport.get("generation") if rapport else None
    return CoverLetterVersionResponse(
        id=version.id,
        version=version.version,
        created_at=version.created_at,
        size_bytes=version.size_bytes,
        sha256=version.sha256,
        audit=CoverLetterAuditResponse.model_validate(rapport) if rapport else None,
        generation=CoverLetterGenerationMeta.model_validate(meta) if meta else None,
    )


def _letter_response(
    document: GeneratedDocumentModel,
    versions: list[DocumentVersionModel],
    content: CoverLetterContent | None = None,
) -> CoverLetterResponse:
    return CoverLetterResponse(
        id=document.id,
        kind=document.kind,
        title=document.title,
        language=document.language,
        offer_id=document.offer_id,
        created_at=document.created_at,
        versions=[_version_response(v) for v in versions],
        content=(
            CoverLetterContentResponse.model_validate(
                {**content.__dict__, "word_count": content.word_count}
            )
            if content
            else None
        ),
    )


@router.post("/generate", response_model=CoverLetterResponse, status_code=201)
async def generate_cover_letter(
    body: GenerateCoverLetterRequest, session: SessionDep, owner_id: Owner
) -> CoverLetterResponse:
    """Génère la lettre depuis le profil validé et l'offre ciblée, compilée en PDF et auditée."""
    document, version, content, _ = await build_cover_letter_service(
        session
    ).generate_tailored_letter(
        owner_id=owner_id,
        offer_id=body.offer_id,
        options=CoverLetterOptions(
            language=body.language,
            country_code=body.country_code,
            recipient_name=body.recipient_name,
            recipient_department=body.recipient_department,
            custom_opening=body.custom_opening,
            motivation=body.motivation,
        ),
    )
    return _letter_response(document, [version], content)


@router.post("/{document_id}/compile", response_model=CoverLetterVersionResponse, status_code=201)
async def compile_custom_version(
    document_id: uuid.UUID, body: CompileVersionRequest, session: SessionDep, owner_id: Owner
) -> CoverLetterVersionResponse:
    """Compile une version éditée de la lettre ; elle est réellement auditée."""
    version, _ = await build_cover_letter_service(session).compile_custom_version(
        owner_id=owner_id, document_id=document_id, latex_source=body.latex_source
    )
    return _version_response(version)


@router.get("", response_model=list[CoverLetterResponse])
async def list_cover_letters(
    session: SessionDep, owner_id: Owner, offer_id: Annotated[uuid.UUID | None, Query()] = None
) -> list[CoverLetterResponse]:
    """Liste les lettres du candidat."""
    library = build_cover_letter_service(session).library
    documents = await library.list_documents(owner_id=owner_id, offer_id=offer_id)
    return [
        _letter_response(d, await library.list_versions(owner_id=owner_id, document_id=d.id))
        for d in documents
    ]


@router.get("/{document_id}", response_model=CoverLetterResponse)
async def get_cover_letter(
    document_id: uuid.UUID, session: SessionDep, owner_id: Owner
) -> CoverLetterResponse:
    """Détail d'une lettre et historique de ses versions."""
    library = build_cover_letter_service(session).library
    document = await library.get_document(owner_id=owner_id, document_id=document_id)
    versions = await library.list_versions(owner_id=owner_id, document_id=document.id)
    return _letter_response(document, versions)


@router.get("/{document_id}/versions/{version}/pdf")
async def download_pdf(
    document_id: uuid.UUID, version: int, session: SessionDep, owner_id: Owner
) -> Response:
    """Télécharge le PDF d'une version."""
    contenu, nom = await build_cover_letter_service(session).library.download_pdf(
        owner_id=owner_id, document_id=document_id, version=version
    )
    return Response(content=contenu, media_type="application/pdf", headers=attachment_headers(nom))


@router.get("/{document_id}/versions/{version}/latex")
async def download_latex(
    document_id: uuid.UUID, version: int, session: SessionDep, owner_id: Owner
) -> Response:
    """Télécharge le source LaTeX d'une version."""
    source, nom = await build_cover_letter_service(session).library.download_latex(
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
    """Diff LaTeX et écart de score entre deux versions."""
    comparaison = await build_cover_letter_service(session).library.compare_versions(
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
