"""Fiches entretien : dates, retours, relance post-entretien (TASK-016-11 à 016-14)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from app.modules.interview_preparation.application.ports import (
    ApplicationTrackerPort,
    InterviewRecord,
    InterviewRepositoryPort,
    SourcesPort,
)
from app.modules.interview_preparation.domain.exceptions import (
    InterviewNotFoundError,
    InvalidInterviewDateError,
)
from app.modules.interview_preparation.domain.followup import (
    draft_follow_up,
    suggest_follow_up_date,
)
from app.modules.interview_preparation.domain.models import FollowUpDraft, InterviewData

_STAGES = {
    "hr_screen": "RH",
    "technical": "technique",
    "manager": "manager",
    "final": "final",
    "other": "",
}


def _require_aware(valeur: datetime | None) -> None:
    if valeur is not None and valeur.tzinfo is None:
        raise InvalidInterviewDateError(
            "La date de l'entretien doit comporter un fuseau horaire : "
            "« 9 h » ne veut rien dire sans lui."
        )


def _description(data: InterviewData, verbe: str) -> str:
    etape = _STAGES.get(data.stage.value, "")
    base = f"Entretien {etape}".strip() + f" {verbe}"
    return base + (f" ({data.location})" if data.location else "")


class InterviewService:
    def __init__(
        self,
        sources: SourcesPort,
        repository: InterviewRepositoryPort,
        tracker: ApplicationTrackerPort,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._sources = sources
        self._repository = repository
        self._tracker = tracker
        self._clock = clock

    async def create(
        self, *, owner_id: uuid.UUID, application_id: uuid.UUID, data: InterviewData
    ) -> InterviewRecord:
        _require_aware(data.scheduled_at)
        await self._sources.application_context(owner_id=owner_id, application_id=application_id)
        fiche = await self._repository.create_interview(
            owner_id=owner_id, application_id=application_id, data=data
        )
        if data.scheduled_at is not None:
            # La même date alimente l'historique de la candidature et l'agenda du tableau de bord.
            await self._tracker.record_interview(
                owner_id=owner_id,
                application_id=application_id,
                description=_description(data, "planifié"),
                when=data.scheduled_at,
            )
        return fiche

    async def update(
        self, *, owner_id: uuid.UUID, interview_id: uuid.UUID, data: InterviewData
    ) -> InterviewRecord:
        _require_aware(data.scheduled_at)
        actuelle = await self._load(owner_id, interview_id)
        fiche = await self._repository.update_interview(
            owner_id=owner_id,
            interview_id=interview_id,
            data=data,
            follow_up_draft=actuelle.follow_up_draft,
        )
        if data.scheduled_at is not None and data.scheduled_at != actuelle.data.scheduled_at:
            verbe = "reprogrammé" if actuelle.data.scheduled_at else "planifié"
            await self._tracker.record_interview(
                owner_id=owner_id,
                application_id=actuelle.application_id,
                description=_description(data, verbe),
                when=data.scheduled_at,
            )
        if data.outcome != actuelle.data.outcome:
            await self._tracker.record_interview(
                owner_id=owner_id,
                application_id=actuelle.application_id,
                description=f"{_description(data, 'terminé')} : issue « {data.outcome.value} »",
                when=None,
            )
        return fiche

    async def get(self, *, owner_id: uuid.UUID, interview_id: uuid.UUID) -> InterviewRecord:
        return await self._load(owner_id, interview_id)

    async def list(
        self,
        *,
        owner_id: uuid.UUID,
        application_id: uuid.UUID | None = None,
        upcoming_only: bool = False,
    ) -> list[InterviewRecord]:
        if application_id is not None:
            await self._sources.application_context(
                owner_id=owner_id, application_id=application_id
            )
        return await self._repository.list_interviews(
            owner_id=owner_id,
            application_id=application_id,
            scheduled_after=self._clock() if upcoming_only else None,
        )

    async def draft_follow_up(
        self, *, owner_id: uuid.UUID, interview_id: uuid.UUID, language: str = "fr"
    ) -> InterviewRecord:
        """Brouillon de remerciement, enregistré avec la fiche ; jamais envoyé par l'application."""
        fiche = await self._load(owner_id, interview_id)
        contexte = await self._sources.application_context(
            owner_id=owner_id, application_id=fiche.application_id
        )
        profil = await self._sources.validated_profile(owner_id=owner_id)
        identite = profil.identity
        nom = " ".join(p for p in (identite.first_name, identite.last_name) if p) or None
        brouillon = draft_follow_up(
            fiche.data, contexte.offer, candidate_name=nom, language=language, now=self._clock()
        )
        return await self._repository.update_interview(
            owner_id=owner_id,
            interview_id=interview_id,
            data=fiche.data,
            follow_up_draft=brouillon,
        )

    async def schedule_follow_up(
        self, *, owner_id: uuid.UUID, interview_id: uuid.UUID, follow_up_at: datetime | None
    ) -> datetime:
        """Planifie la relance dans le suivi de candidature (date proposée si non fournie)."""
        fiche = await self._load(owner_id, interview_id)
        _require_aware(follow_up_at)
        quand = follow_up_at or (
            fiche.follow_up_draft.suggested_follow_up_at
            if fiche.follow_up_draft
            else suggest_follow_up_date(fiche.data, now=self._clock())
        )
        await self._tracker.schedule_follow_up(
            owner_id=owner_id,
            application_id=fiche.application_id,
            follow_up_at=quand,
            notes="Relance après entretien",
        )
        return quand

    async def _load(self, owner_id: uuid.UUID, interview_id: uuid.UUID) -> InterviewRecord:
        trouvee = await self._repository.get_interview(owner_id=owner_id, interview_id=interview_id)
        if trouvee is None:
            raise InterviewNotFoundError("Fiche d'entretien introuvable.")
        return trouvee


__all__ = ["FollowUpDraft", "InterviewService"]
