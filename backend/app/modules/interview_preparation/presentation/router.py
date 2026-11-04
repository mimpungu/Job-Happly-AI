"""Routes de préparation aux entretiens (EPIC 016). Routes minces : validation → service.

Tout appel IA est à la demande (`mode`), jamais automatique ; sans passerelle configurée la
préparation de base reste disponible. Rien n'est envoyé à un recruteur : les brouillons de
relance sont copiés par l'utilisateur.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from app.core.api.dependencies import SessionDep, get_owner_id
from app.modules.ai_management.application.gateway import AIGateway
from app.modules.ai_management.presentation.dependencies import Providers, get_gateway
from app.modules.interview_preparation.application.ports import InterviewRecord, SimulationRecord
from app.modules.interview_preparation.domain.models import (
    InterviewData,
    SimulationAnswer,
    SimulationSummary,
)
from app.modules.interview_preparation.domain.simulation import summarize
from app.modules.interview_preparation.infrastructure.composition import (
    build_interview_service,
    build_preparation_service,
    build_simulation_service,
)
from app.modules.interview_preparation.presentation.schemas import (
    AnswerRequest,
    FollowUpDraftRequest,
    GeneratePreparationRequest,
    InterviewRequest,
    InterviewResponse,
    PreparationResponse,
    ScheduledFollowUpResponse,
    ScheduleFollowUpRequest,
    SimulationResponse,
    StartSimulationRequest,
)

router = APIRouter(prefix="/api/v1/interview-preparation", tags=["interview-preparation"])
Owner = Annotated[uuid.UUID, Depends(get_owner_id)]


def _optional_gateway(request: Request, providers: Providers) -> AIGateway | None:
    """La passerelle IA ne sert qu'aux options IA : sans elle, la préparation reste possible."""
    try:
        return get_gateway(request, providers)
    except HTTPException:
        return None


OptionalGateway = Annotated[AIGateway | None, Depends(_optional_gateway)]


def _simulation(record: SimulationRecord, summary: SimulationSummary) -> SimulationResponse:
    ordre = {q.id: i for i, q in enumerate(record.questions)}
    reponses = sorted(record.answers.values(), key=lambda a: ordre.get(a.question_id, 0))
    return SimulationResponse(
        id=record.id,
        application_id=record.application_id,
        status=record.status,
        questions=list(record.questions),
        answers=reponses,
        summary=summary,
        created_at=record.created_at,
        completed_at=record.completed_at,
    )


