"""Tests de l'audit de compatibilité ATS sur document PDF réel (FEATURE 012.4)."""

import pytest

from app.modules.document_generation.domain.ats_analyzer import analyze_pdf_ats
from app.modules.document_generation.infrastructure.latex_compiler import (
    IsolatedLaTeXCompiler,
)


@pytest.fixture
def compiler() -> IsolatedLaTeXCompiler:
    return IsolatedLaTeXCompiler()


async def test_audit_ats_sur_cv_compilable(compiler: IsolatedLaTeXCompiler) -> None:
    """Vérifie l'audit complet sur un PDF réellement généré (TASK-012-17 à 21)."""
    tex = r"""\documentclass[10pt,a4paper]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\usepackage{geometry}
\geometry{a4paper, margin=1.5cm}
\pagestyle{empty}

\begin{document}
\begin{center}
    {\LARGE\bfseries Thomas Bernard} \\[0.4em]
    {\large Développeur Backend Python} \\[0.4em]
    Paris, France $\cdot$ thomas@example.com
\end{center}

\section*{Profil professionnel}
Ingénieur logiciel passionné par les systèmes distribués et le Clean Code.

\section*{Expériences professionnelles}
\textbf{Lead Developer} -- Entreprise Tech \hfill 2021 -- Présent \\
Développement d'APIs haute performance avec FastAPI et PostgreSQL.

\section*{Compétences techniques}
Python, FastAPI, Docker, PostgreSQL, Clean Architecture.

\section*{Formation}
\textbf{Master Informatique} -- Université Paris-Saclay \hfill 2018 -- 2020

\end{document}
"""
    pdf_bytes = await compiler.compile(tex)

    # Audit ATS avec mots-clés attendus
    report = analyze_pdf_ats(
        pdf_bytes,
        expected_keywords=("Python", "FastAPI", "PostgreSQL"),
    )

    # Critères de validation
    assert report.passed is True
    assert report.score >= 80
    assert report.page_count == 1
    assert report.word_count > 30
    assert report.reading_order_valid is True
    assert report.accents_preserved is True
    assert report.single_column is True

    # Mots-clés trouvés
    assert "Python" in report.keywords_found
    assert "FastAPI" in report.keywords_found
    assert "PostgreSQL" in report.keywords_found


def test_audit_sur_pdf_invalide_ou_vide() -> None:
    """Vérifie la robustesse en cas de PDF corrompu (TASK-012-17)."""
    report = analyze_pdf_ats(b"Faux contenu binaire non PDF")
    assert report.passed is False
    assert report.score == 0
    assert report.word_count == 0

