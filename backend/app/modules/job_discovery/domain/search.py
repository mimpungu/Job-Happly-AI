"""Recherche dans les offres déjà collectées : filtres, tri, pages et contrats de lecture.

Distinct de `SearchCriteria` (interrogation des sources externes) : ici on parcourt la base
locale, donc tous les filtres sont facultatifs (« tout afficher » est légitime).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.domain.value_objects import (
    CountryCode,
    DomainValueError,
    EmploymentType,
    LanguageCode,
    RemoteType,
)
from app.modules.job_discovery.domain.enums import OfferState, OfferStatus

MAX_PAGE_SIZE = 100


class OfferSort(StrEnum):
    PUBLISHED_DESC = "published_desc"
    PUBLISHED_ASC = "published_asc"
    TITLE_ASC = "title_asc"
    COMPANY_ASC = "company_asc"
    SALARY_DESC = "salary_desc"
    RECENTLY_SEEN = "recently_seen"


class StateFilter(StrEnum):
    """Visibilité selon l'état posé par l'utilisateur ; ignorées masquées par défaut."""

    VISIBLE = "visible"
    SAVED = "saved"
    IGNORED = "ignored"
    ALL = "all"


class OfferFilter(BaseModel):
    """Filtres de la liste des offres. Un filtre absent (`None` ou vide) ne restreint rien."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str | None = Field(default=None, max_length=200)
    keywords: tuple[str, ...] = Field(default=(), max_length=20)
    company: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=200)
    country_codes: tuple[str, ...] = Field(default=(), max_length=30)
    remote_types: tuple[RemoteType, ...] = ()
    employment_types: tuple[EmploymentType, ...] = ()
    salary_min: Decimal | None = Field(default=None, ge=0)
    salary_currency: str | None = None
    published_since: datetime | None = None
    language: str | None = None
    statuses: tuple[OfferStatus, ...] = (OfferStatus.ACTIVE,)
    state: StateFilter = StateFilter.VISIBLE
    sort: OfferSort = OfferSort.PUBLISHED_DESC
    page: int = Field(default=1, ge=1, le=10_000)
    page_size: int = Field(default=25, ge=1, le=MAX_PAGE_SIZE)

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

    @field_validator("text", "company", "city")
    @classmethod
    def _texte_non_vide(cls, valeur: str | None) -> str | None:
        return (valeur or "").strip() or None

    @field_validator("keywords")
    @classmethod
    def _mots_cles_nettoyes(cls, valeurs: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(v.strip() for v in valeurs if v.strip()))

    @model_validator(mode="after")
    def _coherence(self) -> Self:
        # Comparer un salaire sans devise n'a aucun sens : 40 000 ≠ 40 000 $.
        if self.salary_min is not None and not self.salary_currency:
            raise ValueError("Un filtre de salaire exige une devise.")
        return self

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


@dataclass(frozen=True, slots=True)
class OfferSummary:
    id: uuid.UUID
    title: str
    company_name: str | None
    location: str | None
    country_code: str | None
    employment_type: str | None
    remote_type: str | None
    salary_min: Decimal | None
    salary_max: Decimal | None
    salary_currency: str | None
    published_at: datetime | None
    status: str
    state: OfferState | None
    source_keys: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OfferSourceView:
    """Où l'offre a été vue : attribution obligatoire, date de dernière observation."""

    source_key: str
    source_name: str
    source_url: str | None
    last_seen_at: datetime
    still_listed: bool


@dataclass(frozen=True, slots=True)
class OfferDetail:
    summary: OfferSummary
    description: str
    application_url: str
    language: str | None
    expires_at: datetime | None
    first_seen_at: datetime
    last_seen_at: datetime
    sources: tuple[OfferSourceView, ...]


@dataclass(frozen=True, slots=True)
class OfferPage:
    items: tuple[OfferSummary, ...]
    total: int
    page: int
    page_size: int

    @property
    def page_count(self) -> int:
        return max(1, -(-self.total // self.page_size))


class OfferNotFoundError(LookupError):
    """L'offre n'existe pas pour ce propriétaire."""


class OfferQueryRepository(Protocol):
    async def search(self, *, owner_id: uuid.UUID, offer_filter: OfferFilter) -> OfferPage: ...

    async def get(self, *, owner_id: uuid.UUID, offer_id: uuid.UUID) -> OfferDetail: ...

    async def set_state(
        self, *, owner_id: uuid.UUID, offer_id: uuid.UUID, state: OfferState | None
    ) -> None:
        """Pose l'état « sauvegardée » ou « ignorée » ; `None` le retire."""
        ...
