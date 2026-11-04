"""Tests de la compilation pdfLaTeX isolée et sécurisée (FEATURE 012.3)."""

import pytest

from app.modules.document_generation.application.ports import (
    CompilationTimeoutError,
    LaTeXCompilationError,
    LaTeXSourceTooLargeError,
)
from app.modules.document_generation.infrastructure.latex_compiler import (
    IsolatedLaTeXCompiler,
)


@pytest.fixture
def compiler() -> IsolatedLaTeXCompiler:
    return IsolatedLaTeXCompiler()


async def test_compilation_reelle_d_un_document_valide(compiler: IsolatedLaTeXCompiler) -> None:
    """Vérifie la compilation réelle d'un document complet en PDF (TASK-012-12, 13, 16)."""
    latex_source = r"""\documentclass{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\begin{document}
\section*{Curriculum Vitae}
Développeur Senior avec maîtrise des accents : élève, naïve, cœur.
\end{document}
"""
    pdf_bytes = await compiler.compile(latex_source)
    assert len(pdf_bytes) > 1000
    # Vérifie le magic number PDF %PDF-
    assert pdf_bytes.startswith(b"%PDF-")


async def test_gestion_erreur_de_compilation_latex(compiler: IsolatedLaTeXCompiler) -> None:
    """Vérifie le diagnostic et la capture d'erreur TeX (TASK-012-14)."""
    syntaxe_invalide = r"""\documentclass{article}
\begin{document}
\commandeInconnueQuiPlante
\end{document}
"""
    with pytest.raises(LaTeXCompilationError) as exc_info:
        await compiler.compile(syntaxe_invalide)

    assert "Échec compilation pdfLaTeX" in str(exc_info.value)
    assert exc_info.value.log_snippet is not None


async def test_limite_de_taille_source_latex() -> None:
    """Vérifie le rejet immédiat d'une source trop volumineuse (TASK-012-15)."""
    compiler = IsolatedLaTeXCompiler()
    source_geante = r"\documentclass{article}" + ("% commentaire\n" * 100_000)

    with pytest.raises(LaTeXSourceTooLargeError):
        await compiler.compile(source_geante)


async def test_limite_de_temps_timeout() -> None:
    """Vérifie l'interruption par timeout en cas de boucle infinie (TASK-012-15)."""
    compiler = IsolatedLaTeXCompiler(timeout_seconds=0.5)
    # Boucle TeX infinie
    boucle_infinie = r"""\documentclass{article}
\begin{document}
\def\loopme{\loopme}\loopme
\end{document}
"""
    with pytest.raises(CompilationTimeoutError):
        await compiler.compile(boucle_infinie)
