"""Tests unitaires du service applicatif ApplicationTrackingService (EPIC 014)."""

import uuid
from datetime import UTC, datetime

import pytest

from app.modules.application_management.application.service import (
    ApplicationTrackingService,
)
from app.modules.application_management.domain.entities import (
    ApplicationAggregate,
    ApplicationStats,
    ContactInfo,
    TimelineEvent,
)
from app.modules.application_management.domain.enums import ApplicationStatus
from app.modules.application_management.domain.exceptions import (
    DuplicateApplicationError,
    ExternalOfferLinkMissingError,
    InvalidStatusTransitionError,
)
from app.modules.application_management.domain.ports import ApplicationRepositoryPort
from app.modules.application_management.domain.rules import compute_application_stats


class InMemoryApplicationRepository(ApplicationRepositoryPort):
    def __init__(self) -> None:
        self.apps: dict[uuid.UUID, ApplicationAggregate] = {}
        self.events: list[TimelineEvent] = []
        self.contacts: list[ContactInfo] = []

    async def get_by_id(
        self, owner_id: uuid.UUID, application_id: uuid.UUID
    ) -> ApplicationAggregate | None:
        app = self.apps.get(application_id)
        if app and app.owner_id == owner_id:
            app.events = [e for e in self.events if e.application_id == app.id]
            app.contacts = [c for c in self.contacts if c.application_id == app.id]
            return app
        return None

    async def get_by_offer_id(
        self, owner_id: uuid.UUID, offer_id: uuid.UUID
    ) -> ApplicationAggregate | None:
        for app in self.apps.values():
            if app.owner_id == owner_id and app.offer_id == offer_id:
                app.events = [e for e in self.events if e.application_id == app.id]
                app.contacts = [c for c in self.contacts if c.application_id == app.id]
                return app
        return None

    async def create(
        self,
        owner_id: uuid.UUID,
        offer_id: uuid.UUID,
        status: ApplicationStatus = ApplicationStatus.NEW_OFFER,
    ) -> ApplicationAggregate:
        app = ApplicationAggregate(
            id=uuid.uuid4(),
            owner_id=owner_id,
            offer_id=offer_id,
            status=status,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self.apps[app.id] = app
        return app

    async def update_status(
        self,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        new_status: ApplicationStatus,
        applied_at: datetime | None = None,
        response_received_at: datetime | None = None,
    ) -> ApplicationAggregate:
        app = self.apps[application_id]
        app.status = new_status
        if applied_at:
            app.applied_at = applied_at
        if response_received_at:
            app.response_received_at = response_received_at
        app.updated_at = datetime.now(UTC)
        app.events = [e for e in self.events if e.application_id == app.id]
        return app

    async def update_follow_up(
        self,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        follow_up_at: datetime | None,
    ) -> ApplicationAggregate:
        app = self.apps[application_id]
        app.follow_up_at = follow_up_at
        app.updated_at = datetime.now(UTC)
        app.events = [e for e in self.events if e.application_id == app.id]
        return app

    async def attach_documents(
        self,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        cv_version_id: uuid.UUID | None = None,
        letter_version_id: uuid.UUID | None = None,
    ) -> ApplicationAggregate:
        app = self.apps[application_id]
        if cv_version_id:
            app.cv_version_id = cv_version_id
        if letter_version_id:
            app.letter_version_id = letter_version_id
        app.events = [e for e in self.events if e.application_id == app.id]
        return app

    async def add_event(
        self,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        event: TimelineEvent,
    ) -> TimelineEvent:
        self.events.append(event)
        return event

    async def add_contact(
        self,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        contact: ContactInfo,
    ) -> ContactInfo:
        self.contacts.append(contact)
        return contact

    async def list_applications(
        self,
        owner_id: uuid.UUID,
        status: ApplicationStatus | None = None,
        company_query: str | None = None,
        title_query: str | None = None,
        has_follow_up_due: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ApplicationAggregate], int]:
        items = [a for a in self.apps.values() if a.owner_id == owner_id]
        if status:
            items = [a for a in items if a.status == status]
        return items[offset : offset + limit], len(items)

    async def list_for_kanban(
        self,
        owner_id: uuid.UUID,
    ) -> dict[ApplicationStatus, list[ApplicationAggregate]]:
        res: dict[ApplicationStatus, list[ApplicationAggregate]] = {
            st: [] for st in ApplicationStatus
        }
        for a in self.apps.values():
            if a.owner_id == owner_id:
                res[a.status].append(a)
        return res

    async def get_stats(
        self,
        owner_id: uuid.UUID,
    ) -> ApplicationStats:
        items = [a for a in self.apps.values() if a.owner_id == owner_id]
        return compute_application_stats(items)


