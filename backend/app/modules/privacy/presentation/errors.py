from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.types import ExceptionHandler

from app.core.api.errors import error_response
from app.modules.privacy.domain import exceptions as exc

_MAPPING: tuple[tuple[type[Exception], int, str], ...] = (
    (exc.ConfirmationRequiredError, 422, "confirmation_required"),
    (exc.UnknownCategoryError, 422, "unknown_category"),
    (exc.DeletionBlockedError, 409, "deletion_blocked"),
)


def _handler(statut: int, code: str) -> ExceptionHandler:
    async def _repondre(_: Request, erreur: Exception) -> JSONResponse:
        return error_response(statut, code, str(erreur))

    return _repondre


def register_privacy_errors(application: FastAPI) -> None:
    for erreur, statut, code in _MAPPING:
        application.add_exception_handler(erreur, _handler(statut, code))
