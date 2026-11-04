"""Contenu d'une préparation, d'une simulation et d'une fiche entretien (valeurs immuables)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.interview_preparation.domain.enums import (
    InterviewFormat,
    InterviewOutcome,
    InterviewStage,
    QuestionCategory,
    QuestionSource,
)


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class OfferFacts(_Frozen):
    """Ce que l'on sait de l'offre : jamais plus que ce qui a été collecté ou analysé."""

    title: str
    company: str | None = None
    description: str = ""
    required_skills: tuple[str, ...] = ()


class Question(_Frozen):
    id: str
    category: QuestionCategory
    text: str
    rationale: str
    """Pourquoi cette question est posée pour ce poste (visible de l'utilisateur)."""
    skill: str | None = None
    skill_gap: bool = False
    """Vrai si la compétence est demandée par l'offre mais absente du profil."""
    source: QuestionSource = QuestionSource.RULES


class Highlight(_Frozen):
    """Expérience du parcours à mettre en avant, avec les termes de l'offre qu'elle recoupe."""

    experience_label: str
    matched_terms: tuple[str, ...]
    achievements: tuple[str, ...]


class AnswerOutline(_Frozen):
    """Trame de réponse bâtie sur le vrai parcours ; ce qui manque est marqué à compléter."""

    question_id: str
    experience_label: str | None
    situation: str | None
    actions: tuple[str, ...]
    result: str | None = None
    to_complete: tuple[str, ...] = ()


class PreparationContent(_Frozen):
    questions: tuple[Question, ...]
    pitch: str
    pitch_to_complete: tuple[str, ...] = ()
    highlights: tuple[Highlight, ...]
    answers: tuple[AnswerOutline, ...]
    recruiter_questions: tuple[str, ...]
    skills_matched: tuple[str, ...] = ()
    skills_to_prepare: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


class AnswerFeedback(_Frozen):
    score: int = Field(ge=0, le=100)
    strengths: tuple[str, ...] = ()
    improvements: tuple[str, ...] = ()
    unverified_numbers: tuple[str, ...] = ()
    ai_comments: tuple[str, ...] = ()
    ai_status: str | None = None
    """`None` : pas d'IA demandée ; sinon `applied` ou `unavailable`."""


class SimulationAnswer(_Frozen):
    question_id: str
    text: str
    answered_at: datetime
    feedback: AnswerFeedback


class SimulationSummary(_Frozen):
    answered: int
    total: int
    average_score: int | None
    """`None` sans réponse : pas de moyenne sans donnée."""
    best_question_id: str | None = None
    weakest_question_id: str | None = None
    unanswered: tuple[str, ...] = ()


class FollowUpDraft(_Frozen):
    subject: str
    body: str
    suggested_follow_up_at: datetime


class InterviewData(_Frozen):
    stage: InterviewStage = InterviewStage.OTHER
    format: InterviewFormat = InterviewFormat.OTHER
    scheduled_at: datetime | None = None
    location: str | None = None
    interviewers: tuple[str, ...] = ()
    notes: str | None = None
    outcome: InterviewOutcome = InterviewOutcome.PENDING
    feedback_notes: str | None = None
