"""Modèles de domaine pour la génération de lettres de motivation (EPIC 013)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


@dataclass(frozen=True)
class CompanyOfferContext:
    """Informations extraites de l'offre et de l'entreprise (TASK-013-01, 02, 03, 05)."""

    company_name: str
    job_title: str
    company_location: str | None = None
    company_sector: str | None = None
    responsibilities: tuple[str, ...] = ()
    key_expectations: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()


@dataclass(frozen=True)
class CoverLetterContent:
    """Structure éditoriale complète en 4 parties conformément au prompt maître."""

    candidate_name: str
    candidate_address: str | None
    candidate_email: str | None
    candidate_phone: str | None
    recipient_company: str
    recipient_department: str | None
    date_and_location: str
    subject: str
    salutation: str
    introduction: str  # Partie 1 — Introduction accrocheuse
    background_highlight: str  # Partie 2 — Valorisation du parcours
    added_value: str  # Partie 3 — Valeur ajoutée et motivation
    closing_and_call_to_action: str  # Partie 4 — Demande d'entretien
    complimentary_close: str
    signature: str
    word_count: int

    def full_text(self) -> str:
        """Texte brut complet de la lettre pour analyse et audit."""
        parties = [
            f"Objet : {self.subject}",
            self.salutation,
            self.introduction,
            self.background_highlight,
            self.added_value,
            self.closing_and_call_to_action,
            self.complimentary_close,
            self.signature,
        ]
        return "\n\n".join(p for p in parties if p)


@dataclass(frozen=True)
class CoverLetterAudit:
    """Audit qualité et conformité de la lettre (TASK-013-09, 10, 11, 18)."""

    score: int  # Note sur 100
    passed: bool
    relevance_score: int  # /30
    personalization_score: int  # /25
    experience_score: int  # /20
    editorial_score: int  # /15
    structure_score: int  # /10
    word_count: int
    is_length_optimal: bool  # 250 - 350 mots
    cv_coherent: bool
    generic_phrases_detected: tuple[str, ...] = ()
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
            "is_length_optimal": self.is_length_optimal,
            "cv_coherent": self.cv_coherent,
            "generic_phrases_detected": list(self.generic_phrases_detected),
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
            is_length_optimal=bool(data.get("is_length_optimal", False)),
            cv_coherent=bool(data.get("cv_coherent", False)),
            generic_phrases_detected=tuple(data.get("generic_phrases_detected", ())),
            issues=tuple(data.get("issues", ())),
        )


class CoverLetterOptions(BaseModel):
    """Options de personnalisation pour la génération d'une lettre (TASK-013-16, 18)."""

    model_config = ConfigDict(frozen=True)

    language: str = Field(default="fr", pattern=r"^[a-z]{2,3}(-[A-Z]{2})?$")
    country_code: str | None = Field(default=None, max_length=2)
    recipient_name: str | None = Field(default=None, max_length=200)
    recipient_department: str | None = Field(default=None, max_length=200)
    custom_opening: str | None = Field(default=None, max_length=1000)

