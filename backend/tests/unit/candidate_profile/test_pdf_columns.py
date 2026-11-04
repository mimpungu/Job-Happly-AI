"""CV en colonnes dont les titres sont dessinés avant leur contenu (modèles graphiques)."""

from app.modules.candidate_profile.domain.extraction.extractor import extract_profile
from app.modules.candidate_profile.domain.extraction.models import ExtractedProfile
from app.modules.candidate_profile.domain.text_normalization import normalize_document_text
from app.modules.candidate_profile.infrastructure.extraction import extract_document_text

from .builders import make_pdf_positioned

_GAUCHE, _DROITE = 40, 272

# Ordre du flux = ordre de dessin : les trois titres de la colonne de droite arrivent d'abord,
# comme dans le PDF réel qui a motivé ce test (0 expérience lue, tout classé en « formation »).
_CV_DEUX_COLONNES = [
    (_GAUCHE, 780, "ATOUTS"),
    (_GAUCHE, 766, "Rigoureux"),
    (_GAUCHE, 752, "Travail en équipe"),
    (_GAUCHE, 738, "Autonomie, curieux"),
    (_GAUCHE, 700, "COMPÉTENCES"),
    (_GAUCHE, 686, "Python, SQL, Docker"),
    (_GAUCHE, 672, "Git, Linux"),
    (_GAUCHE, 640, "LANGUES"),
    (_GAUCHE, 626, "Français"),
    (_DROITE, 750, "EXPÉRIENCES PROFESSIONNELLES"),
    (_DROITE, 400, "CERTIFICATIONS"),
    (_DROITE, 300, "FORMATIONS"),
    (_DROITE, 725, "Développeur Python"),
    (_DROITE, 711, "Depuis juil. 2024 Acme Bordeaux"),
    (_DROITE, 697, "Implication dans la stratégie produit."),
    (_DROITE, 660, "Stagiaire Ingénieur Logiciel"),
    (_DROITE, 646, "De mai 2025 à août 2025 Inetum Pessac"),
    (_DROITE, 632, "Participation au développement d'applications."),
    (_DROITE, 375, "Certification Cisco CCNA (en cours)"),
    (_DROITE, 361, "Depuis juil. 2024 Cisco Talence"),
    (_DROITE, 275, "Master, Méthodes Informatiques Appliquées"),
    (_DROITE, 261, "De 2024 à 2026 Université de Bordeaux Talence"),
]


def _profil() -> tuple[str, ExtractedProfile]:
    contenu = make_pdf_positioned(_CV_DEUX_COLONNES)
    texte = normalize_document_text(extract_document_text("cv.pdf", contenu).text)
    return texte, extract_profile(texte)


def test_chaque_contenu_est_rattache_a_son_titre() -> None:
    _, profil = _profil()

    assert [e.title for e in profil.experiences] == [
        "Développeur Python",
        "Stagiaire Ingénieur Logiciel",
    ]
    assert [e.degree for e in profil.educations] == ["Master, Méthodes Informatiques Appliquées"]
    assert profil.warnings == ()


def test_les_colonnes_ne_sont_pas_melangees() -> None:
    texte, _ = _profil()

    # Colonne de gauche lue en entier avant celle de droite : aucune ligne de l'une n'est
    # intercalée dans l'autre.
    assert texte.index("Français") < texte.index("EXPÉRIENCES PROFESSIONNELLES")
    assert texte.index("Python, SQL, Docker") < texte.index("EXPÉRIENCES PROFESSIONNELLES")


def test_la_colonne_principale_sans_titre_donne_le_nom_et_ne_pollue_pas_les_competences() -> None:
    fragments = [
        *_CV_DEUX_COLONNES,
        (_DROITE, 800, "Marie Dupont"),
        (_DROITE, 786, "Recherche d'une alternance en SI"),
    ]
    contenu = make_pdf_positioned(fragments)
    texte = normalize_document_text(extract_document_text("cv.pdf", contenu).text)

    profil = extract_profile(texte)

    assert profil.contact.full_name == "Marie Dupont"
    assert "Marie Dupont" not in [s.name for s in profil.skills]
    assert profil.summary == "Recherche d'une alternance en SI"
