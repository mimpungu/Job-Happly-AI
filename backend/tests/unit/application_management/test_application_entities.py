"""Tests unitaires des entités du domaine application_management (TASK-014-01)."""

import uuid
from datetime import UTC, datetime

from app.modules.application_management.domain.entities import (
    ApplicationAggregate,
    ContactInfo,
    TimelineEvent,
)
from app.modules.application_management.domain.enums import ApplicationStatus, EventKind


def test_application_aggregate_statut_initial_non_envoye() -> None:
    app = ApplicationAggregate(
        id=uuid.uuid4(),
        owner_id=uuid.uuid4(),
        offer_id=uuid.uuid4(),
        status=ApplicationStatus.NEW_OFFER,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    assert app.is_sent is False
    assert app.has_response is False
    assert len(app.contacts) == 0
    assert len(app.events) == 0


def test_application_aggregate_statut_envoye_et_reponse() -> None:
    app_sent = ApplicationAggregate(
        id=uuid.uuid4(),
        owner_id=uuid.uuid4(),
        offer_id=uuid.uuid4(),
        status=ApplicationStatus.SENT,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        applied_at=datetime.now(UTC),
    )
    assert app_sent.is_sent is True
    assert app_sent.has_response is False

    app_interview = ApplicationAggregate(
        id=uuid.uuid4(),
        owner_id=uuid.uuid4(),
        offer_id=uuid.uuid4(),
        status=ApplicationStatus.INTERVIEW,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        applied_at=datetime.now(UTC),
        response_received_at=datetime.now(UTC),
    )
    assert app_interview.is_sent is True
    assert app_interview.has_response is True


def test_objets_valeurs_contacts_et_evenements() -> None:
    app_id = uuid.uuid4()
    contact = ContactInfo(
        id=uuid.uuid4(),
        application_id=app_id,
        name="Alice Martin",
        email="alice@tech.test",
        phone="0612345678",
        role="Lead Recruteur",
    )
    assert contact.name == "Alice Martin"
    assert contact.role == "Lead Recruteur"

    event = TimelineEvent(
        id=uuid.uuid4(),
        application_id=app_id,
        kind=EventKind.STATUS_CHANGE,
        occurred_at=datetime.now(UTC),
        from_status=ApplicationStatus.NEW_OFFER,
        to_status=ApplicationStatus.TO_APPLY,
        body="Offre marquée pour candidature",
    )
    assert event.kind == EventKind.STATUS_CHANGE
    assert event.to_status == ApplicationStatus.TO_APPLY

