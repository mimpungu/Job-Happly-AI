"""Fixtures communes de la génération de documents.

Les tests de compilation réelle exigent pdfLaTeX. En local sans TeX Live ils sont ignorés
avec une raison explicite ; en CI (`HAPPLY_REQUIRE_PDFLATEX=1`) son absence est une erreur,
pour qu'aucun test ne soit ignoré en silence.
"""

import os
import shutil

import pytest

from app.modules.document_generation.infrastructure.latex_compiler import IsolatedLaTeXCompiler


@pytest.fixture
def compiler() -> IsolatedLaTeXCompiler:
    if shutil.which("pdflatex") is None:
        message = "pdflatex introuvable (installer TeX Live) : compilation réelle non testée."
        if os.environ.get("HAPPLY_REQUIRE_PDFLATEX"):
            pytest.fail(message)
        pytest.skip(message)
    return IsolatedLaTeXCompiler()
