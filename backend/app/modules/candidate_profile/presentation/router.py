"""Routes du profil candidat : import d'un CV (lecture seule, rien n'est conservé)."""

from __future__ import annotations

import uuid
from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, File, Query, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.types import ExceptionHandler

from app.core.api.dependencies import SessionDep, get_owner_id
from app.core.api.errors import error_response
from app.modules.candidate_profile.application.country_resolver import build_country_resolver
from app.modules.candidate_profile.application.import_document import DocumentReader
from app.modules.candidate_profile.application.profile_service import ProfileService
from app.modules.candidate_profile.domain.documents import (
    MAX_UPLOAD_BYTES,
    DocumentError,
    DocumentFormat,
    DocumentTooLargeError,
    UnsupportedDocumentError,
    display_filename,
)
from app.modules.candidate_profile.domain.extraction.extractor import extract_profile
from app.modules.candidate_profile.domain.extraction.geography import CountryResolver
from app.modules.candidate_profile.domain.extraction.models import ExtractedProfile
from app.modules.candidate_profile.domain.profile import ProfileDocument
from app.modules.candidate_profile.domain.proposal import proposal_to_document
from app.modules.candidate_profile.domain.repository import (
    ChangeRecord,
    DraftExistsError,
    NoDraftError,
    ProfileIncompleteError,
    ProfileMeta,
    ProfileNotFoundError,
    StoredProfile,
    UnknownItemError,
)
from app.modules.candidate_profile.domain.text_columns import readable_text
from app.modules.candidate_profile.infrastructure.extraction import extract_document_text
from app.modules.candidate_profile.infrastructure.profile_repository import SqlProfileRepository
from app.modules.localization.infrastructure.cldr import BabelGeographyReference

router = APIRouter(prefix="/api/v1/profile", tags=["candidate-profile"])

_CHUNK = 64 * 1024
_TROP_GROS = f"Le fichier dépasse {MAX_UPLOAD_BYTES // (1024 * 1024)} Mo."


class CvImportResponse(BaseModel):
    filename: str
    format: DocumentFormat
    page_count: int | None
    warnings: list[str]
    text: str
    proposed_profile: ExtractedProfile
    # Même proposition sous forme de brouillon éditable : éléments importés, non validés.
    proposed_document: ProfileDocument


@lru_cache(maxsize=1)
def _country_resolver() -> CountryResolver:
    """Noms de pays du référentiel CLDR : construits une fois, réutilisés à chaque import."""
    return build_country_resolver(BabelGeographyReference())


async def _lire_borne(fichier: UploadFile) -> bytes:
    """Lit le fichier par morceaux et s'arrête dès que la limite est dépassée.

    Un `Content-Length` annoncé peut mentir : seule la lecture bornée protège la mémoire.
    """
    morceaux: list[bytes] = []
    total = 0
    while chunk := await fichier.read(_CHUNK):
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise DocumentTooLargeError(_TROP_GROS)
        morceaux.append(chunk)
    return b"".join(morceaux)


@router.post("/import", response_model=CvImportResponse)
async def import_cv(fichier: Annotated[UploadFile, File()], request: Request) -> CvImportResponse:
    """Lit un CV (PDF, DOCX, TXT) et propose un profil à valider. Le fichier n'est pas conservé."""
    annonce = request.headers.get("content-length")
    # Garde-fou rapide ; la marge couvre l'enveloppe multipart autour du fichier.
    if annonce and annonce.isdigit() and int(annonce) > MAX_UPLOAD_BYTES + 64 * 1024:
        raise DocumentTooLargeError(_TROP_GROS)
    contenu = await _lire_borne(fichier)
    lu = await DocumentReader(extract_document_text).read(fichier.filename or "", contenu)
    proposition = extract_profile(lu.text, country_of=_country_resolver())
    return CvImportResponse(
        filename=display_filename(fichier.filename or ""),
        format=lu.format,
        page_count=lu.page_count,
        warnings=list(lu.warnings),
        text=readable_text(lu.text),
        proposed_profile=proposition,
        proposed_document=proposal_to_document(proposition),
    )


