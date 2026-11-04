"""Traduction des erreurs du suivi de candidatures en réponses HTTP normalisées."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.types import ExceptionHandler

from app.core.api.errors import error_response
from app.modules.application_management.domain import exceptions as exc

# (exception, statut HTTP, code stable) ; le message est celui, rédigé pour l'utilisateur, de
# l'exception : aucune trace ni détail interne.
_MAPPING: tuple[tuple[type[Exception], int, str], ...] = (
    (exc.ApplicationNotFoundError, 404, "application_not_found"),
    (exc.OfferNotFoundError, 404, "offer_not_found"),
    (exc.DocumentVersionNotFoundError, 404, "document_version_not_found"),
    (exc.DuplicateApplicationError, 409, "duplicate_application"),
    (exc.InvalidStatusTransitionError, 409, "invalid_status_transition"),
    (exc.IncompleteDossierError, 409, "incomplete_dossier"),
    (exc.AlreadySubmittedError, 409, "already_submitted"),
    (exc.DocumentLockedError, 409, "document_locked"),
    (exc.DocumentKindMismatchError, 422, "document_kind_mismatch"),
    (exc.NothingToAttachError, 422, "nothing_to_attach"),
    (exc.InvalidDateError, 422, "invalid_date"),
    (exc.ExternalOfferLinkMissingError, 422, "application_url_unavailable"),
)


def _handler(statut: int, code: str) -> ExceptionHandler:
    async def _repondre(_: Request, erreur: Exception) -> JSONResponse:
        return error_response(statut, code, str(erreur))

    return _repondre


def register_application_errors(application: FastAPI) -> None:
    for erreur, statut, code in _MAPPING:
        application.add_exception_handler(erreur, _handler(statut, code))
