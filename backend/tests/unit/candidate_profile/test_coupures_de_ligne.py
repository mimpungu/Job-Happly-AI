"""Lignes coupées par la mise en page : repérées à l'interligne, utilisées pour les compétences.

Cas réel : « VS Code, MySQL, Wmware / Fusion, Oracle SQL / Developper, Figma ». Dans la colonne
latérale d'un modèle graphique, l'interligne est serré à l'intérieur d'un paragraphe et large entre
deux éléments. Dans la colonne principale, les puces sont espacées comme les lignes d'une même
puce : l'interligne n'y prouve rien, le marqueur n'est donc exploité que pour les compétences.
"""

from app.modules.candidate_profile.domain.extraction.extractor import extract_profile
from app.modules.candidate_profile.domain.extraction.skills import extract_skills
from app.modules.candidate_profile.domain.text_columns import (
    SOFT_WRAP,
    TextFragment,
    read_in_columns,
)
from app.modules.candidate_profile.domain.text_normalization import normalize_document_text
from app.modules.candidate_profile.infrastructure.extraction import extract_document_text

from .builders import make_pdf_positioned

TAILLE = 10.0
SERRE = 12.0  # 1,2 × le corps : lignes d'un même paragraphe
LARGE = 20.0  # 2 × le corps : éléments distincts


def _colonne(x: float, lignes: list[tuple[str, float]], y0: float = 800.0) -> list[TextFragment]:
    """`lignes` : (texte, écart au-dessus de la ligne précédente) ; le premier écart est ignoré."""
    fragments, y = [], y0
    for i, (texte, ecart) in enumerate(lignes):
        y -= 0 if i == 0 else ecart
        fragments.append(TextFragment(x, y, TAILLE, texte))
    return fragments


_GAUCHE = [
    ("COMPÉTENCES", 0),
    ("Logiciels", LARGE),
    ("VS Code, MySQL, Wmware", LARGE),
    ("Fusion, Oracle SQL", SERRE),
    ("Developper, Figma", SERRE),
    ("Systèmes", LARGE),
    ("Windows, Linux", LARGE),
    ("Cisco, GNS3,", LARGE),
    ("Nmap", SERRE),
    ("ATOUTS", LARGE),
]
_DROITE = [(f"Ligne {i}", SERRE if i % 3 else LARGE) for i in range(10)]


def _lire(gauche: list[tuple[str, float]] = _GAUCHE) -> list[str]:
    fragments = [*_colonne(20, gauche), *_colonne(400, _DROITE)]
    texte = read_in_columns(fragments)
    assert texte is not None
    return texte.split("\n")


class TestMarqueur:
    def test_une_ligne_a_virgules_collee_a_la_suivante_est_marquee(self) -> None:
        lignes = _lire()

        assert lignes[2] == "VS Code, MySQL, Wmware" + SOFT_WRAP
        assert lignes[3] == "Fusion, Oracle SQL" + SOFT_WRAP
        assert lignes[4] == "Developper, Figma"  # dernière ligne du paragraphe

    def test_un_interligne_large_n_est_jamais_une_coupure(self) -> None:
        lignes = _lire()

        assert SOFT_WRAP not in lignes[1]  # « Logiciels » puis écart large
        assert SOFT_WRAP not in lignes[6]  # « Windows, Linux » puis écart large

    def test_une_ligne_sans_virgule_n_est_pas_marquee(self) -> None:
        lignes = _lire()

        assert lignes[8] == "Nmap"
        assert all(SOFT_WRAP not in ligne for ligne in lignes if "," not in ligne)

    def test_une_phrase_terminee_n_est_pas_une_coupure(self) -> None:
        gauche = [*_GAUCHE[:3], ("Fin de phrase, ici.", SERRE), *_GAUCHE[3:]]

        assert SOFT_WRAP not in _lire(gauche)[3]

    def test_sans_alternance_d_interlignes_rien_n_est_marque(self) -> None:
        # Interligne uniforme : le serré ne distingue plus rien, aucun marqueur.
        uniforme = [(texte, SERRE) for texte, _ in _GAUCHE]

        assert all(SOFT_WRAP not in ligne for ligne in _lire(uniforme))


class TestCompetences:
    def test_les_lignes_marquees_sont_recollees(self) -> None:
        lignes = (
            "VS Code, MySQL, Wmware" + SOFT_WRAP,
            "Fusion, Oracle SQL" + SOFT_WRAP,
            "Developper, Figma",
        )

        noms = [s.name for s in extract_skills(lignes)]

        assert noms == ["VS Code", "MySQL", "Wmware Fusion", "Oracle SQL Developper", "Figma"]

    def test_sans_marqueur_deux_listes_restent_deux_listes(self) -> None:
        noms = [s.name for s in extract_skills(("Python, SQL", "Jira, Docker"))]

        assert noms == ["Python", "SQL", "Jira", "Docker"]

    def test_le_marqueur_ne_reste_dans_aucun_nom(self) -> None:
        competences = extract_skills(("A, B" + SOFT_WRAP, "C"))

        assert all(SOFT_WRAP not in s.name and SOFT_WRAP not in s.source_text for s in competences)


class TestAilleursQueLesCompetences:
    _TEXTE = (
        "Jeanne Martin\n\nEXPÉRIENCES\nAnalyste\nDe 2020 à 2022 Acme Paris, France"
        + SOFT_WRAP
        + "\n"
        "Rapports, tableaux de bord" + SOFT_WRAP + "\nAnalyse mensuelle.\n\n"
        "COMPÉTENCES\nPython, SQL" + SOFT_WRAP + "\nDocker\n"
    )

    def test_le_marqueur_est_retire_des_autres_sections(self) -> None:
        profil = extract_profile(self._TEXTE)

        assert SOFT_WRAP not in repr(profil.experiences)
        assert SOFT_WRAP not in repr(profil.contact)

    def test_les_competences_utilisent_le_marqueur(self) -> None:
        noms = [s.name for s in extract_profile(self._TEXTE).skills]

        assert noms == ["Python", "SQL Docker"]


def test_de_bout_en_bout_sur_un_pdf_en_colonnes() -> None:
    fragments = [
        *((int(f.x), int(f.y), f.text) for f in _colonne(40, _GAUCHE)),
        *((int(f.x), int(f.y), f.text) for f in _colonne(272, _DROITE)),
    ]
    contenu = make_pdf_positioned(fragments)
    texte = normalize_document_text(extract_document_text("cv.pdf", contenu).text)

    noms = [s.name for s in extract_profile(texte).skills]

    assert "Wmware Fusion" in noms
    assert "Oracle SQL Developper" in noms
