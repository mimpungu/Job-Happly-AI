"""Adaptateur du correcteur orthographique : dictionnaires embarqués, entièrement hors ligne.

`pyspellchecker` ne fait aucun appel réseau : le texte de la lettre ne quitte jamais la machine.
Une langue sans dictionnaire n'est pas vérifiée (aucun faux positif).
"""

from __future__ import annotations

from collections.abc import Collection
from functools import lru_cache

from spellchecker import SpellChecker

_LANGUES = frozenset({"fr", "en", "es", "de", "pt", "it", "nl"})


@lru_cache(maxsize=len(_LANGUES))
def _dictionnaire(langue: str) -> SpellChecker:
    return SpellChecker(language=langue)


def _base(langue: str) -> str:
    return langue.lower().split("-")[0]


class PySpellChecker:
    def unknown(self, words: Collection[str], language: str) -> set[str]:
        langue = _base(language)
        if langue not in _LANGUES:
            return set()
        return set(_dictionnaire(langue).unknown(words))

    def suggestion(self, word: str, language: str) -> str | None:
        langue = _base(language)
        if langue not in _LANGUES:
            return None
        return _dictionnaire(langue).correction(word)
