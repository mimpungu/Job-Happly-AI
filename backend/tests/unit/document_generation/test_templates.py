"""Tests unitaires du template LaTeX mono-colonne et des sections standards (FEATURE 012.1)."""

from app.modules.candidate_profile.domain.enums import LanguageProficiency
from app.modules.candidate_profile.domain.profile import (
    CertificationDoc,
    DocDate,
    EducationDoc,
    ExperienceDoc,
    Identity,
    LanguageDoc,
    ProfileDocument,
    SkillDoc,
)
from app.modules.document_generation.domain.enums import LengthTarget
from app.modules.document_generation.domain.templates import render_latex_resume


def _profil_exemple() -> ProfileDocument:
    return ProfileDocument(
        identity=Identity(
            first_name="Jean",
            last_name="Dupont",
            email="jean.dupont@example.com",
            phone="+33 6 12 34 56 78",
            city="Paris",
            country_code="FR",
            headline="Ingénieur Backend Python",
        ),
        summary="Ingénieur backend expérimenté, passionné par la Clean Architecture.",
        experiences=(
            ExperienceDoc(
                title="Lead Tech Python",
                company="Tech Corp & Co",
                location="Paris",
                start=DocDate(year=2021, month=3),
                is_current=True,
                description="Conception d'APIs résilientes et optimisation de la base de données.",
                achievements=("Réduction de la latence de 40%", "Migration vers FastAPI"),
            ),
        ),
        skills=(
            SkillDoc(name="Python", category="Langages"),
            SkillDoc(name="PostgreSQL", category="Base de données"),
            SkillDoc(name="FastAPI", category="Frameworks"),
        ),
        educations=(
            EducationDoc(
                degree="Master Informatique",
                institution="Université de Paris",
                field_of_study="Génie Logiciel",
                start=DocDate(year=2016),
                end=DocDate(year=2018),
            ),
        ),
        certifications=(
            CertificationDoc(
                name="AWS Solutions Architect",
                issuer="Amazon Web Services",
                issued_on=DocDate(year=2023, month=6),
            ),
        ),
        languages=(
            LanguageDoc(
                language_code="fr",
                proficiency=LanguageProficiency.NATIVE,
                level_text="Langue maternelle",
            ),
            LanguageDoc(
                language_code="en",
                proficiency=LanguageProficiency.C1,
                level_text="Courant",
            ),
        ),
    )


def test_template_mono_colonne_strict() -> None:
    """Vérifie l'absence absolue d'éléments multi-colonnes ou perturbateurs ATS (TASK-012-03)."""
    profil = _profil_exemple()
    tex = render_latex_resume(profil)

    # Interdictions ATS absolues
    assert r"\begin{multicols}" not in tex
    assert "twocolumn" not in tex
    assert r"\begin{tabular}" not in tex
    assert r"\begin{minipage}" not in tex
    # Doit être de classe article
    assert (
        r"\documentclass[10pt,a4paper]{article}" in tex
        or r"\documentclass[11pt,a4paper]{article}" in tex
    )


def test_sections_standards_presentes() -> None:
    """Vérifie la présence et l'ordonnancement des rubriques (TASK-012-02)."""
    profil = _profil_exemple()
    tex = render_latex_resume(profil)

    assert "Jean Dupont" in tex
    assert "jean.dupont@example.com" in tex
    assert r"\section*{Profil professionnel}" in tex
    assert r"\section*{Expériences professionnelles}" in tex
    assert r"\section*{Compétences techniques}" in tex
    assert r"\section*{Formation}" in tex
    assert r"\section*{Certifications}" in tex
    assert r"\section*{Langues}" in tex

    # Échappement des caractères spéciaux
    assert r"Tech Corp \& Co" in tex


def test_variations_de_longueur() -> None:
    """Vérifie l'adaptation des marges et polices pour 1 page vs 2 pages (TASK-012-05)."""
    profil = _profil_exemple()

    tex_one_page = render_latex_resume(profil, length_target=LengthTarget.ONE_PAGE)
    assert r"\documentclass[10pt,a4paper]{article}" in tex_one_page
    assert "margin=1.2cm" in tex_one_page

    tex_two_pages = render_latex_resume(profil, length_target=LengthTarget.TWO_PAGES)
    assert r"\documentclass[11pt,a4paper]{article}" in tex_two_pages
    assert "margin=1.8cm" in tex_two_pages


def test_caracteres_internationaux_et_accents() -> None:
    """Vérifie la configuration d'encodage T1, lmodern et UTF-8 (TASK-012-04)."""
    profil = _profil_exemple()
    tex = render_latex_resume(profil)

    assert r"\usepackage[utf8]{inputenc}" in tex
    assert r"\usepackage[T1]{fontenc}" in tex
    assert r"\usepackage{lmodern}" in tex
    assert "Ingénieur Backend" in tex
    assert "Université de Paris" in tex
