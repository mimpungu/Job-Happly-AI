"""Lecture d'une page à deux colonnes : la colonne de gauche en entier, puis celle de droite.

Pourquoi : dans un CV issu d'un modèle graphique, l'ordre de dessin du PDF n'est pas l'ordre de
lecture (les titres de section peuvent être dessinés avant leur contenu). On reconstruit donc
les lignes à partir de la **position** de chaque fragment de texte. Les fragments eux-mêmes
restent intacts : contrairement à une relecture « mise en page » du PDF, aucun mot n'est coupé
(« Jira », « CCNA », « livrables » ont été cassés par cette autre méthode).

Limite assumée : seules deux colonnes sont reconnues. En l'absence de gouttière nette, on
retourne `None` et l'appelant garde le texte brut : un CV à une colonne n'est jamais modifié.
"""

from __future__ import annotations

from dataclasses import dataclass

# Ligne seule posée entre deux colonnes : les sections s'arrêtent là et le texte sans titre qui suit
# (nom, résumé) n'est pas pris pour la suite de la dernière section de la colonne précédente.
# « Caractère de remplacement d'objet » (U+FFFC) : ni une espace (`strip()` ne l'efface pas,
# contrairement aux séparateurs de contrôle), ni retiré par la normalisation, absent des vrais CV.
COLUMN_BREAK = "\ufffc"

# Marqueur de fin de ligne : « cette ligne se poursuit sur la suivante » d'après l'interligne.
# Même choix que ci-dessus : ni espace, ni retiré par la normalisation, absent des vrais CV.
SOFT_WRAP = "\ufffb"

# Interligne rapporté au corps : serré à l'intérieur d'un paragraphe, large entre deux éléments.
_ECART_SERRE = 1.35
_ECART_LARGE = 1.5
# Le signal n'a de sens que si la colonne alterne les deux : un interligne uniforme ne prouve rien.
_PART_MIN_ECARTS_LARGES = 0.25
_FIN_DE_PHRASE = (".", "!", "?", ":", ";")

# Largeur moyenne d'un caractère, en fraction du corps. Volontairement large : sous-estimer une
# largeur créerait de faux vides au milieu d'une ligne, donc de fausses colonnes.
_LARGEUR_CARACTERE = 0.6
# Vide minimal (en points) entre deux colonnes : un simple espace entre deux mots n'en est pas un.
MIN_GUTTER_POINTS = 12.0
# Chaque colonne doit porter un vrai contenu, sinon c'est un tableau ou une mise en forme isolée.
MIN_LINES_PER_COLUMN = 8
# Deux fragments sont sur la même ligne si leur écart vertical reste sous cette part du corps.
_TOLERANCE_LIGNE = 0.4


@dataclass(frozen=True, slots=True)
class TextFragment:
    """Un texte posé sur la page : coin gauche (x), ligne de base (y, vers le haut), corps."""

    x: float
    y: float
    size: float
    text: str

    @property
    def end_x(self) -> float:
        return self.x + len(self.text) * self.size * _LARGEUR_CARACTERE


def read_in_columns(fragments: list[TextFragment]) -> str | None:
    """Texte lu colonne par colonne, ou `None` si la page n'a pas deux colonnes nettes."""
    utiles = [f for f in fragments if f.text.strip() and f.size > 0]
    gouttiere = _gouttiere(utiles)
    if gouttiere is None:
        return None
    gauche = _lignes([f for f in utiles if f.x < gouttiere])
    droite = _lignes([f for f in utiles if f.x >= gouttiere])
    if len(gauche) < MIN_LINES_PER_COLUMN or len(droite) < MIN_LINES_PER_COLUMN:
        return None
    return "\n".join((*gauche, COLUMN_BREAK, *droite))


def _gouttiere(fragments: list[TextFragment]) -> float | None:
    """Abscisse au milieu du plus large vide vertical que traverse aucun fragment."""
    if not fragments:
        return None
    plages = sorted((f.x, f.end_x) for f in fragments)
    meilleur: tuple[float, float] | None = None
    fin = plages[0][1]
    for debut, fin_suivante in plages[1:]:
        if debut - fin >= MIN_GUTTER_POINTS and (
            meilleur is None or debut - fin > meilleur[1] - meilleur[0]
        ):
            meilleur = (fin, debut)
        fin = max(fin, fin_suivante)
    return None if meilleur is None else (meilleur[0] + meilleur[1]) / 2


def _lignes(fragments: list[TextFragment]) -> list[str]:
    """Lignes de haut en bas ; les fragments d'une même ligne sont lus de gauche à droite."""
    groupes: list[list[TextFragment]] = []
    reference = 0.0
    for fragment in sorted(fragments, key=lambda f: -f.y):
        if groupes and abs(fragment.y - reference) <= _TOLERANCE_LIGNE * fragment.size:
            groupes[-1].append(fragment)
        else:
            groupes.append([fragment])
            reference = fragment.y
    textes = [
        " ".join(f.text.strip() for f in sorted(groupe, key=lambda f: f.x)) for groupe in groupes
    ]
    hauteurs = [groupe[0].y for groupe in groupes]
    corps = [max(f.size for f in groupe) for groupe in groupes]
    return _marquer_les_coupures(textes, hauteurs, corps)


def _marquer_les_coupures(
    textes: list[str], hauteurs: list[float], corps: list[float]
) -> list[str]:
    """Ajoute `SOFT_WRAP` aux lignes d'une liste à virgules qui se poursuivent sur la suivante.

    Critère : interligne serré (même paragraphe) dans une colonne qui alterne serré et large. Une
    ligne sans virgule ou qui finit une phrase n'est jamais marquée. Le marqueur n'est exploité
    que pour les compétences : dans la colonne principale, les puces sont espacées comme les
    lignes d'une même puce, l'interligne n'y prouve rien.
    """
    rapports = [
        (hauteurs[i] - hauteurs[i + 1]) / max(corps[i], corps[i + 1])
        for i in range(len(textes) - 1)
    ]
    if not rapports:
        return textes
    larges = sum(1 for r in rapports if r > _ECART_LARGE)
    if larges / len(rapports) < _PART_MIN_ECARTS_LARGES:
        return textes
    return [
        texte + SOFT_WRAP
        if i < len(rapports)
        and rapports[i] <= _ECART_SERRE
        and "," in texte
        and not texte.rstrip().endswith(_FIN_DE_PHRASE)
        else texte
        for i, texte in enumerate(textes)
    ]


def readable_text(texte: str) -> str:
    """Texte sans marqueurs internes, pour l'affichage : une frontière de colonne devient une
    ligne vide, une coupure de ligne disparaît."""
    return texte.replace(COLUMN_BREAK, "").replace(SOFT_WRAP, "")
