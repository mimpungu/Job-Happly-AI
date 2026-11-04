"""Persistance SQL de la préparation, des simulations et des fiches entretien."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.interview_preparation.application.ports import (
    InterviewRecord,
    PreparationRecord,
    SimulationRecord,
)
from app.modules.interview_preparation.domain.enums import SimulationStatus
from app.modules.interview_preparation.domain.exceptions import InterviewNotFoundError
from app.modules.interview_preparation.domain.models import (
    FollowUpDraft,
    InterviewData,
    PreparationContent,
    Question,
    SimulationAnswer,
)
from app.modules.interview_preparation.infrastructure.models import (
    InterviewModel,
    InterviewPreparationModel,
    InterviewSimulationModel,
)


def _preparation(m: InterviewPreparationModel) -> PreparationRecord:
    return PreparationRecord(
        id=m.id,
        application_id=m.application_id,
        content=PreparationContent.model_validate(m.content),
        meta=dict(m.meta),
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def _simulation(m: InterviewSimulationModel) -> SimulationRecord:
    return SimulationRecord(
        id=m.id,
        application_id=m.application_id,
        status=SimulationStatus(m.status),
        questions=tuple(Question.model_validate(q) for q in m.questions),
        answers={k: SimulationAnswer.model_validate(v) for k, v in m.answers.items()},
        created_at=m.created_at,
        completed_at=m.completed_at,
    )


def _interview(m: InterviewModel) -> InterviewRecord:
    return InterviewRecord(
        id=m.id,
        application_id=m.application_id,
        data=InterviewData(
            stage=m.stage,
            format=m.format,
            scheduled_at=m.scheduled_at,
            location=m.location,
            interviewers=tuple(m.interviewers),
            notes=m.notes,
            outcome=m.outcome,
            feedback_notes=m.feedback_notes,
        ),
        follow_up_draft=FollowUpDraft.model_validate(m.follow_up_draft)
        if m.follow_up_draft
        else None,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def _interview_values(data: InterviewData) -> dict[str, Any]:
    return {
        "stage": data.stage.value,
        "format": data.format.value,
        "scheduled_at": data.scheduled_at,
        "location": data.location,
        "interviewers": list(data.interviewers),
        "notes": data.notes,
        "outcome": data.outcome.value,
        "feedback_notes": data.feedback_notes,
    }


class SqlInterviewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------ préparation

    async def upsert_preparation(
        self,
        *,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        content: PreparationContent,
        meta: dict[str, Any],
    ) -> PreparationRecord:
        valeurs = {
            "owner_id": owner_id,
            "application_id": application_id,
            "content": content.model_dump(mode="json"),
            "meta": meta,
        }
        base = insert(InterviewPreparationModel).values(**valeurs)
        requete = base.on_conflict_do_update(
            index_elements=["owner_id", "application_id"],
            set_={
                "content": base.excluded.content,
                "meta": base.excluded.meta,
                "updated_at": func.now(),
            },
        ).returning(InterviewPreparationModel)
        ligne = (
            await self._session.execute(requete, execution_options={"populate_existing": True})
        ).scalar_one()
        return _preparation(ligne)

    async def get_preparation(
        self, *, owner_id: uuid.UUID, application_id: uuid.UUID
    ) -> PreparationRecord | None:
        ligne = await self._session.scalar(
            select(InterviewPreparationModel).where(
                InterviewPreparationModel.owner_id == owner_id,
                InterviewPreparationModel.application_id == application_id,
            )
        )
        return _preparation(ligne) if ligne else None

    # ------------------------------------------------------------ simulations

    async def create_simulation(
        self, *, owner_id: uuid.UUID, application_id: uuid.UUID, questions: Sequence[Question]
    ) -> SimulationRecord:
        modele = InterviewSimulationModel(
            owner_id=owner_id,
            application_id=application_id,
            questions=[q.model_dump(mode="json") for q in questions],
            answers={},
        )
        self._session.add(modele)
        await self._session.flush()
        await self._session.refresh(modele)
        return _simulation(modele)

    async def get_simulation(
        self, *, owner_id: uuid.UUID, simulation_id: uuid.UUID, for_update: bool = False
    ) -> SimulationRecord | None:
        requete = select(InterviewSimulationModel).where(
            InterviewSimulationModel.owner_id == owner_id,
            InterviewSimulationModel.id == simulation_id,
        )
        if for_update:
            requete = requete.with_for_update()
        ligne = await self._session.scalar(requete)
        return _simulation(ligne) if ligne else None

    async def list_simulations(
        self, *, owner_id: uuid.UUID, application_id: uuid.UUID
    ) -> list[SimulationRecord]:
        lignes = await self._session.scalars(
            select(InterviewSimulationModel)
            .where(
                InterviewSimulationModel.owner_id == owner_id,
                InterviewSimulationModel.application_id == application_id,
            )
            .order_by(InterviewSimulationModel.created_at.desc())
        )
        return [_simulation(m) for m in lignes]

    async def update_simulation(self, *, owner_id: uuid.UUID, record: SimulationRecord) -> None:
        ligne = await self._session.scalar(
            select(InterviewSimulationModel).where(
                InterviewSimulationModel.owner_id == owner_id,
                InterviewSimulationModel.id == record.id,
            )
        )
        if ligne is None:
            return
        ligne.status = record.status.value
        ligne.answers = {k: v.model_dump(mode="json") for k, v in record.answers.items()}
        ligne.completed_at = record.completed_at
        await self._session.flush()

    async def delete_simulation(self, *, owner_id: uuid.UUID, simulation_id: uuid.UUID) -> bool:
        resultat = await self._session.execute(
            delete(InterviewSimulationModel).where(
                InterviewSimulationModel.owner_id == owner_id,
                InterviewSimulationModel.id == simulation_id,
            )
        )
        return bool(resultat.rowcount)  # type: ignore[attr-defined]

    # ------------------------------------------------------------ entretiens

    async def create_interview(
        self, *, owner_id: uuid.UUID, application_id: uuid.UUID, data: InterviewData
    ) -> InterviewRecord:
        modele = InterviewModel(
            owner_id=owner_id, application_id=application_id, **_interview_values(data)
        )
        self._session.add(modele)
        await self._session.flush()
        await self._session.refresh(modele)
        return _interview(modele)

    async def get_interview(
        self, *, owner_id: uuid.UUID, interview_id: uuid.UUID
    ) -> InterviewRecord | None:
        ligne = await self._session.scalar(
            select(InterviewModel).where(
                InterviewModel.owner_id == owner_id, InterviewModel.id == interview_id
            )
        )
        return _interview(ligne) if ligne else None

    async def list_interviews(
        self,
        *,
        owner_id: uuid.UUID,
        application_id: uuid.UUID | None = None,
        scheduled_after: datetime | None = None,
    ) -> list[InterviewRecord]:
        requete = select(InterviewModel).where(InterviewModel.owner_id == owner_id)
        if application_id is not None:
            requete = requete.where(InterviewModel.application_id == application_id)
        if scheduled_after is not None:
            requete = requete.where(InterviewModel.scheduled_at >= scheduled_after)
        # Prochains en premier ; sans date, après les datés.
        requete = requete.order_by(
            InterviewModel.scheduled_at.asc().nulls_last(), InterviewModel.created_at.desc()
        )
        return [_interview(m) for m in await self._session.scalars(requete)]

    async def update_interview(
        self,
        *,
        owner_id: uuid.UUID,
        interview_id: uuid.UUID,
        data: InterviewData,
        follow_up_draft: FollowUpDraft | None,
    ) -> InterviewRecord:
        ligne = await self._session.scalar(
            select(InterviewModel)
            .where(InterviewModel.owner_id == owner_id, InterviewModel.id == interview_id)
            .with_for_update()
        )
        if ligne is None:
            raise InterviewNotFoundError("Fiche d'entretien introuvable.")
        for champ, valeur in _interview_values(data).items():
            setattr(ligne, champ, valeur)
        ligne.follow_up_draft = follow_up_draft.model_dump(mode="json") if follow_up_draft else None
        await self._session.flush()
        await self._session.refresh(ligne)
        return _interview(ligne)
