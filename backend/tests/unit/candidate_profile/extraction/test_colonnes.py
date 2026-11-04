"""CV à colonne latérale : le texte sans titre en tête de la colonne principale (nom, résumé)."""

from app.modules.candidate_profile.domain.extraction.extractor import extract_profile
from app.modules.candidate_profile.domain.extraction.sections import SectionKind, split_sections
from app.modules.candidate_profile.domain.text_columns import COLUMN_BREAK

_CV = f"""\
marie@exemple.test
Talence, France

COMPÉTENCES
Python, SQL
Jira, Docker
{COLUMN_BREAK}
Marie Dupont
Recherche d'une alternance en SI
Étudiante en Master MIAGE, motivée par les projets à impact.

EXPÉRIENCES PROFESSIONNELLES
Développeuse
De mai 2025 à août 2025 Acme Pessac
Participation au développement.
"""


def test_le_texte_de_la_colonne_principale_n_est_pas_pris_pour_des_competences() -> None:
    profil = extract_profile(_CV)

    assert [s.name for s in profil.skills] == ["Python", "SQL", "Jira", "Docker"]


def test_le_nom_est_lu_en_tete_de_la_colonne_principale() -> None:
    assert extract_profile(_CV).contact.full_name == "Marie Dupont"


def test_le_texte_d_introduction_devient_titre_et_resume() -> None:
    profil = extract_profile(_CV)

    assert profil.contact.headline == "Recherche d'une alternance en SI"
    assert profil.summary is not None
    assert profil.summary.startswith("Étudiante en Master MIAGE")
    assert "Marie Dupont" not in profil.summary


def test_la_frontiere_de_colonne_n_apparait_jamais_dans_le_profil() -> None:
    profil = extract_profile(_CV)

    assert COLUMN_BREAK not in repr(profil)


def test_une_suite_de_section_sans_nom_reste_dans_sa_section() -> None:
    # La deuxième colonne prolonge « Compétences » : rien n'indique une introduction.
    texte = f"COMPÉTENCES\nPython\nSQL\n{COLUMN_BREAK}\nDocker\nGit\n"

    document = split_sections(texte)

    lignes = [ligne for ligne in document.lines_of(SectionKind.SKILLS) if ligne]
    assert lignes == ["Python", "SQL", "Docker", "Git"]
    assert extract_profile(texte).summary is None


def test_sans_frontiere_le_comportement_est_inchange() -> None:
    texte = "Marie Dupont\nmarie@exemple.test\n\nCOMPÉTENCES\nPython\n"

    profil = extract_profile(texte)

    assert profil.contact.full_name == "Marie Dupont"
    assert [s.name for s in profil.skills] == ["Python"]
