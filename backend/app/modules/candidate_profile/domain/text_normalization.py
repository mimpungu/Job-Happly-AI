"""Normalisation du texte extrait d'un document, avant toute analyse."""

from __future__ import annotations

import re
import unicodedata

_PUCES = "•▪▫●○◦■□◆◇►▶➢➤✓✔–—‣⁃∙·*"
# Espaces insécables et typographiques (U+00A0, U+2000–U+200A, U+202F, U+205F, U+3000).
_ESPACES_SPECIAUX = dict.fromkeys((160, *range(8192, 8203), 8239, 8287, 12288), " ")
# Césure conditionnelle, espaces de largeur nulle, joncteurs, BOM.
_INVISIBLES = dict.fromkeys((0x00AD, 0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF))
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_COUPURE_MOT = re.compile(r"(?<=[^\W\d_])-\n(?=[a-zàâäçéèêëîïôöùûüÿœæ])")
_PUCE_DEBUT = re.compile(rf"^[ \t]*[{re.escape(_PUCES)}][ \t]+(?=\S)")
_LIGNES_VIDES = re.compile(r"\n{3,}")


def normalize_document_text(brut: str) -> str:
    """Rend le texte stable et lisible sans en altérer le sens.

    - Unicode NFC (« é » en un seul caractère), ligatures PDF (ﬁ, ﬂ) dépliées par NFKC ciblé.
    - Retours à la ligne unifiés, caractères de contrôle et invisibles retirés.
    - Mot coupé en fin de ligne par un tiret (« dévelop-\\npement ») recollé, **uniquement** si la
      ligne suivante commence par une minuscule : « full-\\nStack » reste intact.
    - Puces de toute forme ramenées à « - », lignes vides multiples réduites à une.
    """
    texte = unicodedata.normalize("NFC", brut)
    texte = _deplier_ligatures(texte)
    texte = texte.replace("\r\n", "\n").replace("\r", "\n")
    texte = texte.translate(_ESPACES_SPECIAUX).translate(_INVISIBLES)
    texte = _CTRL.sub("", texte)
    texte = _COUPURE_MOT.sub("", texte)

    lignes = []
    for ligne in texte.split("\n"):
        ligne = _PUCE_DEBUT.sub("- ", ligne)
        ligne = re.sub(r"[ \t]{2,}", " ", ligne.strip(" \t"))
        lignes.append(ligne)
    return _LIGNES_VIDES.sub("\n\n", "\n".join(lignes)).strip()


_LIGATURES = {"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st"}


def _deplier_ligatures(texte: str) -> str:
    for ligature, remplacement in _LIGATURES.items():
        texte = texte.replace(ligature, remplacement)
    return texte
