"""Tests unitaires du template LaTeX mono-colonne et des sections standards (FEATURE 012.1)."""

import io

import pytest
from pypdf import PdfReader

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
from app.modules.document_generation.domain.ats_analyzer import analyze_pdf_ats
from app.modules.document_generation.domain.enums import LengthTarget, ResumeTemplateStyle
from app.modules.document_generation.domain.latex_escape import UnsupportedCharactersError
from app.modules.document_generation.domain.templates import headings_for, render_latex_resume
from app.modules.document_generation.infrastructure.latex_compiler import IsolatedLaTeXCompiler


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


def test_cmap_est_charge_avant_fontenc() -> None:
    """Sans cela, « œ » ressort en « ÷ » à l'extraction : illisible pour un ATS."""
    tex = render_latex_resume(_profil_exemple())
    assert tex.index(r"\usepackage{cmap}") < tex.index(r"\usepackage[T1]{fontenc}")


def test_les_trois_styles_produisent_des_documents_distincts() -> None:
    profil = _profil_exemple()
    sources = {s: render_latex_resume(profil, style=s) for s in ResumeTemplateStyle}

    assert len(set(sources.values())) == 3
    assert r"\renewcommand{\familydefault}{\sfdefault}" in sources[ResumeTemplateStyle.MODERN]
    assert r"\renewcommand{\familydefault}" not in sources[ResumeTemplateStyle.CLASSIC]
    assert r"\titlerule" not in sources[ResumeTemplateStyle.MODERN]
    assert "margin=1.1cm" in render_latex_resume(
        profil, style=ResumeTemplateStyle.COMPACT, length_target=LengthTarget.ONE_PAGE
    )
    for source in sources.values():  # tous restent mono-colonne
        assert "multicols" not in source
        assert "minipage" not in source
        assert "tabular" not in source


def test_intitules_en_anglais() -> None:
    tex = render_latex_resume(_profil_exemple(), language="en")

    assert r"\section*{Professional experience}" in tex
    assert r"\section*{Technical skills}" in tex
    assert r"\section*{Education}" in tex
    assert r"\section*{Languages}" in tex
    assert "Présent" not in tex
    assert "Present" in tex
    assert headings_for("pt-BR").experience == "Expériences professionnelles"  # repli : français


def test_aucune_valeur_de_substitution_inventee() -> None:
    """Un profil sans nom ni titre ne produit ni « Candidat » ni « Poste »."""
    from app.modules.candidate_profile.domain.profile import ExperienceDoc, ProfileDocument

    profil = ProfileDocument(experiences=(ExperienceDoc(company="Acme"),))
    tex = render_latex_resume(profil)

    for invente in ("Candidat", "Professionnel", "Poste", "Diplôme", "Général"):
        assert invente not in tex
    assert "Acme" in tex


def test_caractere_non_supporte_est_refuse_explicitement() -> None:
    from app.modules.candidate_profile.domain.profile import Identity, ProfileDocument

    profil = ProfileDocument(identity=Identity(first_name="Иван", last_name="Петров"))
    with pytest.raises(UnsupportedCharactersError):
        render_latex_resume(profil)


def test_texte_utilisateur_ne_peut_pas_injecter_de_commande() -> None:
    from app.modules.candidate_profile.domain.profile import ExperienceDoc, ProfileDocument

    profil = ProfileDocument(
        experiences=(ExperienceDoc(title="\\input{/etc/passwd}", company="A}\\write18{x"),)
    )
    tex = render_latex_resume(profil)

    assert "\\input{/etc" not in tex
    assert "\\write18{" not in tex


@pytest.mark.parametrize("style", list(ResumeTemplateStyle))
@pytest.mark.parametrize("cible", [LengthTarget.ONE_PAGE, LengthTarget.TWO_PAGES])
async def test_compilation_reelle_et_extraction_pour_chaque_style(
    compiler: IsolatedLaTeXCompiler, style: ResumeTemplateStyle, cible: LengthTarget
) -> None:
    """PDF réellement compilé, texte sélectionnable, accents et ligatures intacts (EPIC 012)."""
    profil = _profil_exemple().model_copy(
        update={"summary": "Spécialiste du cœur de métier, d'après l'œuvre -- 100% fiable."}
    )
    pdf = await compiler.compile(render_latex_resume(profil, style=style, length_target=cible))

    texte = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages)
    assert "cœur" in texte
    assert "l'œuvre" in texte.replace("\u2019", "'")
    assert "Tech Corp & Co" in texte
    assert "Réduction de la latence de 40%" in texte

    rapport = analyze_pdf_ats(
        pdf,
        expected_phrases=("Jean Dupont", "Université de Paris", "Tech Corp & Co"),
        expected_sections=(
            "summary",
            "experience",
            "skills",
            "education",
            "certifications",
            "languages",
        ),
        length_target=cible,
    )
    assert rapport.passed is True, [c for c in rapport.checks if c.status.value != "pass"]
    assert rapport.single_column is True
    assert rapport.reading_order_valid is True
    if cible is LengthTarget.ONE_PAGE:
        assert rapport.page_count == 1
