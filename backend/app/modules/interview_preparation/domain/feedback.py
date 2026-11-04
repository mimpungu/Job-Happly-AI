"""Retours de simulation niveau 0 (TASK-016-09) : critères objectifs, aucun avis inventé.

Le score reflète des points vérifiables (longueur, structure Situation-Action-Résultat,
exemple concret, termes de l'offre, chiffres traçables), pas un jugement de personnalité.
"""

from __future__ import annotations

import re

from app.modules.interview_preparation.domain.enums import QuestionCategory
from app.modules.interview_preparation.domain.models import AnswerFeedback, Question
from app.modules.interview_preparation.domain.text import mentions, norm, numbers, word_count

_MIN_WORDS = 30
_MAX_WORDS = 250
_SITUATION = re.compile(
    r"\b(contexte|situation|lorsque|quand|dans mon poste|chez|when|at my|context)\b"
)
_ACTION = re.compile(
    r"\b(j'ai|j ai|mis en place|realise|developpe|i built|i led|i did|i implemented|i designed)\b"
)
_RESULT = re.compile(
    r"\b(resultat|grace a|ce qui a|permis|reduit|augmente|amelior|as a result|which led"
    r"|reduced|increased|improved)\b"
)
_POINTS = {"longueur": 25, "structure": 30, "concret": 20, "offre": 15, "chiffres": 10}


def evaluate_answer(
    question: Question,
    answer: str,
    *,
    offer_terms: tuple[str, ...],
    known_numbers: set[str],
) -> AnswerFeedback:
    """`known_numbers` : chiffres du profil et de l'offre ; les autres sont à vérifier."""
    texte = answer.strip()
    mots = word_count(texte)
    normalise = norm(texte)
    forces: list[str] = []
    pistes: list[str] = []
    score = 0

    if _MIN_WORDS <= mots <= _MAX_WORDS:
        score += _POINTS["longueur"]
        forces.append(f"Longueur adaptée ({mots} mots).")
    elif mots < _MIN_WORDS:
        score += _POINTS["longueur"] * mots // _MIN_WORDS
        pistes.append(f"Réponse très courte ({mots} mots) : développez avec un exemple précis.")
    else:
        pistes.append(f"Réponse longue ({mots} mots) : visez moins de {_MAX_WORDS} mots.")

    structure = (
        bool(_SITUATION.search(normalise)),
        bool(_ACTION.search(normalise)),
        bool(_RESULT.search(normalise)),
    )
    score += _POINTS["structure"] * sum(structure) // 3
    manques = [
        nom
        for nom, present in zip(
            ("le contexte", "vos actions", "le résultat"), structure, strict=True
        )
        if not present
    ]
    if not manques:
        forces.append("La réponse suit la structure Situation, Action, Résultat.")
    elif question.category is not QuestionCategory.HR or len(manques) == 3:
        pistes.append(
            "Structurez avec Situation, Action, Résultat : il manque " + ", ".join(manques) + "."
        )

    chiffres = numbers(texte)
    inconnus = tuple(sorted(chiffres - known_numbers))
    if chiffres:
        score += _POINTS["concret"]
        forces.append("Vous appuyez la réponse sur des éléments chiffrés.")
    else:
        pistes.append("Ajoutez un élément concret (chiffre ou fait observable) si vous en avez un.")
    if inconnus:
        pistes.append(
            "Ces chiffres ne figurent ni dans votre profil ni dans l'offre : "
            + ", ".join(inconnus)
            + ". Vérifiez qu'ils sont exacts avant de les citer."
        )
    else:
        score += _POINTS["chiffres"]

    cibles = [question.skill] if question.skill else list(offer_terms)
    cites = [t for t in cibles if t and mentions(texte, t)]
    if cites:
        score += _POINTS["offre"]
        forces.append("Vous citez des termes de l'offre : " + ", ".join(cites[:4]) + ".")
    elif cibles:
        pistes.append("Reliez votre réponse aux attentes de l'offre (compétences demandées).")
    else:
        score += _POINTS["offre"]

    return AnswerFeedback(
        score=min(100, score),
        strengths=tuple(forces),
        improvements=tuple(pistes),
        unverified_numbers=inconnus,
    )
