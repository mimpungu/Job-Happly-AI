"""Assainissement et échappement LaTeX : aucune entrée utilisateur ne doit atteindre TeX brute.

Deux étapes distinctes :
1. `sanitize_text` rend le texte compatible avec pdfLaTeX (T1) : symboles courants remplacés,
   caractères invisibles ou emojis retirés, lettres latines rares réduites à leur base. Les
   écritures non latines (cyrillique, grec, CJK…) ne sont PAS supprimées en silence : une
   exception explicite évite de produire un CV amputé du nom du candidat.
2. `latex_escape` protège les caractères réservés de TeX et neutralise les ligatures
   typographiques (`--`, `` ` ``, `<<`…) qui altéreraient le texte extrait par les ATS.
"""

from __future__ import annotations

import re
import unicodedata

# Une seule passe : les accolades introduites ne sont pas ré-échappées.
_LATEX_ESCAPES: dict[str, str] = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
    "`": r"\textasciigrave{}",
}
_LATEX_REGEX = re.compile(r"([\\&%$#_{}~^`])")

# Séquences que TeX transformerait en ligatures : on intercale un groupe vide.
_LIGATURES = re.compile(r"--+|''|<<|>>")

# Symboles absents de T1/lmodern, remplacés par leur équivalent ASCII lisible par un ATS.
_SYMBOLES: dict[str, str] = {
    "≥": ">=",
    "≤": "<=",
    "≠": "!=",
    "≈": "~",
    "→": "->",
    "←": "<-",
    "⇒": "=>",
    "↔": "<->",
    "\u2212": "-",  # signe moins mathématique
    "\u2217": "*",
    "\u2032": "'",
    "\u2033": '"',
    "\u00a0": " ",  # espace insécable
    "\u202f": " ",  # espace fine insécable
    "\u2009": " ",
    "\u2002": " ",
    "\u2003": " ",
    "\u00ad": "",  # trait d'union conditionnel
}
# Espaces de largeur nulle, marques directionnelles, BOM et sélecteurs de variation.
_INVISIBLES = re.compile("[\u200b-\u200f\u2060\ufeff\ufe00-\ufe0f]")

# Au-delà de Latin-1 + Latin étendu A, T1 ne couvre plus (vietnamien, roumain virgule…).
_LATIN_MAX = 0x17F


class UnsupportedCharactersError(ValueError):
    """Le texte contient des écritures que pdfLaTeX ne sait pas composer."""

    def __init__(self, characters: str) -> None:
        self.characters = characters
        super().__init__(
            f"Caractères non pris en charge par pdfLaTeX : {characters!r}. "
            "Les écritures non latines (cyrillique, grec, CJK, arabe…) ne sont pas "
            "encore supportées ; saisissez une translittération latine."
        )


def sanitize_text(text: str | None) -> str:
    """Rend un texte composable par pdfLaTeX sans en altérer silencieusement le sens."""
    if not text:
        return ""

    texte = unicodedata.normalize("NFC", text)
    for source, cible in _SYMBOLES.items():
        texte = texte.replace(source, cible)
    texte = _INVISIBLES.sub("", texte)

    sortie: list[str] = []
    refuses: list[str] = []
    for caractere in texte:
        converti = _convertir(caractere)
        if converti is None:
            refuses.append(caractere)
        else:
            sortie.append(converti)
    if refuses:
        raise UnsupportedCharactersError("".join(dict.fromkeys(refuses)))
    return "".join(sortie)


def _convertir(caractere: str) -> str | None:
    """Retourne le caractère à garder, "" pour le retirer, None s'il est non supportable."""
    code = ord(caractere)
    if code < 0x80:
        return caractere if caractere in "\n\t" or 0x20 <= code < 0x7F else ""
    categorie = unicodedata.category(caractere)
    if categorie in {"Cc", "Cf", "Cs", "Co", "Cn", "So", "Sk"}:
        return ""  # contrôles, emojis, pictogrammes : sans valeur pour un CV ATS
    if categorie.startswith("L"):
        if not unicodedata.name(caractere, "").startswith("LATIN"):
            return None
        if code <= _LATIN_MAX:
            return caractere
        base = unicodedata.normalize("NFKD", caractere)
        base = "".join(c for c in base if not unicodedata.combining(c))
        return base if base.isascii() and base else None
    if categorie == "Mn":
        return ""  # accent combinant isolé : le texte est déjà normalisé en NFC
    return caractere  # ponctuation et symboles (guillemets, tirets, €, ©…) gérés par inputenc


def latex_escape(text: str | None) -> str:
    """Assainit puis échappe un texte pour insertion dans un document LaTeX.

    Les caractères accentués latins sont intégralement préservés.
    Exemple : 'R&D / C# / 100% / $50k' -> 'R\\&D / C\\# / 100\\% / \\$50k'
    """
    propre = sanitize_text(text)
    if not propre:
        return ""

    echappe = _LATEX_REGEX.sub(lambda m: _LATEX_ESCAPES[m.group(1)], propre)
    echappe = _LIGATURES.sub(lambda m: "{}".join(m.group(0)), echappe)
    return re.sub(r"\s+", " ", echappe).strip()


def latex_escape_url(url: str | None) -> str:
    """Prépare une URL pour `\\href{url}{…}` : pas d'accolade, d'espace ni de contrôle."""
    if not url:
        return ""
    nettoyee = re.sub(r"[\s{}\\]", "", url)
    nettoyee = "".join(c for c in nettoyee if c.isascii() and c.isprintable())
    return nettoyee.replace("%", r"\%").replace("#", r"\#")
