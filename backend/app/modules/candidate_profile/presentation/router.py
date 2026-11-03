"""Routes du profil candidat : import d'un CV (lecture seule, rien n'est conservé)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, FastAPI, File, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.types import ExceptionHandler

from app.core.api.errors import error_response
from app.modules.candidate_profile.application.import_document import DocumentReader
from app.modules.candidate_profile.domain.documents import (
    MAX_UPLOAD_BYTES,
    DocumentError,
    DocumentFormat,
    DocumentTooLargeError,
    UnsupportedDocumentError,
    display_filename,
)
from app.modules.candidate_profile.domain.extraction.extractor import extract_profile
from app.modules.candidate_profile.domain.extraction.models import ExtractedProfile
from app.modules.candidate_profile.infrastructure.extraction import extract_document_text

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
    return CvImportResponse(
        filename=display_filename(fichier.filename or ""),
        format=lu.format,
        page_count=lu.page_count,
        warnings=list(lu.warnings),
        text=lu.text,
        proposed_profile=extract_profile(lu.text),
    )


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


def register_document_errors(application: FastAPI) -> None:
    application.add_exception_handler(DocumentError, _gestionnaire())
