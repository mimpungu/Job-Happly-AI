"""Tests unitaires des règles métier et du calcul des KPIs réels (TASK-014-03, 17, 22)."""

import uuid
from datetime import UTC, datetime

import pytest

from app.modules.application_management.domain.entities import (
    ApplicationAggregate,
    ApplicationDossier,
)
from app.modules.application_management.domain.enums import ApplicationStatus
from app.modules.application_management.domain.exceptions import (
    IncompleteDossierError,
    InvalidStatusTransitionError,
)
from app.modules.application_management.domain.rules import (
    calculate_response_rate,
    compute_application_stats,
    validate_status_transition,
    verify_dossier_readiness,
)


def test_transitions_de_statut_valides() -> None:
    # Transitions autorisées du cycle de vie
    validate_status_transition(ApplicationStatus.NEW_OFFER, ApplicationStatus.TO_APPLY)
    validate_status_transition(ApplicationStatus.TO_APPLY, ApplicationStatus.DOCUMENTS_TO_PREPARE)
    validate_status_transition(
        ApplicationStatus.DOCUMENTS_TO_PREPARE, ApplicationStatus.READY_TO_SEND
    )
    validate_status_transition(ApplicationStatus.READY_TO_SEND, ApplicationStatus.SENT)
    validate_status_transition(ApplicationStatus.SENT, ApplicationStatus.INTERVIEW)
    validate_status_transition(ApplicationStatus.INTERVIEW, ApplicationStatus.OFFER_RECEIVED)
    # Tout statut peut être abandonné
    validate_status_transition(ApplicationStatus.TO_APPLY, ApplicationStatus.ABANDONED)
    # Même statut (idempotent)
    validate_status_transition(ApplicationStatus.SENT, ApplicationStatus.SENT)


def test_transition_de_statut_invalide_leve_exception() -> None:
    with pytest.raises(InvalidStatusTransitionError):
        # Ne peut pas sauter directement de NEW_OFFER à OFFER_RECEIVED
        validate_status_transition(ApplicationStatus.NEW_OFFER, ApplicationStatus.OFFER_RECEIVED)

    with pytest.raises(InvalidStatusTransitionError):
        # Une offre reçue ne peut pas revenir directement à TO_APPLY
        validate_status_transition(ApplicationStatus.OFFER_RECEIVED, ApplicationStatus.TO_APPLY)


def test_verification_dossier_pret() -> None:
    dossier_complet = ApplicationDossier(
        application_id=uuid.uuid4(),
        offer_id=uuid.uuid4(),
        job_title="Développeur Python",
        company_name="Acme SAS",
        application_url="https://acme.test/apply",
        has_cv=True,
        cv_version_id=uuid.uuid4(),
        has_letter=True,
        letter_version_id=uuid.uuid4(),
        is_ready_to_send=True,
        missing_elements=(),
    )
    # Doit passer sans lever d'exception
    verify_dossier_readiness(dossier_complet)


def test_verification_dossier_incomplet_leve_exception() -> None:
    dossier_incomplet = ApplicationDossier(
        application_id=uuid.uuid4(),
        offer_id=uuid.uuid4(),
        job_title="Développeur Python",
        company_name="Acme SAS",
        application_url=None,
        has_cv=False,
        cv_version_id=None,
        has_letter=True,
        letter_version_id=uuid.uuid4(),
        is_ready_to_send=False,
        missing_elements=("CV manquant", "Lien externe manquant"),
    )
    with pytest.raises(IncompleteDossierError) as exc_info:
        verify_dossier_readiness(dossier_incomplet)
    assert "CV manquant" in str(exc_info.value)


def test_calcul_taux_de_reponse_zero_si_aucune_candidature_envoyee() -> None:
    assert calculate_response_rate(sent_count=0, responses_count=0) == 0.0
    assert calculate_response_rate(sent_count=0, responses_count=5) == 0.0


def test_calcul_taux_de_reponse_sur_donnees_reelles() -> None:
    # 4 envoyées, 2 réponses = 50.0 %
    assert calculate_response_rate(sent_count=4, responses_count=2) == 50.0
    # 3 envoyées, 1 réponse = 33.3 %
    assert calculate_response_rate(sent_count=3, responses_count=1) == 33.3


def test_consolidation_statistiques_reelles() -> None:
    owner = uuid.uuid4()
    now = datetime.now(UTC)

    app1 = ApplicationAggregate(
        id=uuid.uuid4(),
        owner_id=owner,
        offer_id=uuid.uuid4(),
        status=ApplicationStatus.SENT,
        created_at=now,
        updated_at=now,
        applied_at=now,
    )
    app2 = ApplicationAggregate(
        id=uuid.uuid4(),
        owner_id=owner,
        offer_id=uuid.uuid4(),
        status=ApplicationStatus.INTERVIEW,
        created_at=now,
        updated_at=now,
        applied_at=now,
        response_received_at=now,
    )
    app3 = ApplicationAggregate(
        id=uuid.uuid4(),
        owner_id=owner,
        offer_id=uuid.uuid4(),
        status=ApplicationStatus.NEW_OFFER,
        created_at=now,
        updated_at=now,
    )

    stats = compute_application_stats([app1, app2, app3])
    assert stats.total_applications == 3
    assert stats.sent_applications == 2
    assert stats.interviews_count == 1
    assert stats.response_rate == 50.0
    assert stats.active_applications == 3
