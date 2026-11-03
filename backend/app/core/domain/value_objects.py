"""Value objects partagés du domaine (immuables, validés à la construction).

Règle : une information absente est `None`, jamais zéro ni chaîne vide.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum

_COUNTRY_RE = re.compile(r"^[A-Z]{2}$")
_LANGUAGE_RE = re.compile(r"^[a-z]{2,3}(-[A-Z]{2})?$")
_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")


class DomainValueError(ValueError):
    """Valeur invalide pour un value object."""


@dataclass(frozen=True, slots=True)
class CountryCode:
    """Code pays ISO 3166-1 alpha-2 (ex. `FR`). Aucune liste fermée de pays n'est codée en dur."""

    value: str

    def __post_init__(self) -> None:
        normalise = self.value.strip().upper()
        if not _COUNTRY_RE.fullmatch(normalise):
            raise DomainValueError(f"Code pays invalide : {self.value!r}")
        object.__setattr__(self, "value", normalise)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class LanguageCode:
    """Code langue BCP 47 simplifié : `fr`, `en`, `pt-BR`."""

    value: str

    def __post_init__(self) -> None:
        brut = self.value.strip()
        langue, separateur, region = brut.partition("-")
        if separateur and not region:
            raise DomainValueError(f"Code langue invalide : {self.value!r}")
        normalise = langue.lower() + (f"-{region.upper()}" if region else "")
        if not _LANGUAGE_RE.fullmatch(normalise):
            raise DomainValueError(f"Code langue invalide : {self.value!r}")
        object.__setattr__(self, "value", normalise)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class Money:
    """Montant décimal dans une devise ISO 4217. Jamais de flottant pour l'argent."""

    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            raise DomainValueError("Le montant doit être un Decimal.")
        if not self.amount.is_finite() or self.amount < 0:
            raise DomainValueError(f"Montant invalide : {self.amount}")
        devise = self.currency.strip().upper()
        if not _CURRENCY_RE.fullmatch(devise):
            raise DomainValueError(f"Devise invalide : {self.currency!r}")
        object.__setattr__(self, "currency", devise)

    def __add__(self, autre: Money) -> Money:
        if self.currency != autre.currency:
            raise DomainValueError("Addition impossible entre devises différentes.")
        return Money(self.amount + autre.amount, self.currency)


@dataclass(frozen=True, slots=True)
class DateRange:
    """Période. `end=None` signifie « en cours » (et non une date inconnue)."""

    start: date
    end: date | None = None

    def __post_init__(self) -> None:
        if self.end is not None and self.end < self.start:
            raise DomainValueError("La fin d'une période ne peut précéder son début.")

    @property
    def is_ongoing(self) -> bool:
        return self.end is None

    def contains(self, jour: date) -> bool:
        return self.start <= jour and (self.end is None or jour <= self.end)


class EmploymentType(StrEnum):
    PERMANENT = "permanent"
    FIXED_TERM = "fixed_term"
    FREELANCE = "freelance"
    INTERNSHIP = "internship"
    APPRENTICESHIP = "apprenticeship"
    PART_TIME = "part_time"
    TEMPORARY = "temporary"
    OTHER = "other"


class RemoteType(StrEnum):
    ON_SITE = "on_site"
    HYBRID = "hybrid"
    REMOTE = "remote"


class SkillLevel(StrEnum):
    """Niveau déclaré par le candidat. Absence de niveau = `None`, pas `BEGINNER`."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"
