"""Tests de la compilation pdfLaTeX isolée et sécurisée (FEATURE 012.3)."""

import io
import shutil
from pathlib import Path

import pytest
from pypdf import PdfReader

from app.modules.document_generation.application.ports import (
    CompilationTimeoutError,
    CompilerUnavailableError,
    LaTeXCompilationError,
    LaTeXSourceTooLargeError,
    UnsafeLaTeXSourceError,
)
from app.modules.document_generation.infrastructure import latex_compiler
from app.modules.document_generation.infrastructure.latex_compiler import IsolatedLaTeXCompiler

ENTETE = (
    "\\documentclass{article}\n\\usepackage{cmap}\n\\usepackage[utf8]{inputenc}\n"
    "\\usepackage[T1]{fontenc}\n\\usepackage{lmodern}\n\\begin{document}\n"
)


def _texte(pdf: bytes) -> str:
    return "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(pdf)).pages)


async def test_compilation_reelle_d_un_document_valide(compiler: IsolatedLaTeXCompiler) -> None:
    """Compilation réelle d'un document accentué (TASK-012-12, 13)."""
    pdf = await compiler.compile(
        ENTETE + "\\section*{Curriculum Vitae}\nDéveloppeur : élève, naïve, cœur.\n\\end{document}"
    )
    assert pdf.startswith(b"%PDF-")
    assert "Développeur : élève, naïve, cœur." in _texte(pdf)


async def test_gestion_erreur_de_compilation_latex(compiler: IsolatedLaTeXCompiler) -> None:
    """Diagnostic clair d'une erreur TeX (TASK-012-14)."""
    with pytest.raises(LaTeXCompilationError) as erreur:
        await compiler.compile(ENTETE + "\\commandeInconnueQuiPlante\n\\end{document}")

    assert "Échec compilation pdfLaTeX" in str(erreur.value)
    assert "commandeInconnueQuiPlante" in str(erreur.value)
    assert erreur.value.log_snippet is not None


async def test_limite_de_taille_source_latex() -> None:
    """Rejet immédiat d'une source trop volumineuse, sans même chercher pdfLaTeX (012-15)."""
    compiler = IsolatedLaTeXCompiler(pdflatex_path="/nexiste/pas")
    with pytest.raises(LaTeXSourceTooLargeError):
        await compiler.compile("\\documentclass{article}" + ("% commentaire\n" * 100_000))


async def test_limite_de_temps_timeout(compiler: IsolatedLaTeXCompiler) -> None:
    """Boucle TeX infinie : interrompue et groupe de processus tué (TASK-012-15)."""
    court = IsolatedLaTeXCompiler(timeout_seconds=0.5)
    with pytest.raises(CompilationTimeoutError):
        await court.compile(ENTETE + "\\def\\loopme{\\loopme}\\loopme\n\\end{document}")


async def test_sources_dangereuses_refusees_avant_compilation() -> None:
    compiler = IsolatedLaTeXCompiler(pdflatex_path="/nexiste/pas")
    with pytest.raises(UnsafeLaTeXSourceError):
        await compiler.compile(ENTETE + "\\input{/etc/passwd}\n\\end{document}")


async def test_lecture_de_fichier_arbitraire_impossible_meme_sans_denylist(
    compiler: IsolatedLaTeXCompiler, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Seconde barrière : TeX en mode paranoïaque refuse les chemins absolus (CLAUDE.md §11).

    On neutralise la liste de refus pour vérifier que `openin_any=p` suffit seul.
    """
    secret = tmp_path / "secret.txt"
    secret.write_text("CLE-API-CONFIDENTIELLE")
    monkeypatch.setattr(latex_compiler, "validate_latex_source", lambda _: None)

    source = ENTETE + f"\\input{{{secret}}}\n\\end{{document}}"
    try:
        pdf = await compiler.compile(source)
    except LaTeXCompilationError:
        return  # refus de TeX : comportement attendu
    assert "CLE-API-CONFIDENTIELLE" not in _texte(pdf)


async def test_secrets_de_l_environnement_non_transmis(
    compiler: IsolatedLaTeXCompiler, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HAPPLY_GEMINI_API_KEY", "secret-a-ne-pas-fuiter")
    env = compiler._environment(str(tmp_path))
    assert "HAPPLY_GEMINI_API_KEY" not in env
    assert env["openin_any"] == "p"
    assert env["openout_any"] == "p"
    assert env["shell_escape"] == "f"


async def test_pdflatex_absent_leve_une_erreur_d_environnement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La construction du compilateur n'échoue pas : seule la compilation exige pdfLaTeX."""
    monkeypatch.setattr(shutil, "which", lambda _: None)
    monkeypatch.setattr(latex_compiler, "_STANDARD_PATHS", ())
    compiler = IsolatedLaTeXCompiler(pdflatex_path="/nexiste/pas")

    with pytest.raises(CompilerUnavailableError):
        await compiler.compile(ENTETE + "x\n\\end{document}")
