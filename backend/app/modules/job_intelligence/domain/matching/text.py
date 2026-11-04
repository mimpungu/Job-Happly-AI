"""Normalisation de texte commune aux critères."""

from __future__ import annotations

import re
import unicodedata


def fold(texte: str) -> str:
    """Minuscules sans accents : « Développeur » et « developpeur » se comparent égaux."""
    plie = texte.casefold()
    if plie.isascii():
        return plie  # cas courant (texte anglais, sigles) : rien à décomposer
    decompose = unicodedata.normalize("NFD", plie)
    return "".join(c for c in decompose if not unicodedata.combining(c))


_NON_ALNUM = re.compile(r"[^a-z0-9+#]+")


def compact(texte: str) -> str:
    """Forme de comparaison d'un nom de compétence : « Node.js » et « nodejs » coïncident,
    « C++ » et « C# » restent distincts de « C »."""
    return _NON_ALNUM.sub("", fold(texte))


def words(texte: str) -> list[str]:
    return [m for m in re.split(r"[^a-z0-9+#]+", fold(texte)) if m]
