"""Schémas Pydantic de l'API des lettres de motivation."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class GenerateCoverLetterRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    offer_id: uuid.UUID
    language: Literal["fr", "en"] = "fr"
    country_code: str | None = Field(default=None, pattern=r"^[A-Za-z]{2}$")
    recipient_name: str | None = Field(default=None, max_length=200)
    recipient_department: str | None = Field(default=None, max_length=200)
    custom_opening: str | None = Field(default=None, max_length=1000)
    motivation: str | None = Field(default=None, max_length=1500)


class CoverLetterAuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    score: int
    passed: bool
    relevance_score: int
    personalization_score: int
    experience_score: int
    editorial_score: int
    structure_score: int
    word_count: int
    length_status: str
    is_length_optimal: bool
    cv_coherent: bool
    page_count: int | None = None
    generic_phrases_detected: list[str] = Field(default_factory=list)
    spelling_issues: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)


class CoverLetterGenerationMeta(BaseModel):
    origin: str
    prompt_version: str | None = None
    language: str | None = None
    country_code: str | None = None


class CoverLetterContentResponse(BaseModel):
    """Texte de la lettre, pour relecture avant envoi."""

    model_config = ConfigDict(from_attributes=True)

    candidate_name: str
    recipient_company: str | None
    date_and_location: str
    subject: str
    salutation: str
    introduction: str
    background_highlight: str
    added_value: str
    closing_and_call_to_action: str
    complimentary_close: str
    signature: str
    word_count: int


class CoverLetterVersionResponse(BaseModel):
    id: uuid.UUID
    version: int
    created_at: datetime
    size_bytes: int
    sha256: str
    audit: CoverLetterAuditResponse | None = None
    generation: CoverLetterGenerationMeta | None = None


class CoverLetterResponse(BaseModel):
    id: uuid.UUID
    kind: str
    title: str
    language: str
    offer_id: uuid.UUID | None
    created_at: datetime
    versions: list[CoverLetterVersionResponse] = Field(default_factory=list)
    content: CoverLetterContentResponse | None = None
