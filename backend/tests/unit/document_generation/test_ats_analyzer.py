"""Tests de l'audit ATS sur des PDF réellement compilés (FEATURE 012.4)."""

import pytest

from app.modules.document_generation.domain.ats_analyzer import analyze_pdf_ats
from app.modules.document_generation.domain.enums import ATSCheckStatus, LengthTarget
from app.modules.document_generation.domain.models import ATSReport
from app.modules.document_generation.infrastructure.latex_compiler import IsolatedLaTeXCompiler

ENTETE = (
    "\\documentclass[10pt,a4paper]{article}\n\\usepackage{cmap}\n"
    "\\usepackage[utf8]{inputenc}\n\\usepackage[T1]{fontenc}\n\\usepackage{lmodern}\n"
    "\\usepackage{multicol}\n\\pagestyle{empty}\n\\begin{document}\n"
)
FIN = "\n\\end{document}\n"

CV_CORRECT = """\\begin{center}{\\LARGE\\bfseries Thomas Bernard}\\\\
Développeur Backend Python\\end{center}
\\section*{Profil professionnel}
Ingénieur logiciel spécialisé dans les systèmes distribués et la qualité de code.
\\section*{Expériences professionnelles}
\\textbf{Lead Developer} -- Entreprise Tech \\hfill 2021 -- Présent \\\\
Développement d'APIs avec FastAPI et PostgreSQL pour une plateforme de paiement.
\\section*{Compétences techniques}
Python, FastAPI, Docker, PostgreSQL, Clean Architecture.
\\section*{Formation}
\\textbf{Master Informatique} -- Université Paris-Saclay \\hfill 2018 -- 2020"""


async def _auditer(compiler: IsolatedLaTeXCompiler, corps: str, **options: object) -> ATSReport:
    pdf = await compiler.compile(ENTETE + corps + FIN)
    return analyze_pdf_ats(pdf, **options)  # type: ignore[arg-type]


def _statut(rapport: ATSReport, nom: str) -> ATSCheckStatus:
    return next(c.status for c in rapport.checks if c.name.startswith(nom))


async def test_cv_correct_est_conforme(compiler: IsolatedLaTeXCompiler) -> None:
    rapport = await _auditer(
        compiler,
        CV_CORRECT,
        expected_keywords=("Python", "FastAPI", "PostgreSQL", "Rust"),
        expected_phrases=("Thomas Bernard", "Université Paris-Saclay", "Développement d'APIs"),
        expected_sections=("summary", "experience", "skills", "education"),
        length_target=LengthTarget.ONE_PAGE,
    )

    assert rapport.passed is True
    assert rapport.score == 100
    assert rapport.page_count == 1
    assert rapport.single_column is True
    assert rapport.reading_order_valid is True
    assert rapport.accents_preserved is True
    assert set(rapport.keywords_found) == {"Python", "FastAPI", "PostgreSQL"}
    assert rapport.keywords_missing == ("Rust",)


async def test_deux_colonnes_sont_detectees(compiler: IsolatedLaTeXCompiler) -> None:
    """Un PDF multi-colonnes ne doit JAMAIS être déclaré mono-colonne (TASK-012-21)."""
    texte = "Lorem ipsum dolor sit amet consectetur. " * 30
    corps = (
        "\\begin{multicols}{2}\\section*{Expériences professionnelles}"
        f"{texte}\\section*{{Formation}}{texte}\\end{{multicols}}"
    )
    rapport = await _auditer(compiler, corps)

    assert rapport.single_column is False
    assert rapport.passed is False
    assert _statut(rapport, "Structure mono-colonne") is ATSCheckStatus.FAIL


async def test_blocs_cote_a_cote_sont_detectes(compiler: IsolatedLaTeXCompiler) -> None:
    corps = (
        "\\noindent\\begin{minipage}{.45\\textwidth}Colonne gauche : première ligne du bloc.\\par "
        "Deuxième ligne du bloc gauche.\\end{minipage}\\hfill"
        "\\begin{minipage}{.45\\textwidth}Colonne droite : première ligne du bloc.\\par "
        "Deuxième ligne du bloc droit.\\end{minipage}"
    )
    rapport = await _auditer(compiler, corps)
    assert rapport.single_column is False