@pytest.fixture
def service() -> ApplicationTrackingService:
    repo = InMemoryApplicationRepository()
    return ApplicationTrackingService(repo)


async def test_creation_candidature_et_doublon_interdit(
    service: ApplicationTrackingService,
) -> None:
    owner = uuid.uuid4()
    offer = uuid.uuid4()

    app = await service.create_application(owner_id=owner, offer_id=offer)
    assert app.offer_id == offer
    assert app.status == ApplicationStatus.NEW_OFFER
    assert len(app.events) == 1

    with pytest.raises(DuplicateApplicationError):
        await service.create_application(owner_id=owner, offer_id=offer)


async def test_changement_statut_avec_historisation(
    service: ApplicationTrackingService,
) -> None:
    owner = uuid.uuid4()
    app = await service.create_application(owner_id=owner, offer_id=uuid.uuid4())

    updated = await service.change_status(
        owner_id=owner,
        application_id=app.id,
        target_status=ApplicationStatus.TO_APPLY,
        reason="Sélectionnée pour envoi",
    )
    assert updated.status == ApplicationStatus.TO_APPLY
    assert len(updated.events) == 2
    assert updated.events[-1].to_status == ApplicationStatus.TO_APPLY


async def test_changement_statut_interdit_leve_erreur(
    service: ApplicationTrackingService,
) -> None:
    owner = uuid.uuid4()
    app = await service.create_application(owner_id=owner, offer_id=uuid.uuid4())

    with pytest.raises(InvalidStatusTransitionError):
        await service.change_status(
            owner_id=owner,
            application_id=app.id,
            target_status=ApplicationStatus.OFFER_RECEIVED,
        )


async def test_confirmation_envoi_manuel(service: ApplicationTrackingService) -> None:
    owner = uuid.uuid4()
    app = await service.create_application(owner_id=owner, offer_id=uuid.uuid4())

    sent_app = await service.confirm_manual_submission(
        owner_id=owner,
        application_id=app.id,
        notes="Postulé via formulaire ATS de l'entreprise",
    )
    assert sent_app.status == ApplicationStatus.SENT
    assert sent_app.applied_at is not None
    assert sent_app.is_sent is True


async def test_ajout_note_et_contact(service: ApplicationTrackingService) -> None:
    owner = uuid.uuid4()
    app = await service.create_application(owner_id=owner, offer_id=uuid.uuid4())

    note = await service.add_note(
        owner_id=owner,
        application_id=app.id,
        note_body="Contacté par la RH sur LinkedIn",
    )
    assert note.body == "Contacté par la RH sur LinkedIn"

    contact = await service.add_contact(
        owner_id=owner,
        application_id=app.id,
        name="Jean Dupont",
        email="jean@rh.test",
        role="Responsable Recrutement",
    )
    assert contact.name == "Jean Dupont"

    detail = await service.get_application(owner_id=owner, application_id=app.id)
    assert len(detail.contacts) == 1
    assert any(e.body == "Contacté par la RH sur LinkedIn" for e in detail.events)


async def test_preparation_et_verification_dossier(
    service: ApplicationTrackingService,
) -> None:
    owner = uuid.uuid4()
    app = await service.create_application(owner_id=owner, offer_id=uuid.uuid4())

    # Dossier incomplet au départ
    dossier = await service.prepare_dossier(
        owner_id=owner,
        application_id=app.id,
        job_title="Lead Tech",
        company_name="Tesla",
        application_url=None,
    )
    assert dossier.is_ready_to_send is False
    assert len(dossier.missing_elements) == 3

    # Association des documents
    cv_id = uuid.uuid4()
    letter_id = uuid.uuid4()
    await service.attach_documents(
        owner_id=owner,
        application_id=app.id,
        cv_version_id=cv_id,
        letter_version_id=letter_id,
    )

    dossier_pret = await service.prepare_dossier(
        owner_id=owner,
        application_id=app.id,
        job_title="Lead Tech",
        company_name="Tesla",
        application_url="https://tesla.com/careers/lead-tech",
    )
    assert dossier_pret.is_ready_to_send is True
    assert dossier_pret.has_cv is True
    assert dossier_pret.has_letter is True
    assert len(dossier_pret.missing_elements) == 0


async def test_action_lien_externe_securisee(service: ApplicationTrackingService) -> None:
    owner = uuid.uuid4()
    app = await service.create_application(owner_id=owner, offer_id=uuid.uuid4())

    url = await service.get_application_url_action(
        owner_id=owner,
        application_id=app.id,
        offer_application_url="https://jobs.apple.com/fr-fr/details/123",
    )
    assert url == "https://jobs.apple.com/fr-fr/details/123"

    with pytest.raises(ExternalOfferLinkMissingError):
        await service.get_application_url_action(
            owner_id=owner,
            application_id=app.id,
            offer_application_url=None,
        )
