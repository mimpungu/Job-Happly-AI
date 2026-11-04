"""Simulation d'entretien : questions tirées de la préparation, retours, historique."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime

from app.modules.interview_preparation.application.ports import (
    CoachPort,
    PreparationRepositoryPort,
    SimulationRecord,
    SimulationRepositoryPort,
    SourcesPort,
)
from app.modules.interview_preparation.domain.enums import AssistMode, SimulationStatus
from app.modules.interview_preparation.domain.exceptions import (
    CoachUnavailableError,
    PreparationRequiredError,
    SimulationClosedError,
    SimulationNotFoundError,
    UnknownQuestionError,
)
from app.modules.interview_preparation.domain.feedback import evaluate_answer
from app.modules.interview_preparation.domain.models import (
    AnswerFeedback,
    Question,
    SimulationAnswer,
    SimulationSummary,
)
from app.modules.interview_preparation.domain.simulation import (
    DEFAULT_QUESTION_COUNT,
    MAX_QUESTION_COUNT,
    select_questions,
    summarize,
)
from app.modules.interview_preparation.domain.text import numbers


class SimulationService:
    def __init__(
        self,
        sources: SourcesPort,
        preparations: PreparationRepositoryPort,
        simulations: SimulationRepositoryPort,
        coach: CoachPort | None = None,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._sources = sources
        self._preparations = preparations
        self._simulations = simulations
        self._coach = coach
        self._clock = clock

    async def start(
        self,
        *,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        question_count: int = DEFAULT_QUESTION_COUNT,
    ) -> SimulationRecord:
        """Démarre une simulation : aucun appel IA ici, donc aucun coût au lancement."""
        await self._sources.application_context(owner_id=owner_id, application_id=application_id)
        preparation = await self._preparations.get_preparation(
            owner_id=owner_id, application_id=application_id
        )
        if preparation is None:
            raise PreparationRequiredError(
                "Préparez d'abord l'entretien : la simulation utilise ses questions."
            )
        nombre = max(1, min(question_count, MAX_QUESTION_COUNT))
        return await self._simulations.create_simulation(
            owner_id=owner_id,
            application_id=application_id,
            questions=select_questions(preparation.content.questions, nombre),
        )

    async def answer(
        self,
        *,
        owner_id: uuid.UUID,
        simulation_id: uuid.UUID,
        question_id: str,
        text: str,
        mode: AssistMode = AssistMode.NONE,
        language: str = "fr",
    ) -> SimulationAnswer:
        """Enregistre (ou remplace) la réponse à une question et renvoie le retour."""
        simulation = await self._load(owner_id, simulation_id, for_update=True)
        if simulation.status is SimulationStatus.COMPLETED:
            raise SimulationClosedError(
                "Cette simulation est terminée : elle est en lecture seule."
            )
        question = next((q for q in simulation.questions if q.id == question_id), None)
        if question is None:
            raise UnknownQuestionError("Cette question ne fait pas partie de la simulation.")

        contexte = await self._sources.application_context(
            owner_id=owner_id, application_id=simulation.application_id
        )
        profil = await self._sources.validated_profile(owner_id=owner_id)
        connus = numbers(profil.model_dump_json()) | numbers(
            f"{contexte.offer.title} {contexte.offer.description}"
        )
        retour = evaluate_answer(
            question,
            text,
            offer_terms=contexte.offer.required_skills,
            known_numbers=connus,
        )
        if mode is not AssistMode.NONE:
            retour = await self._with_ai(retour, owner_id, question, text, language, mode)
        reponse = SimulationAnswer(
            question_id=question_id, text=text.strip(), answered_at=self._clock(), feedback=retour
        )
        reponses = {**simulation.answers, question_id: reponse}
        await self._simulations.update_simulation(
            owner_id=owner_id, record=replace(simulation, answers=reponses)
        )
        return reponse

    async def _with_ai(
        self,
        retour: AnswerFeedback,
        owner_id: uuid.UUID,
        question: Question,
        text: str,
        language: str,
        mode: AssistMode,
    ) -> AnswerFeedback:
        if self._coach is None:
            return retour.model_copy(update={"ai_status": "unavailable"})
        try:
            commentaires = await self._coach.review_answer(
                owner_id=owner_id, question=question, answer=text, language=language, mode=mode
            )
        except CoachUnavailableError:
            return retour.model_copy(update={"ai_status": "unavailable"})
        return retour.model_copy(update={"ai_comments": commentaires, "ai_status": "applied"})

    async def complete(
        self, *, owner_id: uuid.UUID, simulation_id: uuid.UUID
    ) -> tuple[SimulationRecord, SimulationSummary]:
        simulation = await self._load(owner_id, simulation_id, for_update=True)
        if simulation.status is not SimulationStatus.COMPLETED:
            simulation = replace(
                simulation, status=SimulationStatus.COMPLETED, completed_at=self._clock()
            )
            await self._simulations.update_simulation(owner_id=owner_id, record=simulation)
        return simulation, summarize(simulation.questions, simulation.answers)

    async def get(
        self, *, owner_id: uuid.UUID, simulation_id: uuid.UUID
    ) -> tuple[SimulationRecord, SimulationSummary]:
        simulation = await self._load(owner_id, simulation_id)
        return simulation, summarize(simulation.questions, simulation.answers)

    async def list(
        self, *, owner_id: uuid.UUID, application_id: uuid.UUID
    ) -> list[tuple[SimulationRecord, SimulationSummary]]:
        await self._sources.application_context(owner_id=owner_id, application_id=application_id)
        trouvees = await self._simulations.list_simulations(
            owner_id=owner_id, application_id=application_id
        )
        return [(s, summarize(s.questions, s.answers)) for s in trouvees]

    async def delete(self, *, owner_id: uuid.UUID, simulation_id: uuid.UUID) -> None:
        """Suppression à la demande de l'utilisateur (RGPD)."""
        if not await self._simulations.delete_simulation(
            owner_id=owner_id, simulation_id=simulation_id
        ):
            raise SimulationNotFoundError("Simulation introuvable.")

    async def _load(
        self, owner_id: uuid.UUID, simulation_id: uuid.UUID, *, for_update: bool = False
    ) -> SimulationRecord:
        trouvee = await self._simulations.get_simulation(
            owner_id=owner_id, simulation_id=simulation_id, for_update=for_update
        )
        if trouvee is None:
            raise SimulationNotFoundError("Simulation introuvable.")
        return trouvee
