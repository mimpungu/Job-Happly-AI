"""Traduction des erreurs de préparation aux entretiens en réponses HTTP normalisées."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.types import ExceptionHandler

from app.core.api.errors import error_response
from app.modules.interview_preparation.domain import exceptions as exc

_MAPPING: tuple[tuple[type[Exception], int, str], ...] = (
    (exc.PreparationNotFoundError, 404, "preparation_not_found"),
    (exc.SimulationNotFoundError, 404, "simulation_not_found"),
    (exc.InterviewNotFoundError, 404, "interview_not_found"),
    (exc.UnknownQuestionError, 422, "unknown_question"),
    (exc.InvalidInterviewDateError, 422, "invalid_interview_date"),
    (exc.PreparationRequiredError, 409, "preparation_required"),
    (exc.SimulationClosedError, 409, "simulation_closed"),
    (exc.NoValidatedProfileError, 409, "no_validated_profile"),
)


def _handler(statut: int, code: str) -> ExceptionHandler:
    async def _repondre(_: Request, erreur: Exception) -> JSONResponse:
        return error_response(statut, code, str(erreur))

    return _repondre


def register_interview_errors(application: FastAPI) -> None:
    for erreur, statut, code in _MAPPING:
        application.add_exception_handler(erreur, _handler(statut, code))
