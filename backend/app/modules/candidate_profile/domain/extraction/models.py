"""Résultat de l'extraction : des **propositions** à valider, jamais des faits établis.

Chaque élément garde le texte d'origine (`source_text`) : l'utilisateur voit d'où vient
l'information (traçabilité) et peut la corriger. Une donnée absente du document reste `None`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from app.modules.candidate_profile.domain.extraction.dates import PartialDate


class Confidence(StrEnum):
    HIGH = "high"
    LOW = "low"
    """Plusieurs lectures possibles (ex. titre et entreprise interchangeables) : à vérifier."""


@dataclass(frozen=True, slots=True)
class ExtractedContact:
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    city: str | None = None
    linkedin_url: str | None = None
    website_url: str | None = None


@dataclass(frozen=True, slots=True)
class ExtractedExperience:
    title: str | None
    company: str | None
    location: str | None
    start: PartialDate | None
    end: PartialDate | None
    is_current: bool
    description: str | None
    achievements: tuple[str, ...]
    confidence: Confidence
    source_text: str


@dataclass(frozen=True, slots=True)
class ExtractedEducation:
    degree: str | None
    institution: str | None
    field_of_study: str | None
    start: PartialDate | None
    end: PartialDate | None
    confidence: Confidence
    source_text: str


@dataclass(frozen=True, slots=True)
class ExtractedSkill:
    name: str
    category: str | None
    source_text: str


@dataclass(frozen=True, slots=True)
class ExtractedLanguage:
    name: str
    language_code: str | None
    """Code ISO seulement si le nom est reconnu ; sinon `None`."""
    proficiency: str | None
    """Niveau CEFR ou « native » uniquement si explicite ; « courant » ne devient pas C1."""
    level_text: str | None
    source_text: str


@dataclass(frozen=True, slots=True)
class ExtractedCertification:
    name: str
    year: int | None
    source_text: str


@dataclass(frozen=True, slots=True)
class ExtractedProfile:
    contact: ExtractedContact = field(default_factory=ExtractedContact)
    experiences: tuple[ExtractedExperience, ...] = ()
    educations: tuple[ExtractedEducation, ...] = ()
    skills: tuple[ExtractedSkill, ...] = ()
    languages: tuple[ExtractedLanguage, ...] = ()
    certifications: tuple[ExtractedCertification, ...] = ()
    summary: str | None = None
    warnings: tuple[str, ...] = ()
