"""Adaptateur IA du coach : données transmises, restriction locale, validation des sorties."""

import json
import uuid
from decimal import Decimal
from typing import Any

import pytest

from app.modules.ai_management.application.gateway import AIResult
from app.modules.ai_management.domain.errors import BudgetExceededError
from app.modules.ai_management.domain.models import ProviderKind
from app.modules.interview_preparation.domain.enums import (
    AssistMode,
    QuestionCategory,
    QuestionSource,
)
from app.modules.interview_preparation.domain.exceptions import CoachUnavailableError
from app.modules.interview_preparation.domain.models import Question
from app.modules.interview_preparation.infrastructure.ai_coach import (
    GatewayInterviewCoach,
    _valider_commentaires,
    _valider_questions,
)
from tests.unit.interview_preparation.support import OWNER, offre


class FakeGateway:
    def __init__(self, value: Any = None, *, erreur: Exception | None = None) -> None:
        self.value = value
        self.erreur = erreur
        self.requetes: list[Any] = []

    async def run(self, *, owner_id: uuid.UUID, request: Any, validate: Any) -> Any:
        self.requetes.append(request)
        if self.erreur:
            raise self.erreur
        return AIResult(validate(self.value), "p", "m", False, Decimal(0), 1, 1)


QUESTION = Question(
    id="technical-1",
    category=QuestionCategory.TECHNICAL,
    text="Décrivez un cas avec Python.",
    rationale="x",
)


async def test_questions_ne_transmettent_que_l_offre() -> None:
    gateway = FakeGateway(
        {
            "questions": [
                {
                    "category": "technical",
                    "text": "Comment tester une API FastAPI ?",
                    "rationale": "Stack",
                },
                {
                    "category": "inconnue",
                    "text": "Comment déployer sur Kubernetes ?",
                    "rationale": "Infra",
                },
                {"category": "hr", "text": "court", "rationale": "ignorée : trop courte"},
            ]
        }
    )

    questions = await GatewayInterviewCoach(gateway).extra_questions(  # type: ignore[arg-type]
        owner_id=OWNER, offer=offre(), language="fr", mode=AssistMode.AI
    )

    requete = gateway.requetes[0]
    assert requete.contains_personal_data is False
    assert requete.allowed_kinds is None
    envoye = json.loads(requete.content)
    assert set(envoye) == {"language", "title", "company", "required_skills", "description"}
    assert [q.category for q in questions] == [
        QuestionCategory.TECHNICAL,
        QuestionCategory.TECHNICAL,
    ]
    assert all(q.source is QuestionSource.AI for q in questions)


async def test_commentaire_de_reponse_est_une_donnee_personnelle_et_local_restreint() -> None:
    gateway = FakeGateway({"comments": ["Ajoutez un chiffre réel.", "  ", 3]})

    commentaires = await GatewayInterviewCoach(gateway).review_answer(  # type: ignore[arg-type]
        owner_id=OWNER,
        question=QUESTION,
        answer="Ma réponse.",
        language="fr",
        mode=AssistMode.LOCAL,
    )

    requete = gateway.requetes[0]
    assert requete.contains_personal_data is True
    assert requete.allowed_kinds == frozenset({ProviderKind.LOCAL})
    assert commentaires == ("Ajoutez un chiffre réel.",)


async def test_erreur_ia_devient_indisponibilite_du_coach() -> None:
    gateway = FakeGateway(erreur=BudgetExceededError("Plafond atteint."))

    with pytest.raises(CoachUnavailableError, match="Plafond"):
        await GatewayInterviewCoach(gateway).review_answer(  # type: ignore[arg-type]
            owner_id=OWNER, question=QUESTION, answer="x", language="fr", mode=AssistMode.AI
        )


@pytest.mark.parametrize(
    "brut",
    [{}, {"questions": "x"}, {"questions": [1]}, {"questions": [{"text": 3, "rationale": "a"}]}],
)
def test_questions_mal_formees_rejetees(brut: Any) -> None:
    with pytest.raises(ValueError):
        _valider_questions(brut)


@pytest.mark.parametrize("brut", [{}, {"comments": "x"}, {"comments": []}, {"comments": [""]}])
def test_commentaires_mal_formes_rejetes(brut: Any) -> None:
    with pytest.raises(ValueError):
        _valider_commentaires(brut)
