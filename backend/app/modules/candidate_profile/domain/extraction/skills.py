"""Compétences : listes à virgules, puces, ou « Catégorie : a, b, c », y compris coupées par la mise
en page d'un CV à colonne latérale (libellés sur deux lignes, éléments coupés en fin de ligne)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.modules.candidate_profile.domain.extraction.models import ExtractedSkill
from app.modules.candidate_profile.domain.text_columns import SOFT_WRAP

_SEPARATEURS = re.compile(r"\s*[,;|•·/]\s*|\s{3,}")
_CATEGORIE = re.compile(r"^(?P<cat>[^:,;]{2,40}):\s*(?P<reste>.*)$")
_PARENTHESE_AVEC_LISTE = re.compile(r"^(?P<tete>[^()]+?)\s*\((?P<corps>[^()]*,[^()]*)\)$")
MAX_MOTS = 5
MAX_LONGUEUR = 60
MAX_MOTS_TITRE = 4

# Mots qui ne terminent jamais un libellé : une ligne qui s'y arrête se poursuit sur la suivante.
_CONNECTIFS = frozenset({"de", "du", "des", "d'", "et", "and", "of", "for", "la", "le", "les", "&"})
# Titres d'un seul mot sans ambiguïté : sans eux, « Logiciels » serait pris pour une compétence.
_TITRES_GENERIQUES = frozenset(
    {"logiciels", "outils", "langages", "frameworks", "technologies", "software", "tools"}
)


@dataclass(slots=True)
class _Bloc:
    categorie: str | None
    lignes: list[str]
    etiquette_seule: bool = False
    """Libellé seul sur sa ligne : il vaut pour toutes les lignes jusqu'au libellé suivant. Un
    libellé suivi de sa liste (« Outils : a, b ») ne vaut que pour cette liste."""


def extract_skills(lignes: tuple[str, ...]) -> tuple[ExtractedSkill, ...]:
    vues: set[str] = set()
    competences: list[ExtractedSkill] = []
    for bloc in _blocs([_sans_puce(ligne) for ligne in lignes if ligne.strip()]):
        source = "\n".join(_nette(ligne) for ligne in bloc.lignes)
        for morceau in _morceaux(bloc.lignes):
            for nom in _elements(_nette(morceau)):
                # Une phrase n'est pas une compétence : on la laisse à l'utilisateur plutôt que de
                # la découper en mots-clés approximatifs.
                if not nom or len(nom) > MAX_LONGUEUR or len(nom.split()) > MAX_MOTS:
                    continue
                cle = nom.casefold()
                if cle in vues:
                    continue
                vues.add(cle)
                competences.append(ExtractedSkill(nom, bloc.categorie, source))
    return tuple(competences)


def _sans_puce(ligne: str) -> str:
    texte = ligne.strip()
    return texte[2:].strip() if texte.startswith("- ") else texte


def _nette(ligne: str) -> str:
    """Ligne sans le marqueur de coupure posé par la lecture des colonnes d'un PDF."""
    return ligne.replace(SOFT_WRAP, "").rstrip()


def _mots(ligne: str) -> list[str]:
    return _nette(ligne).casefold().split()


def _finit_par_connectif(ligne: str) -> bool:
    mots = _mots(ligne)
    return bool(mots) and (mots[-1] in _CONNECTIFS or mots[-1].endswith("'"))


def _liste_ouverte(lignes: list[str]) -> bool:
    """La dernière ligne finit par une virgule : la suivante prolonge la liste, pas un titre."""
    return bool(lignes) and _nette(lignes[-1]).endswith((",", ";"))


def _est_titre_sans_deux_points(ligne: str, suivante: str, courant: list[str]) -> bool:
    """Titre sans « : » : très court, sans virgule, juste avant une liste, la liste précédente
    étant close. Prudent par construction : perdre une vraie compétence serait invisible, garder
    un libellé ne coûte qu'une suppression."""
    mots = _mots(ligne)
    if "," in ligne or not mots or len(mots) > MAX_MOTS_TITRE or _liste_ouverte(courant):
        return False
    if len(mots) == 1:
        return mots[0] in _TITRES_GENERIQUES
    return any(m in _CONNECTIFS for m in mots[1:-1]) and "," in suivante