def _interview(r: InterviewRecord) -> InterviewResponse:
    d = r.data
    return InterviewResponse(
        id=r.id,
        application_id=r.application_id,
        stage=d.stage,
        format=d.format,
        scheduled_at=d.scheduled_at,
        location=d.location,
        interviewers=list(d.interviewers),
        notes=d.notes,
        outcome=d.outcome,
        feedback_notes=d.feedback_notes,
        follow_up_draft=r.follow_up_draft,
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


def _data(body: InterviewRequest) -> InterviewData:
    return InterviewData(
        stage=body.stage,
        format=body.format,
        scheduled_at=body.scheduled_at,
        location=body.location or None,
        interviewers=tuple(body.interviewers),
        notes=body.notes or None,
        outcome=body.outcome,
        feedback_notes=body.feedback_notes or None,
    )


# ------------------------------------------------------------------ préparation


@router.post(
    "/applications/{application_id}/preparation",
    response_model=PreparationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_preparation(
    application_id: uuid.UUID,
    body: GeneratePreparationRequest,
    session: SessionDep,
    owner_id: Owner,
    gateway: OptionalGateway,
) -> PreparationResponse:
    """Prépare l'entretien depuis le profil validé et l'offre ; remplace la précédente."""
    p = await build_preparation_service(session, gateway).generate(
        owner_id=owner_id, application_id=application_id, language=body.language, mode=body.mode
    )
    return PreparationResponse(**p.__dict__)


@router.get("/applications/{application_id}/preparation", response_model=PreparationResponse)
async def get_preparation(
    application_id: uuid.UUID, session: SessionDep, owner_id: Owner
) -> PreparationResponse:
    p = await build_preparation_service(session).get(
        owner_id=owner_id, application_id=application_id
    )
    return PreparationResponse(**p.__dict__)


# ------------------------------------------------------------------ simulations


@router.post(
    "/applications/{application_id}/simulations",
    response_model=SimulationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_simulation(
    application_id: uuid.UUID, body: StartSimulationRequest, session: SessionDep, owner_id: Owner
) -> SimulationResponse:
    s = await build_simulation_service(session).start(
        owner_id=owner_id, application_id=application_id, question_count=body.question_count
    )
    return _simulation(s, summarize(s.questions, s.answers))


@router.get("/applications/{application_id}/simulations", response_model=list[SimulationResponse])
async def list_simulations(
    application_id: uuid.UUID, session: SessionDep, owner_id: Owner
) -> list[SimulationResponse]:
    trouvees = await build_simulation_service(session).list(
        owner_id=owner_id, application_id=application_id
    )
    return [_simulation(s, resume) for s, resume in trouvees]


@router.get("/simulations/{simulation_id}", response_model=SimulationResponse)
async def get_simulation(
    simulation_id: uuid.UUID, session: SessionDep, owner_id: Owner
) -> SimulationResponse:
    s, resume = await build_simulation_service(session).get(
        owner_id=owner_id, simulation_id=simulation_id
    )
    return _simulation(s, resume)


@router.put("/simulations/{simulation_id}/answers/{question_id}", response_model=SimulationAnswer)
async def answer_question(
    simulation_id: uuid.UUID,
    question_id: str,
    body: AnswerRequest,
    session: SessionDep,
    owner_id: Owner,
    gateway: OptionalGateway,
) -> SimulationAnswer:
    """Enregistre la réponse et renvoie le retour ; l'IA n'intervient que si `mode` le demande."""
    return await build_simulation_service(session, gateway).answer(
        owner_id=owner_id,
        simulation_id=simulation_id,
        question_id=question_id,
        text=body.text,
        mode=body.mode,
        language=body.language,
    )


@router.post("/simulations/{simulation_id}/complete", response_model=SimulationResponse)
async def complete_simulation(
    simulation_id: uuid.UUID, session: SessionDep, owner_id: Owner
) -> SimulationResponse:
    s, resume = await build_simulation_service(session).complete(
        owner_id=owner_id, simulation_id=simulation_id
    )
    return _simulation(s, resume)


@router.delete("/simulations/{simulation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_simulation(
    simulation_id: uuid.UUID, session: SessionDep, owner_id: Owner
) -> Response:
    await build_simulation_service(session).delete(owner_id=owner_id, simulation_id=simulation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------------ entretiens


@router.post(
    "/applications/{application_id}/interviews",
    response_model=InterviewResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_interview(
    application_id: uuid.UUID, body: InterviewRequest, session: SessionDep, owner_id: Owner
) -> InterviewResponse:
    r = await build_interview_service(session).create(
        owner_id=owner_id, application_id=application_id, data=_data(body)
    )
    return _interview(r)


@router.get("/interviews", response_model=list[InterviewResponse])
async def list_interviews(
    session: SessionDep,
    owner_id: Owner,
    application_id: Annotated[uuid.UUID | None, Query()] = None,
    upcoming: Annotated[bool, Query()] = False,
) -> list[InterviewResponse]:
    trouves = await build_interview_service(session).list(
        owner_id=owner_id, application_id=application_id, upcoming_only=upcoming
    )
    return [_interview(r) for r in trouves]


@router.get("/interviews/{interview_id}", response_model=InterviewResponse)
async def get_interview(
    interview_id: uuid.UUID, session: SessionDep, owner_id: Owner
) -> InterviewResponse:
    return _interview(
        await build_interview_service(session).get(owner_id=owner_id, interview_id=interview_id)
    )


@router.put("/interviews/{interview_id}", response_model=InterviewResponse)
async def update_interview(
    interview_id: uuid.UUID, body: InterviewRequest, session: SessionDep, owner_id: Owner
) -> InterviewResponse:
    return _interview(
        await build_interview_service(session).update(
            owner_id=owner_id, interview_id=interview_id, data=_data(body)
        )
    )


@router.post("/interviews/{interview_id}/follow-up-draft", response_model=InterviewResponse)
async def draft_follow_up(
    interview_id: uuid.UUID, body: FollowUpDraftRequest, session: SessionDep, owner_id: Owner
) -> InterviewResponse:
    """Brouillon de remerciement ; copié par l'utilisateur, jamais envoyé par l'application."""
    return _interview(
        await build_interview_service(session).draft_follow_up(
            owner_id=owner_id, interview_id=interview_id, language=body.language
        )
    )


@router.post("/interviews/{interview_id}/follow-up", response_model=ScheduledFollowUpResponse)
async def schedule_follow_up(
    interview_id: uuid.UUID, body: ScheduleFollowUpRequest, session: SessionDep, owner_id: Owner
) -> ScheduledFollowUpResponse:
    quand = await build_interview_service(session).schedule_follow_up(
        owner_id=owner_id, interview_id=interview_id, follow_up_at=body.follow_up_at
    )
    return ScheduledFollowUpResponse(follow_up_at=quand)
