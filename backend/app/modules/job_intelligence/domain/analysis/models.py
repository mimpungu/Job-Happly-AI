"""Résultat structuré de l'analyse d'une offre (EPIC 011). Tout est lu dans le texte de l'offre."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

ANALYSIS_VERSION = "a2"
"""À incrémenter dès qu'une règle d'extraction change : une analyse est reproductible pour une
version de règles et une empreinte de texte."""


class VisaPolicy(StrEnum):
    SPONSORSHIP_OFFERED = "sponsorship_offered"
    NO_SPONSORSHIP = "no_sponsorship"
    WORK_AUTHORIZATION_REQUIRED = "work_authorization_required"


@dataclass(frozen=True, slots=True)
class LanguageRequirement:
    language: str
    """Code ISO 639-1 (fr, en, de…)."""
    level: str | None
    """Niveau tel qu'écrit dans l'offre (« courant », « B2 »…), jamais deviné."""
    mandatory: bool
    evidence: str


@dataclass(frozen=True, slots=True)
class Mobility:
    visa: VisaPolicy | None
    relocation_offered: bool
    travel: str | None
    """Déplacements demandés, tels qu'écrits (« jusqu'à 20 % »)."""
    evidence: tuple[str, ...]

    @property
    def is_empty(self) -> bool:
        return self.visa is None and not self.relocation_offered and self.travel is None


class MissingInfo(StrEnum):
    """Information utile au candidat que l'offre ne donne pas."""

    SALARY = "salary"
    LOCATION = "location"
    EMPLOYMENT_TYPE = "employment_type"
    REMOTE = "remote"
    EXPERIENCE = "experience"
    REQUIREMENTS = "requirements"
    MISSIONS = "missions"
    LANGUAGES = "languages"


MISSING_LABELS: dict[MissingInfo, str] = {
    MissingInfo.SALARY: "Salaire non indiqué",
    MissingInfo.LOCATION: "Lieu non indiqué",
    MissingInfo.EMPLOYMENT_TYPE: "Type de contrat non indiqué",
    MissingInfo.REMOTE: "Politique de télétravail non indiquée",
    MissingInfo.EXPERIENCE: "Expérience demandée non indiquée",
    MissingInfo.REQUIREMENTS: "Aucune rubrique d'exigences identifiée dans l'annonce",
    MissingInfo.MISSIONS: "Aucune rubrique de missions identifiée dans l'annonce",
    MissingInfo.LANGUAGES: "Langues exigées non précisées",
}


@dataclass(frozen=True, slots=True)
class OfferAnalysis:
    version: str
    missions: tuple[str, ...]
    mandatory_skills: tuple[str, ...]
    expected_skills: tuple[str, ...]
    desired_skills: tuple[str, ...]
    technologies: tuple[str, ...]
    """Outils et technologies cités n'importe où dans l'annonce (exigence ou simple mention)."""
    years_experience: int | None
    years_mandatory: bool | None
    languages: tuple[LanguageRequirement, ...]
    mobility: Mobility
    missing: tuple[MissingInfo, ...]
    summary: str | None
    """Résumé **extractif** : phrases de l'annonce, jamais reformulées ni complétées."""

    def to_dict(self) -> dict[str, Any]:
        """JSON stockable et affichable (énumérations en texte)."""
        return {
            "version": self.version,
            "missions": list(self.missions),
            "mandatory_skills": list(self.mandatory_skills),
            "expected_skills": list(self.expected_skills),
            "desired_skills": list(self.desired_skills),
            "technologies": list(self.technologies),
            "years_experience": self.years_experience,
            "years_mandatory": self.years_mandatory,
            "languages": [
                {
                    "language": x.language,
                    "level": x.level,
                    "mandatory": x.mandatory,
                    "evidence": x.evidence,
                }
                for x in self.languages
            ],
            "mobility": {
                "visa": self.mobility.visa.value if self.mobility.visa else None,
                "relocation_offered": self.mobility.relocation_offered,
                "travel": self.mobility.travel,
                "evidence": list(self.mobility.evidence),
            },
            "missing": [{"code": m.value, "label": MISSING_LABELS[m]} for m in self.missing],
            "summary": self.summary,
        }
