"""Normalisation de texte partagée par le générateur et l'évaluation."""

from __future__ import annotations

import re
import unicodedata

_NOMBRE = re.compile(r"\d+(?:[.,]\d+)?")
_MOT = re.compile(r"[\w+#.]+", re.UNICODE)


def norm(texte: str) -> str:
    """Minuscules sans accents : comparaison tolérante (« Développeur » = « developpeur »)."""
    texte = texte.replace("\u2019", "'")
    sans_accent = "".join(
        c for c in unicodedata.normalize("NFKD", texte) if not unicodedata.combining(c)
    )
    return re.sub(r"\s+", " ", sans_accent.casefold()).strip()


def mentions(texte: str, terme: str) -> bool:
    """Le terme figure dans le texte comme mot entier (« Java » ne correspond pas à JavaScript)."""
    t = norm(terme)
    if not t:
        return False
    return re.search(rf"(?<![\w+#]){re.escape(t)}(?![\w+#])", norm(texte)) is not None


def numbers(texte: str) -> set[str]:
    return {n.replace(",", ".") for n in _NOMBRE.findall(texte)}


def word_count(texte: str) -> int:
    return len(_MOT.findall(texte))
