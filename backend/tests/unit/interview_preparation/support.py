"""Jeux de données et doublures partagés par les tests de la préparation aux entretiens."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from app.modules.candidate_profile.domain.profile import (
    DocDate,
    ExperienceDoc,
    Identity,
    ProfileDocument,
    SkillDoc,
)
from app.modules.interview_preparation.application.ports import (
    ApplicationContext,
    InterviewRecord,
    PreparationRecord,
    SimulationRecord,
)
from app.modules.interview_preparation.domain.enums import (
    AssistMode,
    SimulationStatus,
)
from app.modules.interview_preparation.domain.exceptions import CoachUnavailableError
from app.modules.interview_preparation.domain.models import (
    FollowUpDraft,
    InterviewData,
    OfferFacts,
    PreparationContent,
    Question,
)

NOW = datetime(2026, 11, 4, 10, 0, tzinfo=UTC)
OWNER = uuid.uuid4()
APPLICATION = uuid.uuid4()


def profil() -> ProfileDocument:
    return ProfileDocument(
        identity=Identity(first_name="Camille", last_name="Dubois", headline="Développeuse Python"),
        experiences=(
            ExperienceDoc(
                title="Ingénieure Backend",
                company="OpenCorp",
                start=DocDate(year=2021),
                is_current=True,
                description="Services de données.",
                achievements=("Migration de 12 services vers FastAPI", "Revue de code"),
            ),
            ExperienceDoc(
                title="Développeuse",
                company="Vieille Boîte",
                start=DocDate(year=2018),
                end=DocDate(year=2021),
                achievements=("Maintenance d'applications Java",),
            ),
        ),
        skills=(SkillDoc(name="Python"), SkillDoc(name="FastAPI"), SkillDoc(name="Java")),
    )


def offre(**kw: Any) -> OfferFacts:
    base: dict[str, Any] = {
        "title": "Ingénieur Backend",
        "company": "Acme",
        "description": "Nous cherchons un profil backend, équipe de 8 personnes.",
        "required_skills": ("Python", "FastAPI", "Kubernetes"),
    }
    return OfferFacts(**{**base, **kw})


class FakeSources:
    def __init__(self, cv: uuid.UUID | None = None) -> None:
        self.cv = cv
        self.offer = offre()

    async def validated_profile(self, *, owner_id: uuid.UUID) -> ProfileDocument:
        return profil()

    async def application_context(
        self, *, owner_id: uuid.UUID, application_id: uuid.UUID
    ) -> ApplicationContext:
        return ApplicationContext(application_id, self.offer, "interview", self.cv)


class FakeRepository:
    """Implémente les trois ports de persistance en mémoire."""

    def __init__(self) -> None:
        self.preparations: dict[uuid.UUID, PreparationRecord] = {}
        self.simulations: dict[uuid.UUID, SimulationRecord] = {}
        self.interviews: dict[uuid.UUID, InterviewRecord] = {}

    async def upsert_preparation(
        self,
        *,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        content: PreparationContent,
        meta: dict[str, Any],
    ) -> PreparationRecord:
        rec = PreparationRecord(uuid.uuid4(), application_id, content, meta, NOW, NOW)
        self.preparations[application_id] = rec
        return rec

    async def get_preparation(
        self, *, owner_id: uuid.UUID, application_id: uuid.UUID
    ) -> PreparationRecord | None:
        return self.preparations.get(application_id)

    async def create_simulation(
        self, *, owner_id: uuid.UUID, application_id: uuid.UUID, questions: Sequence[Question]
    ) -> SimulationRecord:
        rec = SimulationRecord(
            uuid.uuid4(), application_id, SimulationStatus.IN_PROGRESS, tuple(questions), {}, NOW
        )
        self.simulations[rec.id] = rec
        return rec

    async def get_simulation(
        self, *, owner_id: uuid.UUID, simulation_id: uuid.UUID, for_update: bool = False
    ) -> SimulationRecord | None:
        return self.simulations.get(simulation_id)

    async def list_simulations(
        self, *, owner_id: uuid.UUID, application_id: uuid.UUID
    ) -> list[SimulationRecord]:
        return [s for s in self.simulations.values() if s.application_id == application_id]

    async def update_simulation(self, *, owner_id: uuid.UUID, record: SimulationRecord) -> None:
        self.simulations[record.id] = record

    async def delete_simulation(self, *, owner_id: uuid.UUID, simulation_id: uuid.UUID) -> bool:
        return self.simulations.pop(simulation_id, None) is not None

    async def create_interview(
        self, *, owner_id: uuid.UUID, application_id: uuid.UUID, data: InterviewData
    ) -> InterviewRecord:
        rec = InterviewRecord(uuid.uuid4(), application_id, data, None, NOW, NOW)
        self.interviews[rec.id] = rec
        return rec

    async def get_interview(
        self, *, owner_id: uuid.UUID, interview_id: uuid.UUID
    ) -> InterviewRecord | None:
        return self.interviews.get(interview_id)

    async def list_interviews(
        self,
        *,
        owner_id: uuid.UUID,
        application_id: uuid.UUID | None = None,
        scheduled_after: datetime | None = None,
    ) -> list[InterviewRecord]:
        trouves = list(self.interviews.values())
        if application_id:
            trouves = [i for i in trouves if i.application_id == application_id]
        if scheduled_after:
            trouves = [
                i for i in trouves if i.data.scheduled_at and i.data.scheduled_at >= scheduled_after
            ]
        return trouves

    async def update_interview(
        self,
        *,
        owner_id: uuid.UUID,
        interview_id: uuid.UUID,
        data: InterviewData,
        follow_up_draft: FollowUpDraft | None,
    ) -> InterviewRecord:
        ancien = self.interviews[interview_id]
        rec = InterviewRecord(
            interview_id, ancien.application_id, data, follow_up_draft, ancien.created_at, NOW
        )
        self.interviews[interview_id] = rec
        return rec


class FakeTracker:
    def __init__(self) -> None:
        self.events: list[tuple[str, datetime | None]] = []
        self.follow_ups: list[datetime] = []

    async def record_interview(
        self,
        *,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        description: str,
        when: datetime | None,
    ) -> None:
        self.events.append((description, when))

    async def schedule_follow_up(
        self,
        *,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        follow_up_at: datetime,
        notes: str | None,
    ) -> None:
        self.follow_ups.append(follow_up_at)


class FakeCoach:
    def __init__(
        self,
        questions: list[Question] | None = None,
        comments: tuple[str, ...] = ("Ajoutez un exemple.",),
        *,
        fail: bool = False,
    ) -> None:
        self.questions = questions or []
        self.comments = comments
        self.fail = fail
        self.calls: list[AssistMode] = []

    async def extra_questions(
        self, *, owner_id: uuid.UUID, offer: OfferFacts, language: str, mode: AssistMode
    ) -> list[Question]:
        self.calls.append(mode)
        if self.fail:
            raise CoachUnavailableError("Plafond atteint.")
        return self.questions

    async def review_answer(
        self,
        *,
        owner_id: uuid.UUID,
        question: Question,
        answer: str,
        language: str,
        mode: AssistMode,
    ) -> tuple[str, ...]:
        self.calls.append(mode)
        if self.fail:
            raise CoachUnavailableError("Plafond atteint.")
        return self.comments