def _titre_en_deux_lignes_avant_une_liste(lignes: list[str], i: int) -> bool:
    """« Langages de » / « Programmation » / « C, C++ » : un titre coupé puis sa liste, même si la
    liste précédente finissait par une virgule."""
    if i + 2 >= len(lignes):
        return False
    suite, liste = lignes[i + 1], lignes[i + 2]
    return "," not in suite and len(suite.split()) <= MAX_MOTS - 2 and "," in liste


def _blocs(lignes: list[str]) -> list[_Bloc]:
    blocs: list[_Bloc] = []
    courant = _Bloc(None, [])
    attente: list[str] = []  # début d'un titre coupé en fin de ligne (« Outils de Gestion de »)

    def clore() -> None:
        nonlocal courant
        if courant.lignes:
            blocs.append(courant)

    def ouvrir(categorie: str, lignes: list[str]) -> None:
        nonlocal courant
        clore()
        courant = _Bloc(categorie, lignes, etiquette_seule=not lignes)

    for i, ligne in enumerate(lignes):
        suivante = lignes[i + 1] if i + 1 < len(lignes) else ""
        categorie = _CATEGORIE.match(ligne)
        if categorie and "http" not in ligne.lower():
            titre = " ".join([*attente, categorie.group("cat").strip()])
            attente = []
            reste = categorie.group("reste").strip()
            ouvrir(titre, [reste] if reste else [])
            continue
        if attente:
            if "," not in ligne and len(ligne.split()) <= MAX_MOTS - 2:
                titre = " ".join([*attente, ligne.strip(" :")])
                attente = []
                ouvrir(titre, [])
                continue
            courant.lignes.extend(attente)  # ce n'était pas un titre coupé
            attente = []
        if (
            _finit_par_connectif(ligne)
            and "," not in ligne
            and len(ligne.split()) <= MAX_MOTS_TITRE
            and (
                not _liste_ouverte(courant.lignes)
                or _titre_en_deux_lignes_avant_une_liste(lignes, i)
            )
        ):
            attente = [ligne]
            continue
        if _est_titre_sans_deux_points(ligne, suivante, courant.lignes):
            ouvrir(ligne.strip(" :"), [])
            continue
        if (
            courant.categorie is not None
            and not courant.etiquette_seule
            and courant.lignes
            and not _liste_ouverte(courant.lignes)
        ):
            clore()
            courant = _Bloc(None, [])
        courant.lignes.append(ligne)
    courant.lignes.extend(attente)
    clore()
    return blocs


def _prolonge_la_precedente(precedente: str, ligne: str) -> bool:
    """La ligne continue la précédente seulement sur un signal explicite : coupure de ligne
    mesurée dans le PDF, virgule ou connectif final, ou début de ligne qui ne peut pas ouvrir un
    élément (parenthèse, minuscule). Deux listes à virgules consécutives (« Python, SQL » puis
    « Jira, Docker ») restent deux listes."""
    return (
        precedente.rstrip().endswith(SOFT_WRAP)  # interligne serré : même paragraphe
        or _nette(precedente).endswith((",", ";"))
        or _finit_par_connectif(precedente)
        or ligne[:1] == "("
        or ligne[:1].islower()
    )


def _morceaux(lignes: list[str]) -> list[str]:
    """Textes à découper : lignes recollées sur signal explicite, sinon une ligne par morceau."""
    groupes: list[str] = []
    for ligne in lignes:
        if groupes and _prolonge_la_precedente(groupes[-1], ligne):
            groupes[-1] = f"{_nette(groupes[-1])} {ligne}"
        else:
            groupes.append(ligne)
    return groupes


def _decouper_hors_parentheses(texte: str) -> list[str]:
    profondeur = 0
    courant: list[str] = []
    morceaux: list[str] = []
    for c in texte:
        profondeur += (c == "(") - (c == ")")
        if profondeur <= 0 and _SEPARATEURS.fullmatch(c):
            morceaux.append("".join(courant))
            courant = []
        else:
            courant.append(c)
    morceaux.append("".join(courant))
    return morceaux


def _elements(texte: str) -> list[str]:
    """« Linux (Ubuntu, Debian) » -> Linux, Ubuntu, Debian ; « Excel (avancé) » reste entier."""
    elements: list[str] = []
    for morceau in _decouper_hors_parentheses(texte):
        nom = morceau.strip(" .:-–—")
        m = _PARENTHESE_AVEC_LISTE.match(nom)
        if m:
            elements.append(m.group("tete").strip())
            elements.extend(e.strip(" .:-–—") for e in m.group("corps").split(","))
        else:
            elements.append(nom)
    return elements
