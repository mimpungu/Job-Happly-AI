"""Règles de la simulation : choix des questions et synthèse (TASK-016-07, 016-09)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.modules.interview_preparation.domain.enums import QuestionCategory
from app.modules.interview_preparation.domain.models import (
    Question,
    SimulationAnswer,
    SimulationSummary,
)

DEFAULT_QUESTION_COUNT = 6
MAX_QUESTION_COUNT = 15
_ORDRE = (QuestionCategory.HR, QuestionCategory.BEHAVIORAL, QuestionCategory.TECHNICAL)


def select_questions(questions: Sequence[Question], count: int) -> tuple[Question, ...]:
    """Alterne RH, comportemental et technique ; les questions « écart de compétence » en dernier.

    Déterministe : une même préparation donne la même simulation (pas de hasard, donc testable).
    """
    pioches = {
        cat: sorted((q for q in questions if q.category is cat), key=lambda q: q.skill_gap)
        for cat in _ORDRE
    }
    retenues: list[Question] = []
    while len(retenues) < min(count, len(questions)):
        avance = False
        for cat in _ORDRE:
            if pioches[cat] and len(retenues) < count:
                retenues.append(pioches[cat].pop(0))
                avance = True
        if not avance:
            break
    return tuple(retenues)


def summarize(
    questions: Sequence[Question], answers: Mapping[str, SimulationAnswer]
) -> SimulationSummary:
    repondues = [a for q in questions if (a := answers.get(q.id)) is not None]
    sans = tuple(q.id for q in questions if q.id not in answers)
    if not repondues:
        return SimulationSummary(
            answered=0, total=len(questions), average_score=None, unanswered=sans
        )
    moyenne = round(sum(a.feedback.score for a in repondues) / len(repondues))
    meilleure = max(repondues, key=lambda a: a.feedback.score)
    faible = min(repondues, key=lambda a: a.feedback.score)
    return SimulationSummary(
        answered=len(repondues),
        total=len(questions),
        average_score=moyenne,
        best_question_id=meilleure.question_id,
        weakest_question_id=faible.question_id if len(repondues) > 1 else None,
        unanswered=sans,
    )
