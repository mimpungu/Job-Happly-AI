"""Entrées et sorties du moteur de correspondance (score déterministe, sans IA).

Le moteur est pur : il reçoit des **faits** sur le profil et sur l'offre (`ProfileFacts`,
`OfferFacts`) et ne connaît ni la base ni les autres modules. Un score est un indicateur
d'aide au tri, jamais une prédiction d'embauche.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class Criterion(StrEnum):
    """Critères du score (spécification §8). L'ordre est celui de l'affichage."""

    JOB_TITLE = "job_title"
    SKILLS = "skills"
    EXPERIENCE = "experience"
    EDUCATION = "education"
    LOCATION = "location"
    CONTRACT = "contract"
    SALARY = "salary"
    REMOTE = "remote"
    FRESHNESS = "freshness"
    MANDATORY = "mandatory_requirements"


CRITERION_LABELS: dict[Criterion, str] = {
    Criterion.JOB_TITLE: "Métier",
    Criterion.SKILLS: "Compétences",
    Criterion.EXPERIENCE: "Expérience",
    Criterion.EDUCATION: "Formation",
    Criterion.LOCATION: "Localisation",
    Criterion.CONTRACT: "Contrat",
    Criterion.SALARY: "Salaire",
    Criterion.REMOTE: "Télétravail",
    Criterion.FRESHNESS: "Ancienneté de l'annonce",
    Criterion.MANDATORY: "Exigences obligatoires",
}


class Status(StrEnum):
    """Un critère est évalué, ou ses données manquent : jamais « 0 » faute d'information."""

    EVALUATED = "evaluated"
    MISSING_DATA = "missing_data"


class MatchKind(StrEnum):
    """Statut d'un élément comparé (spécification §8)."""

    PRESENT = "present"
    PARTIAL = "partial"
    ABSENT = "absent"
    """Exigé par l'offre et introuvable dans le profil — pas forcément absent chez la personne."""
    UNVERIFIABLE = "unverifiable"
    """Exigence qu'on ne sait pas comparer automatiquement (ex. « esprit d'équipe »)."""


class Reliability(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True, slots=True)
class YearMonth:
    year: int
    month: int | None = None


@dataclass(frozen=True, slots=True)
class ExperiencePeriod:
    start: YearMonth | None
    end: YearMonth | None
    is_current: bool = False


@dataclass(frozen=True, slots=True)
class ProfileFacts:
    """Ce que le moteur sait du candidat. Une liste vide signifie « non renseigné »."""

    titles: tuple[str, ...] = ()
    skills: tuple[str, ...] = ()
    experience_periods: tuple[ExperiencePeriod, ...] = ()
    degrees: tuple[str, ...] = ()
    country_codes: tuple[str, ...] = ()
    cities: tuple[str, ...] = ()
    remote_types: tuple[str, ...] = ()
    employment_types: tuple[str, ...] = ()
    salary_min: Decimal | None = None
    salary_currency: str | None = None


@dataclass(frozen=True, slots=True)
class OfferFacts:
    title: str
    description: str
    location: str | None = None
    country_code: str | None = None
    employment_type: str | None = None
    remote_type: str | None = None
    salary_min: Decimal | None = None
    salary_max: Decimal | None = None
    salary_currency: str | None = None
    published_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class MatchItem:
    """Une correspondance ou un écart, avec de quoi l'expliquer."""

    kind: MatchKind
    label: str
    detail: str | None = None
    criterion: Criterion | None = None
    """Critère d'origine, renseigné quand les éléments sont regroupés dans le résultat global."""


@dataclass(frozen=True, slots=True)
class CriterionResult:
    criterion: Criterion
    status: Status
    weight: Decimal
    score: Decimal | None
    """0 à 1 ; `None` quand les données manquent."""
    explanation: str
    items: tuple[MatchItem, ...] = ()
    uncertain: bool = False
    """Plusieurs lectures possibles (ex. dates partielles) : le résultat est à vérifier."""


@dataclass(frozen=True, slots=True)
class Weights:
    """Pondérations des critères. Seuls les rapports entre poids comptent (normalisés)."""

    values: dict[Criterion, Decimal]

    def get(self, criterion: Criterion) -> Decimal:
        return self.values.get(criterion, Decimal(0))

    def total(self) -> Decimal:
        return sum(self.values.values(), Decimal(0))


@dataclass(frozen=True, slots=True)
class MatchResult:
    score: Decimal | None
    """Sur 100 ; `None` si aucun critère n'a pu être évalué."""
    coverage: Decimal
    """Part (0 à 1) du poids total réellement évaluée : mesure la solidité du score."""
    reliability: Reliability
    weights_version: str
    criteria: tuple[CriterionResult, ...]
    matches: tuple[MatchItem, ...] = field(default=())
    gaps: tuple[MatchItem, ...] = field(default=())
    summary: str = ""
    disclaimer: str = (
        "Score indicatif d'aide au tri, calculé par des règles lisibles. "
        "Ce n'est pas une probabilité d'être recruté."
    )
