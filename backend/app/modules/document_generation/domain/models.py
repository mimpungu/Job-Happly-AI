from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.modules.document_generation.domain.enums import (
    ATSCheckStatus,
    LengthTarget,
    ResumeTemplateStyle,
)


@dataclass(frozen=True)
class ATSCheckResult:
    """Résultat d'une vérification ATS unitaire."""

    name: str
    status: ATSCheckStatus
    message: str
    details: str | None = None


@dataclass(frozen=True)
class ATSReport:
    """Rapport d'audit ATS complet extrait du PDF compilé."""

    score: int  # 0 à 100
    passed: bool
    checks: tuple[ATSCheckResult, ...]
    word_count: int
    character_count: int
    page_count: int
    keywords_found: tuple[str, ...]
    keywords_missing: tuple[str, ...]
    reading_order_valid: bool
    accents_preserved: bool
    single_column: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "passed": self.passed,
            "checks": [
                {
                    "name": c.name,
                    "status": c.status.value,
                    "message": c.message,
                    "details": c.details,
                }
                for c in self.checks
            ],
            "word_count": self.word_count,
            "character_count": self.character_count,
            "page_count": self.page_count,
            "keywords_found": list(self.keywords_found),
            "keywords_missing": list(self.keywords_missing),
            "reading_order_valid": self.reading_order_valid,
            "accents_preserved": self.accents_preserved,
            "single_column": self.single_column,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ATSReport:
        checks = tuple(
            ATSCheckResult(
                name=c["name"],
                status=ATSCheckStatus(c["status"]),
                message=c["message"],
                details=c.get("details"),
            )
            for c in data.get("checks", [])
        )
        return cls(
            score=int(data.get("score", 0)),
            passed=bool(data.get("passed", False)),
            checks=checks,
            word_count=int(data.get("word_count", 0)),
            character_count=int(data.get("character_count", 0)),
            page_count=int(data.get("page_count", 0)),
            keywords_found=tuple(data.get("keywords_found", ())),
            keywords_missing=tuple(data.get("keywords_missing", ())),
            reading_order_valid=bool(data.get("reading_order_valid", False)),
            accents_preserved=bool(data.get("accents_preserved", False)),
            single_column=bool(data.get("single_column", False)),
        )


@dataclass(frozen=True)
class FactCheckResult:
    """Résultat du contrôle d'intégrité factuelle par rapport au profil maître."""

    is_valid: bool
    unverified_companies: tuple[str, ...] = ()
    unverified_institutions: tuple[str, ...] = ()
    unverified_skills: tuple[str, ...] = ()
    issues: tuple[str, ...] = ()


@dataclass(frozen=True)
class DocumentVersionInfo:
    """Informations de synthèse sur une version d'un document."""

    id: uuid.UUID
    document_id: uuid.UUID
    version: int
    created_at: datetime
    size_bytes: int
    sha256: str
    ats_score: int | None
    storage_key: str


@dataclass(frozen=True)
class DocumentComparison:
    """Comparaison différentielle entre deux versions d'un document."""

    document_id: uuid.UUID
    version_a: int
    version_b: int
    diff_latex: str
    score_a: int | None
    score_b: int | None
    size_diff_bytes: int


class ResumeGenerationOptions(BaseModel):
    """Options de personnalisation pour la génération d'un CV."""

    model_config = ConfigDict(frozen=True)

    title: str | None = Field(default=None, max_length=300)
    target_role: str | None = Field(default=None, max_length=200)
    language: str = Field(default="fr", pattern=r"^[a-z]{2,3}(-[A-Z]{2})?$")
    style: ResumeTemplateStyle = ResumeTemplateStyle.CLASSIC
    length_target: LengthTarget = LengthTarget.AUTO
    max_experiences: int | None = Field(default=None, ge=1, le=20)
    custom_summary: str | None = Field(default=None, max_length=2000)
