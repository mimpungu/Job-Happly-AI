"""Schémas Pydantic pour l'API REST de lettres de motivation."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field


class GenerateCoverLetterRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    offer_id: uuid.UUID
    language: str = Field(default="fr", pattern=r"^[a-z]{2,3}(-[A-Z]{2})?$")
    country_code: str | None = Field(default=None, max_length=2)
    recipient_name: str | None = Field(default=None, max_length=200)
    recipient_department: str | None = Field(default=None, max_length=200)
    custom_opening: str | None = Field(default=None, max_length=1000)


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
    is_length_optimal: bool
    cv_coherent: bool
    generic_phrases_detected: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)


class CoverLetterContentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    candidate_name: str
    recipient_company: str
    subject: str
    salutation: str
    introduction: str
    background_highlight: str
    added_value: str
    closing_and_call_to_action: str
    complimentary_close: str
    signature: str
    word_count: int

