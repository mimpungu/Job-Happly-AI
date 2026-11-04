"""Traduction des erreurs de génération de documents en réponses HTTP normalisées."""

from __future__ import annotations

from fastapi import FastAPI
from starlette.types import ExceptionHandler

from app.core.api.errors import error_response
from app.modules.document_generation.application.ports import (
    CompilerUnavailableError,
    DocumentNotFoundError,
    DocumentVersionNotFoundError,
    LaTeXCompilationError,
    LaTeXSourceTooLargeError,
    NoValidatedProfileError,
    OfferNotFoundError,
)
from app.modules.document_generation.domain.cover_letter_models import IncompleteProfileError
from app.modules.document_generation.domain.fact_checker import UnverifiedFactError
from app.modules.document_generation.domain.latex_escape import UnsupportedCharactersError


def _simple(statut: int, code: str, message: str | None = None) -> ExceptionHandler:
    async def _repondre(_: object, erreur: Exception) -> object:
        # Messages rédigés pour l'utilisateur ; aucune trace ni chemin interne.
        return error_response(statut, code, message or str(erreur))

    return _repondre  # type: ignore[return-value]


def register_generation_errors(application: FastAPI) -> None:
    application.add_exception_handler(
        DocumentNotFoundError, _simple(404, "document_not_found", "Document introuvable.")
    )
    application.add_exception_handler(
        DocumentVersionNotFoundError,
        _simple(404, "document_version_not_found", "Version de document introuvable."),
    )
    application.add_exception_handler(
        OfferNotFoundError, _simple(404, "offer_not_found", "Offre d'emploi introuvable.")
    )
    application.add_exception_handler(
        NoValidatedProfileError,
        _simple(
            409,
            "no_validated_profile",
            "Aucun profil validé : validez votre profil maître avant de générer un document.",
        ),
    )
    application.add_exception_handler(UnverifiedFactError, _simple(422, "unverified_fact"))
    application.add_exception_handler(IncompleteProfileError, _simple(422, "incomplete_profile"))
    application.add_exception_handler(
        UnsupportedCharactersError, _simple(422, "unsupported_characters")
    )
    application.add_exception_handler(LaTeXCompilationError, _simple(422, "latex_compilation"))
    application.add_exception_handler(
        LaTeXSourceTooLargeError, _simple(422, "latex_source_too_large")
    )
    application.add_exception_handler(
        CompilerUnavailableError,
        _simple(
            503,
            "latex_compiler_unavailable",
            "Le compilateur LaTeX n'est pas disponible sur ce serveur.",
        ),
    )
