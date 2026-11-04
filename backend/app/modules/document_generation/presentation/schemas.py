"""Schémas Pydantic pour l'API REST de génération de documents."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.document_generation.domain.enums import LengthTarget, ResumeTemplateStyle


class GenerateResumeRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    offer_id: uuid.UUID | None = None
    title: str | None = Field(default=None, max_length=300)
    target_role: str | None = Field(default=None, max_length=200)
    language: str = Field(default="fr", pattern=r"^[a-z]{2,3}(-[A-Z]{2})?$")
    style: ResumeTemplateStyle = ResumeTemplateStyle.CLASSIC
    length_target: LengthTarget = LengthTarget.AUTO
    max_experiences: int | None = Field(default=None, ge=1, le=20)
    custom_summary: str | None = Field(default=None, max_length=2000)


class CompileVersionRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    latex_source: str = Field(min_length=10, max_length=1_000_000)
    expected_keywords: list[str] = Field(default_factory=list)


class ATSCheckResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    status: str
    message: str
    details: str | None = None


class ATSReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    score: int
    passed: bool
    checks: list[ATSCheckResponse]
    word_count: int
    character_count: int
    page_count: int
    keywords_found: list[str]
    keywords_missing: list[str]
    reading_order_valid: bool
    accents_preserved: bool
    single_column: bool


class DocumentVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version: int
    created_at: datetime
    size_bytes: int
    sha256: str
    ats_report: ATSReportResponse | None = None


class GeneratedDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    title: str
    language: str
    offer_id: uuid.UUID | None
    created_at: datetime
    versions: list[DocumentVersionResponse] = Field(default_factory=list)


class ComparisonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: uuid.UUID
    version_a: int
    version_b: int
    diff_latex: str
    score_a: int | None
    score_b: int | None
    size_diff_bytes: int