class ProfileResponse(BaseModel):
    meta: ProfileMeta
    document: ProfileDocument

    @classmethod
    def of(cls, stocke: StoredProfile) -> ProfileResponse:
        return cls(meta=stocke.meta, document=stocke.document)


def _service(session: AsyncSession) -> ProfileService:
    return ProfileService(SqlProfileRepository(session))


Owner = Annotated[uuid.UUID, Depends(get_owner_id)]


@router.get("", response_model=ProfileResponse | None)
async def get_profile(session: SessionDep, owner_id: Owner) -> ProfileResponse | None:
    """Dernière version du profil maître (brouillon ou validée) ; `null` s'il n'existe pas."""
    stocke = await _service(session).current(owner_id=owner_id)
    return ProfileResponse.of(stocke) if stocke else None


@router.put("/draft", response_model=ProfileResponse)
async def save_draft(
    session: SessionDep, owner_id: Owner, document: ProfileDocument
) -> ProfileResponse:
    """Enregistre le brouillon (créé à la première sauvegarde)."""
    stocke = await _service(session).save_draft(owner_id=owner_id, document=document)
    return ProfileResponse.of(stocke)


@router.post("/versions", response_model=ProfileResponse, status_code=201)
async def new_version(session: SessionDep, owner_id: Owner) -> ProfileResponse:
    """Nouveau brouillon copié de la dernière version validée."""
    return ProfileResponse.of(await _service(session).start_new_version(owner_id=owner_id))


@router.post("/validate", response_model=ProfileResponse)
async def validate_profile(session: SessionDep, owner_id: Owner) -> ProfileResponse:
    return ProfileResponse.of(await _service(session).validate(owner_id=owner_id))


@router.get("/versions", response_model=list[ProfileMeta])
async def list_versions(session: SessionDep, owner_id: Owner) -> tuple[ProfileMeta, ...]:
    return await _service(session).versions(owner_id=owner_id)


@router.get("/versions/{version}", response_model=ProfileResponse)
async def get_version(session: SessionDep, owner_id: Owner, version: int) -> ProfileResponse:
    return ProfileResponse.of(await _service(session).version(owner_id=owner_id, version=version))


@router.get("/history", response_model=list[ChangeRecord])
async def history(
    session: SessionDep, owner_id: Owner, limit: Annotated[int, Query(ge=1, le=500)] = 100
) -> tuple[ChangeRecord, ...]:
    return await _service(session).history(owner_id=owner_id, limit=limit)


def _statut(erreur: DocumentError) -> int:
    if isinstance(erreur, DocumentTooLargeError):
        return 413
    if isinstance(erreur, UnsupportedDocumentError):
        return 415
    return 422


def _gestionnaire() -> ExceptionHandler:
    async def _repondre(_: Request, erreur: Exception) -> JSONResponse:
        assert isinstance(erreur, DocumentError)  # noqa: S101  (garanti par l'enregistrement)
        # Les messages des erreurs de document sont écrits pour l'utilisateur, sans détail interne.
        return error_response(_statut(erreur), "document_error", str(erreur))

    return _repondre


def _simple(statut: int, code: str, message: str | None = None) -> ExceptionHandler:
    async def _repondre(_: Request, erreur: Exception) -> JSONResponse:
        # Messages des erreurs de profil : rédigés pour l'utilisateur, sans détail interne.
        return error_response(statut, code, message or str(erreur))

    return _repondre


async def _incomplet(_: Request, erreur: Exception) -> JSONResponse:
    assert isinstance(erreur, ProfileIncompleteError)  # noqa: S101  (garanti par l'enregistrement)
    details = [{"field": i.path, "message": i.message} for i in erreur.issues]
    return error_response(422, "profile_incomplete", "Le profil est incomplet.", details)


def register_document_errors(application: FastAPI) -> None:
    application.add_exception_handler(DocumentError, _gestionnaire())
    application.add_exception_handler(
        ProfileNotFoundError, _simple(404, "profile_not_found", "Profil ou version introuvable.")
    )
    application.add_exception_handler(NoDraftError, _simple(409, "no_draft"))
    application.add_exception_handler(DraftExistsError, _simple(409, "draft_exists"))
    application.add_exception_handler(UnknownItemError, _simple(422, "unknown_item"))
    application.add_exception_handler(ProfileIncompleteError, _incomplet)
