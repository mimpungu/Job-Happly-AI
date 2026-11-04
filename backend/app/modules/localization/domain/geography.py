"""Référentiel géographique (TASK-017-06 à 017-10) : pays, langues officielles, devises.

Les données ne sont **jamais codées en dur** : elles viennent d'un référentiel normalisé (CLDR,
ISO 3166, ISO 4217) derrière le port `GeographyReference`. Le domaine ne connaît que ce contrat.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Country:
    code: str
    """ISO 3166-1 alpha-2."""
    name: str
    """Nom dans la langue demandée."""
    official_languages: tuple[str, ...]
    """Codes de langue (ex. `fr`, `de`) ; vide si le référentiel n'en déclare pas."""
    currencies: tuple[str, ...]
    """Devises ISO 4217 actuellement en usage, la principale d'abord."""


@dataclass(frozen=True, slots=True)
class Currency:
    code: str
    """ISO 4217."""
    name: str
    symbol: str


class GeographyReference(Protocol):
    def countries(self, locale: str) -> tuple[Country, ...]:
        """Tous les pays, triés par nom dans `locale`."""
        ...

    def country(self, code: str, locale: str) -> Country | None: ...

    def currencies(self, locale: str) -> tuple[Currency, ...]: ...

    def has_currency(self, code: str) -> bool: ...
