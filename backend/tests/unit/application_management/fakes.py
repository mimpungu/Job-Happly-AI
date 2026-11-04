"""Doubles en mémoire du CRM de candidatures : dépôt, lecteurs d'offres et de documents."""

import uuid
from datetime import UTC, datetime

from app.modules.application_management.domain.entities import (
    ApplicationAggregate,
    ContactInfo,
    DocumentVersionInfo,
    OfferSummary,
    TimelineEvent,
)
from app.modules.application_management.domain.enums import ApplicationStatus
from app.modules.application_management.domain.exceptions import DuplicateApplicationError
from app.modules.application_management.domain.ports import (
    ApplicationFilter,
    ApplicationRepositoryPort,
    DocumentVersionReaderPort,
    KanbanColumn,
    OfferReaderPort,
)

OWNER = uuid.UUID(int=1)
MAINTENANT = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)


class FakeOffers(OfferReaderPort):
    def __init__(self) -> None:
        self.offers: dict[uuid.UUID, OfferSummary] = {}

    def add(
        self, *, url: str = "https://careers.example.test/apply", **champs: object
    ) -> uuid.UUID:
        offre_id = uuid.uuid4()
        self.offers[offre_id] = OfferSummary(
            offer_id=offre_id,
            title=str(champs.get("title", "Développeur Python")),
            company_name=champs.get("company_name", "Acme"),  # type: ignore[arg-type]
            location="Paris",
            country_code="FR",
            application_url=url,
        )
        return offre_id

    async def get_summary(self, owner_id: uuid.UUID, offer_id: uuid.UUID) -> OfferSummary | None:
        return self.offers.get(offer_id)


class FakeDocuments(DocumentVersionReaderPort):
    def __init__(self) -> None:
        self.versions: dict[uuid.UUID, DocumentVersionInfo] = {}

    def add(
        self,
        kind: str,
        *,
        title: str = "Document",
        version: int = 1,
        passed: bool | None = True,
        score: int | None = 90,
    ) -> uuid.UUID:
        version_id = uuid.uuid4()
        self.versions[version_id] = DocumentVersionInfo(
            version_id=version_id,
            document_id=uuid.uuid4(),
            kind=kind,
            title=title,
            version=version,
            quality_passed=passed,
            quality_score=score,
        )
        return version_id

    async def get_info(
        self, owner_id: uuid.UUID, version_id: uuid.UUID
    ) -> DocumentVersionInfo | None:
        return self.versions.get(version_id)


class InMemoryApplicationRepository(ApplicationRepositoryPort):
    def __init__(self, offers: FakeOffers) -> None:
        self._offers = offers
        self.apps: dict[uuid.UUID, ApplicationAggregate] = {}
        self.events: list[TimelineEvent] = []
        self.contacts: list[ContactInfo] = []
        self.locked: list[uuid.UUID] = []

    def _fiche(self, app: ApplicationAggregate) -> ApplicationAggregate:
        app.events = [e for e in self.events if e.application_id == app.id]
        app.contacts = [c for c in self.contacts if c.application_id == app.id]
        app.offer = self._offers.offers.get(app.offer_id)
        return app

    async def get_by_id(
        self, owner_id: uuid.UUID, application_id: uuid.UUID, *, for_update: bool = False
    ) -> ApplicationAggregate | None:
        app = self.apps.get(application_id)
        if app is None or app.owner_id != owner_id:
            return None
        if for_update:
            self.locked.append(application_id)
        return self._fiche(app)

    async def get_by_offer_id(
        self, owner_id: uuid.UUID, offer_id: uuid.UUID
    ) -> ApplicationAggregate | None:
        for app in self.apps.values():
            if app.owner_id == owner_id and app.offer_id == offer_id:
                return self._fiche(app)
        return None

    async def create(
        self, owner_id: uuid.UUID, offer_id: uuid.UUID, status: ApplicationStatus
    ) -> ApplicationAggregate:
        if await self.get_by_offer_id(owner_id, offer_id) is not None:
            raise DuplicateApplicationError("doublon")
        app = ApplicationAggregate(
            id=uuid.uuid4(),
            owner_id=owner_id,
            offer_id=offer_id,
            status=status,
            created_at=MAINTENANT,
            updated_at=MAINTENANT,
        )
        self.apps[app.id] = app
        return app

    async def delete(self, owner_id: uuid.UUID, application_id: uuid.UUID) -> None:
        del self.apps[application_id]
        self.events = [e for e in self.events if e.application_id != application_id]
        self.contacts = [c for c in self.contacts if c.application_id != application_id]

    async def update_status(
        self,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        new_status: ApplicationStatus,
        applied_at: datetime | None = None,
        response_received_at: datetime | None = None,
    ) -> None:
        app = self.apps[application_id]
        app.status = new_status
        app.applied_at = applied_at or app.applied_at
        app.response_received_at = response_received_at or app.response_received_at

    async def update_follow_up(
        self, owner_id: uuid.UUID, application_id: uuid.UUID, follow_up_at: datetime | None
    ) -> None:
        self.apps[application_id].follow_up_at = follow_up_at

    async def attach_documents(
        self,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        cv_version_id: uuid.UUID | None = None,
        letter_version_id: uuid.UUID | None = None,
    ) -> None:
        app = self.apps[application_id]
        app.cv_version_id = cv_version_id or app.cv_version_id
        app.letter_version_id = letter_version_id or app.letter_version_id

    async def add_event(
        self, owner_id: uuid.UUID, application_id: uuid.UUID, event: TimelineEvent
    ) -> TimelineEvent:
        self.events.append(event)
        return event

    async def add_contact(
        self, owner_id: uuid.UUID, application_id: uuid.UUID, contact: ContactInfo
    ) -> ContactInfo:
        self.contacts.append(contact)
        return contact

    async def list_applications(
        self, owner_id: uuid.UUID, criteria: ApplicationFilter, limit: int, offset: int
    ) -> tuple[list[ApplicationAggregate], int]:
        apps = [a for a in self.apps.values() if a.owner_id == owner_id]
        return apps[offset : offset + limit], len(apps)

    async def list_for_kanban(
        self, owner_id: uuid.UUID, per_column_limit: int
    ) -> dict[ApplicationStatus, KanbanColumn]:
        colonnes: dict[ApplicationStatus, KanbanColumn] = {}
        for statut in ApplicationStatus:
            apps = [a for a in self.apps.values() if a.status is statut]
            colonnes[statut] = KanbanColumn(count=len(apps), items=apps[:per_column_limit])
        return colonnes

    async def list_for_stats(self, owner_id: uuid.UUID) -> list[ApplicationAggregate]:
        return [a for a in self.apps.values() if a.owner_id == owner_id]