async def test_ordre_de_lecture_inverse_est_signale(compiler: IsolatedLaTeXCompiler) -> None:
    """TASK-012-18 : Formation avant Expériences n'est pas l'ordre standard."""
    corps = (
        "\\section*{Formation}Master Informatique à Lyon, promotion 2020, mention bien.\n"
        "\\section*{Compétences techniques}Python, SQL, Docker et Linux au quotidien.\n"
        "\\section*{Expériences professionnelles}Développeur Python chez Acme pendant trois ans."
    )
    rapport = await _auditer(compiler, corps)

    assert rapport.reading_order_valid is False
    assert _statut(rapport, "Ordre de lecture") is ATSCheckStatus.WARNING
    assert rapport.single_column is True  # seul l'ordre des rubriques est en cause


async def test_rubrique_manquante_est_signalee(compiler: IsolatedLaTeXCompiler) -> None:
    """TASK-012-20 : seules les lignes de titre comptent, pas le mot dans un paragraphe."""
    corps = (
        "\\section*{Expériences professionnelles}Développeur. J'ai une formation solide et "
        "des compétences variées en ingénierie logicielle moderne et en architecture.\n"
        "\\section*{Compétences techniques}Python, SQL, Docker."
    )
    rapport = await _auditer(compiler, corps)

    statut = _statut(rapport, "Rubriques standards")
    assert statut is ATSCheckStatus.WARNING
    details = next(c for c in rapport.checks if c.name == "Rubriques standards")
    assert "education" in details.message


async def test_rubrique_non_exigee_n_est_pas_penalisee(compiler: IsolatedLaTeXCompiler) -> None:
    corps = (
        "\\section*{Expériences professionnelles}Développeur Python depuis plusieurs années.\n"
        "\\section*{Compétences techniques}Python, SQL, Docker et Linux."
    )
    rapport = await _auditer(compiler, corps, expected_sections=("experience", "skills"))
    assert _statut(rapport, "Rubriques standards") is ATSCheckStatus.PASS


async def test_phrase_attendue_absente_est_une_alteration(compiler: IsolatedLaTeXCompiler) -> None:
    """TASK-012-19 : un nom attendu mais absent du texte extrait = accents perdus."""
    rapport = await _auditer(compiler, CV_CORRECT, expected_phrases=("Hélène Müller-Çelik",))

    assert rapport.accents_preserved is False
    assert _statut(rapport, "Intégrité typographique") is ATSCheckStatus.FAIL
    assert rapport.passed is False


async def test_accents_internationaux_conserves(compiler: IsolatedLaTeXCompiler) -> None:
    rapport = await _auditer(
        compiler,
        "\\section*{Expériences professionnelles}Łukasz Wójcik, Ünal Çelik, São Paulo, "
        "œuvre, naïveté, Zürich : développement logiciel pour des clients européens.",
        expected_phrases=("Łukasz Wójcik", "Ünal Çelik", "São Paulo", "œuvre", "Zürich"),
    )
    assert rapport.accents_preserved is True


async def test_une_page_demandee_deux_obtenues(compiler: IsolatedLaTeXCompiler) -> None:
    corps = ("Paragraphe de remplissage assez long pour déborder. " * 25 + "\\par\n") * 6
    rapport = await _auditer(compiler, corps, length_target=LengthTarget.ONE_PAGE)

    assert rapport.page_count > 1
    assert _statut(rapport, "Mise en page : longueur") is ATSCheckStatus.WARNING


async def test_police_trop_petite_est_signalee(compiler: IsolatedLaTeXCompiler) -> None:
    rapport = await _auditer(
        compiler, "{\\tiny " + "Texte minuscule illisible pour un recruteur. " * 12 + "}"
    )
    assert _statut(rapport, "Mise en page : police") is ATSCheckStatus.WARNING


async def test_mots_cles_ne_matchent_pas_une_sous_chaine(compiler: IsolatedLaTeXCompiler) -> None:
    """« Go » ne doit pas être trouvé dans « Google » ni « C » dans « Clean »."""
    rapport = await _auditer(
        compiler,
        "\\section*{Compétences techniques}Google Cloud, Clean Code, C++ et Python.",
        expected_keywords=("Go", "C", "C++", "Python"),
    )
    assert set(rapport.keywords_found) == {"C++", "Python"}
    assert set(rapport.keywords_missing) == {"Go", "C"}


@pytest.mark.parametrize("contenu", [b"Faux contenu binaire non PDF", b"", b"%PDF-1.4 tronque"])
def test_pdf_invalide_ou_illisible(contenu: bytes) -> None:
    rapport = analyze_pdf_ats(contenu, expected_keywords=("Python",))

    assert rapport.passed is False
    assert rapport.score == 0
    assert rapport.word_count == 0
    assert rapport.keywords_missing == ("Python",)
