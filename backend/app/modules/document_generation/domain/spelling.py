"""Contrôle orthographique par dictionnaire des lettres de motivation (TASK-013-18).

Le domaine ne connaît que le port `SpellingChecker` ; le dictionnaire réel est un adaptateur
d'infrastructure. Les anomalies sont des signalements, jamais un blocage : un dictionnaire se
trompe sur les noms propres et le jargon, donc ils sont écartés avant la vérification.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Iterable
from typing import Protocol

# Lettres (accents compris), éventuellement reliées par apostrophe ou trait d'union.
_MOT = re.compile(r"[^\W\d_]+(?:['\u2019\-][^\W\d_]+)*", re.UNICODE)
_MIN_LENGTH = 3
_MAX_ISSUES = 10


class SpellingChecker(Protocol):
    """Dictionnaire d'une langue ; `unknown` renvoie les mots inconnus (en minuscules)."""

    def unknown(self, words: Collection[str], language: str) -> set[str]: ...

    def suggestion(self, word: str, language: str) -> str | None: ...


def _candidats(texte: str) -> Iterable[str]:
    """Mots à vérifier : on écarte noms propres, sigles et très courts (élisions comprises)."""
    for mot in _MOT.findall(texte):
        for partie in re.split(r"['\u2019\-]", mot):
            if len(partie) < _MIN_LENGTH or partie[0].isupper():
                continue  # majuscule : nom propre, début de phrase ou sigle, donc non fiable
            yield partie.casefold()


def find_spelling_issues(
    texte: str,
    language: str,
    checker: SpellingChecker | None,
    *,
    ignore: Collection[str] = (),
) -> list[str]:
    """Fautes d'orthographe probables, sans doublon, bornées (`ignore` : termes du profil)."""
    if checker is None:
        return []
    ignores = {mot.casefold() for terme in ignore for mot in _MOT.findall(terme)}
    mots = {m for m in _candidats(texte) if m not in ignores}
    inconnus = checker.unknown(mots, language)
    ordre = [m for m in dict.fromkeys(_candidats(texte)) if m in inconnus]
    problemes: list[str] = []
    for mot in ordre[:_MAX_ISSUES]:
        piste = checker.suggestion(mot, language)
        suite = f" (vous vouliez peut-être « {piste} »)" if piste and piste != mot else ""
        problemes.append(f"Orthographe à vérifier : « {mot} »{suite}")
    return problemes
