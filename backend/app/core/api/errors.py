"""Erreurs HTTP normalisées : `{"error": {"code", "message"}}`, jamais de trace côté client."""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def error_response(
    status: int, code: str, message: str, details: list[dict[str, str]] | None = None
) -> JSONResponse:
    corps: dict[str, object] = {"code": code, "message": message}
    if details:
        corps["details"] = details
    return JSONResponse(status_code=status, content={"error": corps})


def register_error_handlers(application: FastAPI) -> None:
    @application.exception_handler(RequestValidationError)
    async def _validation(_: Request, erreur: RequestValidationError) -> JSONResponse:
        # `loc[0]` désigne l'emplacement (query, body, path) : inutile au client.
        # Seuls le champ et le message sont renvoyés : la valeur reçue n'est jamais réécrite.
        details = [
            {"field": ".".join(str(p) for p in e["loc"][1:]), "message": str(e["msg"])}
            for e in erreur.errors()
        ]
        return error_response(
            422, "validation_error", "Les données envoyées sont invalides.", details
        )

    @application.exception_handler(HTTPException)
    async def _http(_: Request, erreur: HTTPException) -> JSONResponse:
        return error_response(erreur.status_code, "http_error", str(erreur.detail))

    @application.exception_handler(Exception)
    async def _inattendue(_: Request, erreur: Exception) -> JSONResponse:
        logger.error("Erreur inattendue", exc_info=erreur)
        return error_response(500, "internal_error", "Erreur interne.")
