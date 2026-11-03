"""Critères de recherche (spécification §6.3), validés avant toute requête ou sauvegarde."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.domain.value_objects import (
    CountryCode,
    DomainValueError,
    EmploymentType,
    LanguageCode,
    RemoteType,
)


class SearchCriteria(BaseModel):
    """Critères d'une recherche. Un critère absent est `None` : il ne filtre pas."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str | None = Field(default=None, max_length=200)
    alternative_titles: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    skills: tuple[str, ...] = ()
    company: str | None = Field(default=None, max_length=200)
    sector: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=200)
    country_codes: tuple[str, ...] = ()
    radius_km: int | None = Field(default=None, ge=1, le=1000)
    remote_types: tuple[RemoteType, ...] = ()
    employment_types: tuple[EmploymentType, ...] = ()
    salary_min: Decimal | None = Field(default=None, ge=0)
    salary_max: Decimal | None = Field(default=None, ge=0)
    salary_currency: str | None = None
    experience_level: str | None = Field(default=None, max_length=50)
    published_since: datetime | None = None
    language: str | None = None
    page_size: int = Field(default=50, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=500)
    whole_catalogue: bool = False
    """Énumère tout le catalogue d'une source (collecte d'un job board d'entreprise) : seule
    intention qui dispense de préciser un critère de recherche."""

    @field_validator("country_codes")
    @classmethod
    def _pays_valides(cls, valeurs: tuple[str, ...]) -> tuple[str, ...]:
        try:
            return tuple(dict.fromkeys(CountryCode(v).value for v in valeurs))
        except DomainValueError as erreur:
            raise ValueError(str(erreur)) from erreur

    @field_validator("language")
    @classmethod
    def _langue_valide(cls, valeur: str | None) -> str | None:
        if valeur is None:
            return None
        try:
            return LanguageCode(valeur).value
        except DomainValueError as erreur:
            raise ValueError(str(erreur)) from erreur

    @field_validator("salary_currency")
    @classmethod
    def _devise_valide(cls, valeur: str | None) -> str | None:
        if valeur is None:
            return None
        devise = valeur.strip().upper()
        if len(devise) != 3 or not devise.isalpha():
            raise ValueError(f"Devise invalide : {valeur!r}")
        return devise

    @field_validator("title", "company", "sector", "city", "experience_level")
    @classmethod
    def _texte_non_vide(cls, valeur: str | None) -> str | None:
        if valeur is None:
            return None
        nettoye = valeur.strip()
        return nettoye or None

    @field_validator("alternative_titles", "keywords", "skills")
    @classmethod
    def _liste_nettoyee(cls, valeurs: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(v.strip() for v in valeurs if v.strip()))

    @model_validator(mode="after")
    def _coherence(self) -> Self:
        if not self.whole_catalogue and not (
            self.title or self.keywords or self.skills or self.company or self.sector
        ):
            raise ValueError(
                "Précisez au moins un intitulé, un mot-clé, une compétence, "
                "une entreprise ou un secteur."
            )
        if (
            self.salary_min is not None
            and self.salary_max is not None
            and self.salary_max < self.salary_min
        ):
            raise ValueError("Le salaire maximum ne peut être inférieur au minimum.")
        if (
            self.salary_min is not None or self.salary_max is not None
        ) and not self.salary_currency:
            raise ValueError("Un critère de salaire exige une devise.")
        if self.radius_km is not None and not self.city:
            raise ValueError("Un rayon exige une ville.")
        return self
