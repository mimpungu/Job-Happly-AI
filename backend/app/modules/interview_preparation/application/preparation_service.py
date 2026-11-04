"""Génération de la préparation d'entretien, toujours à la demande (TASK-016-01 à 016-06)."""

from __future__ import annotations

import uuid
from typing import Any

from app.modules.interview_preparation.application.ports import (
    CoachPort,
    PreparationRecord,
    PreparationRepositoryPort,
    SourcesPort,
)
from app.modules.interview_preparation.domain.enums import AssistMode, QuestionCategory
from app.modules.interview_preparation.domain.exceptions import (
    CoachUnavailableError,
    PreparationNotFoundError,
)
from app.modules.interview_preparation.domain.generator import build_preparation
from app.modules.interview_preparation.domain.models import PreparationContent, Question
from app.modules.interview_preparation.domain.text import norm

_MAX_AI_QUESTIONS = 5


class PreparationService:
    def __init__(
        self,
        sources: SourcesPort,
        repository: PreparationRepositoryPort,
        coach: CoachPort | None = None,
    ) -> None:
        self._sources = sources
        self._repository = repository
        self._coach = coach

    async def generate(
        self,
        *,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        language: str = "fr",
        mode: AssistMode = AssistMode.NONE,
    ) -> PreparationRecord:
        """Prépare l'entretien depuis le profil validé et l'offre ; remplace la préparation
        précédente (les simulations déjà faites gardent leurs propres questions)."""
        contexte = await self._sources.application_context(
            owner_id=owner_id, application_id=application_id
        )
        profil = await self._sources.validated_profile(owner_id=owner_id)
        contenu = build_preparation(profil, contexte.offer, language=language)
        meta: dict[str, Any] = {
            "language": language,
            "cv_version_id": str(contexte.cv_version_id) if contexte.cv_version_id else None,
            "ai": {"requested": mode.value, "status": "not_requested"},
        }
        if contexte.cv_version_id is None:
            contenu = contenu.model_copy(
                update={
                    "warnings": (
                        *contenu.warnings,
                        "Aucun CV n'est associé à cette candidature : la préparation s'appuie "
                        "sur votre profil validé.",
                    )
                }
            )
        if mode is not AssistMode.NONE:
            contenu, meta["ai"] = await self._enrich(
                owner_id, contenu, contexte.offer, language, mode
            )
        return await self._repository.upsert_preparation(
            owner_id=owner_id, application_id=application_id, content=contenu, meta=meta
        )

    async def _enrich(
        self,
        owner_id: uuid.UUID,
        contenu: PreparationContent,
        offer: Any,
        language: str,
        mode: AssistMode,
    ) -> tuple[PreparationContent, dict[str, Any]]:
        """Questions supplémentaires par IA ; un échec garde la préparation de base, et le dit."""
        if self._coach is None:
            return contenu, {
                "requested": mode.value,
                "status": "unavailable",
                "reason": "IA non disponible sur ce serveur.",
            }
        try:
            proposees = await self._coach.extra_questions(
                owner_id=owner_id, offer=offer, language=language, mode=mode
            )
        except CoachUnavailableError as erreur:
            return contenu, {
                "requested": mode.value,
                "status": "unavailable",
                "reason": str(erreur),
            }
        connues = {norm(q.text) for q in contenu.questions}
        nouvelles: list[Question] = []
        for question in proposees:
            if norm(question.text) in connues or len(nouvelles) >= _MAX_AI_QUESTIONS:
                continue
            connues.add(norm(question.text))
            nouvelles.append(question.model_copy(update={"id": f"ai-{len(nouvelles) + 1}"}))
        enrichi = contenu.model_copy(update={"questions": (*contenu.questions, *nouvelles)})
        return enrichi, {"requested": mode.value, "status": "applied", "added": len(nouvelles)}

    async def get(self, *, owner_id: uuid.UUID, application_id: uuid.UUID) -> PreparationRecord:
        trouvee = await self._repository.get_preparation(
            owner_id=owner_id, application_id=application_id
        )
        if trouvee is None:
            raise PreparationNotFoundError(
                "Aucune préparation pour cette candidature : lancez-la d'abord."
            )
        return trouvee


__all__ = ["PreparationService", "QuestionCategory"]
