"""Certifications : une entrée par certification, pas une par ligne de sa description."""

from app.modules.candidate_profile.domain.extraction.extractor import extract_profile

_CCNA = """\
CERTIFICATIONS
Certification Cisco Certified Network Associate (CCNA) (en cours)
Depuis juil. 2024 Cisco Talence, France
En cours de préparation - Obtention prévue :2025
Formation sur les technologies Cisco et les protocoles de communication réseau
Configuration et dépannage de réseaux informatiques (Switching & Routing)
"""


def test_une_certification_decrite_sur_plusieurs_lignes_n_est_qu_une_entree() -> None:
    certifications = extract_profile(_CCNA).certifications

    assert [c.name for c in certifications] == [
        "Certification Cisco Certified Network Associate (CCNA) (en cours)"
    ]
    assert "Switching & Routing" in certifications[0].source_text


def test_une_certification_en_cours_n_a_pas_d_annee_d_obtention() -> None:
    # « Obtention prévue : 2025 » est un projet, pas une date d'obtention.
    assert extract_profile(_CCNA).certifications[0].year is None


def test_l_annee_d_obtention_est_la_fin_de_la_periode() -> None:
    texte = "CERTIFICATIONS\nGoogle Data Analytics\nMars 2022 - Juin 2022 Coursera\n"

    certification = extract_profile(texte).certifications[0]

    assert (certification.name, certification.year) == ("Google Data Analytics", 2022)


def test_plusieurs_certifications_datees() -> None:
    texte = (
        "CERTIFICATIONS\nGoogle Data Analytics\nMars 2022 - Juin 2022 Coursera\n"
        "AWS Cloud Practitioner\nJanvier 2023 - Février 2023 Amazon\n"
    )

    assert [(c.name, c.year) for c in extract_profile(texte).certifications] == [
        ("Google Data Analytics", 2022),
        ("AWS Cloud Practitioner", 2023),
    ]


def test_une_liste_simple_reste_une_certification_par_ligne() -> None:
    texte = "CERTIFICATIONS\n- AWS Solutions Architect – 2023\n- Scrum Master\n"

    assert [(c.name, c.year) for c in extract_profile(texte).certifications] == [
        ("AWS Solutions Architect", 2023),
        ("Scrum Master", None),
    ]


def test_les_lignes_avant_la_premiere_certification_datee_ne_sont_pas_perdues() -> None:
    texte = "CERTIFICATIONS\nScrum Master\nGoogle Data Analytics\nMars 2022 - Juin 2022 Coursera\n"

    noms = [c.name for c in extract_profile(texte).certifications]

    assert noms == ["Scrum Master", "Google Data Analytics"]
