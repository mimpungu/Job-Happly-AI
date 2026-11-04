"""Traduction des erreurs métier en réponses HTTP normalisées (jamais de stack trace)."""

import httpx
import pytest
from fastapi import FastAPI

from app.core.api.errors import register_error_handlers
from app.modules.document_generation.application.ports import (
    CompilationTimeoutError,
    CompilerUnavailableError,
    DocumentNotFoundError,
    DocumentVersionNotFoundError,
    LaTeXCompilationError,
    LaTeXSourceTooLargeError,
    NoValidatedProfileError,
    OfferNotFoundError,
    UnsafeLaTeXSourceError,
)
from app.modules.document_generation.domain.fact_checker import UnverifiedFactError
from app.modules.document_generation.domain.latex_escape import UnsupportedCharactersError
from app.modules.document_generation.presentation.errors import register_generation_errors

CAS: list[tuple[Exception, int, str]] = [
    (DocumentNotFoundError("x"), 404, "document_not_found"),
    (DocumentVersionNotFoundError("x"), 404, "document_version_not_found"),
    (OfferNotFoundError("x"), 404, "offer_not_found"),
    (NoValidatedProfileError(), 409, "no_validated_profile"),
    (UnverifiedFactError("Entreprise non vérifiée"), 422, "unverified_fact"),
    (UnsupportedCharactersError("Ж"), 422, "unsupported_characters"),
    (LaTeXCompilationError("Échec compilation"), 422, "latex_compilation"),
    (CompilationTimeoutError("Délai dépassé"), 422, "latex_compilation"),
    (UnsafeLaTeXSourceError("Commande interdite"), 422, "latex_compilation"),
    (LaTeXSourceTooLargeError("trop gros"), 422, "latex_source_too_large"),
    (CompilerUnavailableError("/usr/bin/secret/chemin"), 503, "latex_compiler_unavailable"),
]


@pytest.mark.parametrize(
    ("erreur", "statut", "code"), CAS, ids=[c[2] + str(i) for i, c in enumerate(CAS)]
)
async def test_erreur_metier_vers_http(erreur: Exception, statut: int, code: str) -> None:
    application = FastAPI()
    register_error_handlers(application)
    register_generation_errors(application)

    @application.get("/boom")
    async def boom() -> None:
        raise erreur

    transport = httpx.ASGITransport(app=application, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        reponse = await client.get("/boom")

    assert reponse.status_code == statut
    assert reponse.json()["error"]["code"] == code


async def test_indisponibilite_du_compilateur_ne_divulgue_pas_de_chemin() -> None:
    application = FastAPI()
    register_generation_errors(application)

    @application.get("/boom")
    async def boom() -> None:
        raise CompilerUnavailableError("/usr/bin/secret/chemin")

    transport = httpx.ASGITransport(app=application, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        reponse = await client.get("/boom")

    assert "secret" not in reponse.text
