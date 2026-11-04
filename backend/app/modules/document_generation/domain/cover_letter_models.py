"""Modèles de domaine de la lettre de motivation (EPIC 013)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SUPPORTED_LANGUAGES = ("fr", "en")

_WORD = re.compile("\\w+(?:['\u2019-]\\w+)*")


def count_words(text: str) -> int:
    """Nombre de mots (une apostrophe ou un trait d'union ne coupe pas un mot)."""
    return len(_WORD.findall(text))


class IncompleteProfileError(ValueError):
    """Le profil ne permet pas de rédiger une lettre exacte (nom ou contenu manquant)."""


@dataclass(frozen=True)
class CompanyOfferContext:
    """Informations de l'offre et de l'entreprise. Aucune recherche externe : seules les
    informations de l'annonce sont utilisées (TASK-013-01, 02, 03, 05)."""

    job_title: str
    company_name: str | None = None
    company_location: str | None = None
    company_sector: str | None = None
    responsibilities: tuple[str, ...] = ()
    required_skills: tuple[str, ...] = ()
    offer_text: str = ""


@dataclass(frozen=True)
class LetterFacts:
    """Faits du profil effectivement cités dans la lettre, vérifiés contre le profil maître."""

    experiences: tuple[tuple[str | None, str | None], ...] = ()  # (entreprise, intitulé)
    skills: tuple[str, ...] = ()
    achievements: tuple[str, ...] = ()
    degrees: tuple[str, ...] = ()


@dataclass(frozen=True)
class CoverLetterContent:
    """Lettre en 4 parties conforme au prompt maître."""

    language: str
    candidate_name: str
    candidate_city: str | None
    candidate_email: str | None
    candidate_phone: str | None
    recipient_company: str | None
    recipient_department: str | None
    recipient_name: str | None
    date_and_location: str
    subject: str
    salutation: str
    introduction: str  # Partie 1 — Introduction
    background_highlight: str  # Partie 2 — Valorisation du parcours
    added_value: str  # Partie 3 — Valeur ajoutée et motivation
    closing_and_call_to_action: str  # Partie 4 — Demande d'entretien
    complimentary_close: str
    signature: str
    user_written: tuple[str, ...] = ()
    """Textes saisis par l'utilisateur : non contrôlés par le détecteur de faits inventés."""
    facts: LetterFacts = field(default_factory=LetterFacts)

    def body_paragraphs(self) -> tuple[str, ...]:
        return (
            self.introduction,
            self.background_highlight,
            self.added_value,
            self.closing_and_call_to_action,
        )

    def body_text(self) -> str:
        return "\n\n".join(p for p in self.body_paragraphs() if p)

    @property
    def word_count(self) -> int:
        return count_words(self.body_text())

    def full_text(self) -> str:
        parties = [
            self.subject,
            self.salutation,
            *self.body_paragraphs(),
            self.complimentary_close,
            self.signature,
        ]
        return "\n\n".join(p for p in parties if p)


@dataclass(frozen=True)
class CoverLetterAudit:
    """Audit éditorial et factuel, indicatif (grille sur 100 du prompt maître §12)."""

    score: int
    passed: bool
    relevance_score: int  # /30
    personalization_score: int  # /25
    experience_score: int  # /20
    editorial_score: int  # /15
    structure_score: int  # /10
    word_count: int
    length_status: str  # "short" | "optimal" | "long"
    is_length_optimal: bool  # 250 à 350 mots
    cv_coherent: bool
    page_count: int | None = None
    generic_phrases_detected: tuple[str, ...] = ()
    spelling_issues: tuple[str, ...] = ()
    issues: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "passed": self.passed,
            "relevance_score": self.relevance_score,
            "personalization_score": self.personalization_score,
            "experience_score": self.experience_score,
            "editorial_score": self.editorial_score,
            "structure_score": self.structure_score,
            "word_count": self.word_count,
            "length_status": self.length_status,
            "is_length_optimal": self.is_length_optimal,
            "cv_coherent": self.cv_coherent,
            "page_count": self.page_count,
            "generic_phrases_detected": list(self.generic_phrases_detected),
            "spelling_issues": list(self.spelling_issues),
            "issues": list(self.issues),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CoverLetterAudit:
        return cls(
            score=int(data.get("score", 0)),
            passed=bool(data.get("passed", False)),
            relevance_score=int(data.get("relevance_score", 0)),
            personalization_score=int(data.get("personalization_score", 0)),
            experience_score=int(data.get("experience_score", 0)),
            editorial_score=int(data.get("editorial_score", 0)),
            structure_score=int(data.get("structure_score", 0)),
            word_count=int(data.get("word_count", 0)),
            length_status=str(data.get("length_status", "short")),
            is_length_optimal=bool(data.get("is_length_optimal", False)),
            cv_coherent=bool(data.get("cv_coherent", False)),
            page_count=data.get("page_count"),
            generic_phrases_detected=tuple(data.get("generic_phrases_detected", ())),
            spelling_issues=tuple(data.get("spelling_issues", ())),
            issues=tuple(data.get("issues", ())),
        )


class CoverLetterOptions(BaseModel):
    """Options de la lettre. Langues gérées : français et anglais (TASK-013-16)."""

    model_config = ConfigDict(frozen=True)

    language: Literal["fr", "en"] = "fr"
    country_code: str | None = Field(default=None, pattern=r"^[A-Za-z]{2}$")
    recipient_name: str | None = Field(default=None, max_length=200)
    recipient_department: str | None = Field(default=None, max_length=200)
    custom_opening: str | None = Field(default=None, max_length=1000)
    motivation: str | None = Field(default=None, max_length=1500)
    """Paragraphe de motivation rédigé par l'utilisateur, inséré tel quel (partie 3)."""

    @field_validator("country_code")
    @classmethod
    def _majuscules(cls, valeur: str | None) -> str | None:
        return valeur.upper() if valeur else None
