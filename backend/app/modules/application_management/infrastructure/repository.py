"""Implémentation SQLAlchemy des ports de persistance pour les candidatures et le dashboard."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import desc, func, select

from app.modules.ai_management.infrastructure.models import AIBudgetModel, AIUsageModel
from app.modules.application_management.domain.entities import (
    ApplicationAggregate,
    ApplicationStats,
    AssociatedDocument,
    ContactInfo,
    DashboardMetrics,
    TimelineEvent,
)
from app.modules.application_management.domain.enums import ApplicationStatus, EventKind
from app.modules.application_management.domain.ports import (
    ApplicationRepositoryPort,
    DashboardRepositoryPort,
)
from app.modules.application_management.domain.rules import compute_application_stats
from app.modules.application_management.infrastructure.models import (
    ApplicationContactModel,
    ApplicationDocumentModel,
    ApplicationEventModel,
    ApplicationModel,
)
from app.modules.job_discovery.infrastructure.models import JobOfferModel

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class SQLAlchemyApplicationRepository(ApplicationRepositoryPort):
    """Repository SQLAlchemy pour la gestion et le suivi des candidatures."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_entity(
        self,
        model: ApplicationModel,
        contacts: list[ApplicationContactModel] | None = None,
        events: list[ApplicationEventModel] | None = None,
        documents: list[ApplicationDocumentModel] | None = None,
    ) -> ApplicationAggregate:
        contact_entities = [
            ContactInfo(
                id=c.id,
                application_id=c.application_id,
                name=c.name,
                email=c.email,
                phone=c.phone,
                role=c.role,
                created_at=c.created_at,
            )
            for c in (contacts or [])
        ]
        event_entities = [
            TimelineEvent(
                id=e.id,
                application_id=e.application_id,
                kind=EventKind(e.kind),
                occurred_at=e.occurred_at,
                from_status=ApplicationStatus(e.from_status) if e.from_status else None,
                to_status=ApplicationStatus(e.to_status) if e.to_status else None,
                body=e.body,
            )
            for e in (events or [])
        ]
        doc_entities = [
            AssociatedDocument(
                id=d.id,
                application_id=d.application_id,
                document_version_id=d.document_version_id,
                created_at=d.created_at,
            )
            for d in (documents or [])
        ]

        return ApplicationAggregate(
            id=model.id,
            owner_id=model.owner_id,
            offer_id=model.offer_id,
            status=ApplicationStatus(model.status),
            created_at=model.created_at,
            updated_at=model.updated_at,
            applied_at=model.applied_at,
            follow_up_at=model.follow_up_at,
            response_received_at=model.response_received_at,
            cv_version_id=model.cv_version_id,
            letter_version_id=model.letter_version_id,
            contacts=contact_entities,
            events=event_entities,
            documents=doc_entities,
        )

    async def _load_relations(
        self, app_id: uuid.UUID
    ) -> tuple[
        list[ApplicationContactModel],
        list[ApplicationEventModel],
        list[ApplicationDocumentModel],
    ]:
        contacts_query = (
            select(ApplicationContactModel)
            .where(ApplicationContactModel.application_id == app_id)
            .order_by(ApplicationContactModel.created_at.asc())
        )
        events_query = (
            select(ApplicationEventModel)
            .where(ApplicationEventModel.application_id == app_id)
            .order_by(ApplicationEventModel.occurred_at.asc())
        )
        docs_query = (
            select(ApplicationDocumentModel)
            .where(ApplicationDocumentModel.application_id == app_id)
            .order_by(ApplicationDocumentModel.created_at.asc())
        )

        res_contacts = await self._session.execute(contacts_query)
        res_events = await self._session.execute(events_query)
        res_docs = await self._session.execute(docs_query)

        return (
            list(res_contacts.scalars().all()),
            list(res_events.scalars().all()),
            list(res_docs.scalars().all()),
        )

    async def get_by_id(
        self, owner_id: uuid.UUID, application_id: uuid.UUID
    ) -> ApplicationAggregate | None:
        query = select(ApplicationModel).where(
            ApplicationModel.id == application_id,
            ApplicationModel.owner_id == owner_id,
        )
        res = await self._session.execute(query)
        model = res.scalar_one_or_none()
        if model is None:
            return None

        contacts, events, docs = await self._load_relations(model.id)
        return self._to_entity(model, contacts, events, docs)

    async def get_by_offer_id(
        self, owner_id: uuid.UUID, offer_id: uuid.UUID
    ) -> ApplicationAggregate | None:
        query = select(ApplicationModel).where(
            ApplicationModel.offer_id == offer_id,
            ApplicationModel.owner_id == owner_id,
        )
        res = await self._session.execute(query)
        model = res.scalar_one_or_none()
        if model is None:
            return None

        contacts, events, docs = await self._load_relations(model.id)
        return self._to_entity(model, contacts, events, docs)

    async def create(
        self,
        owner_id: uuid.UUID,
        offer_id: uuid.UUID,
        status: ApplicationStatus = ApplicationStatus.NEW_OFFER,
    ) -> ApplicationAggregate:
        model = ApplicationModel(
            owner_id=owner_id,
            offer_id=offer_id,
            status=status.value,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def update_status(
        self,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        new_status: ApplicationStatus,
        applied_at: datetime | None = None,
        response_received_at: datetime | None = None,
    ) -> ApplicationAggregate:
        query = select(ApplicationModel).where(
            ApplicationModel.id == application_id,
            ApplicationModel.owner_id == owner_id,
        )
        res = await self._session.execute(query)
        model = res.scalar_one()

        model.status = new_status.value
        if applied_at is not None:
            model.applied_at = applied_at
        if response_received_at is not None:
            model.response_received_at = response_received_at

        await self._session.flush()
        await self._session.refresh(model)

        contacts, events, docs = await self._load_relations(model.id)
        return self._to_entity(model, contacts, events, docs)

    async def update_follow_up(
        self,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        follow_up_at: datetime | None,
    ) -> ApplicationAggregate:
        query = select(ApplicationModel).where(
            ApplicationModel.id == application_id,
            ApplicationModel.owner_id == owner_id,
        )
        res = await self._session.execute(query)
        model = res.scalar_one()
        model.follow_up_at = follow_up_at

        await self._session.flush()
        await self._session.refresh(model)

        contacts, events, docs = await self._load_relations(model.id)
        return self._to_entity(model, contacts, events, docs)

    async def attach_documents(
        self,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        cv_version_id: uuid.UUID | None = None,
        letter_version_id: uuid.UUID | None = None,
    ) -> ApplicationAggregate:
        query = select(ApplicationModel).where(
            ApplicationModel.id == application_id,
            ApplicationModel.owner_id == owner_id,
        )
        res = await self._session.execute(query)
        model = res.scalar_one()

        if cv_version_id is not None:
            model.cv_version_id = cv_version_id
            self._session.add(
                ApplicationDocumentModel(
                    owner_id=owner_id,
                    application_id=application_id,
                    document_version_id=cv_version_id,
                )
            )
        if letter_version_id is not None:
            model.letter_version_id = letter_version_id
            self._session.add(
                ApplicationDocumentModel(
                    owner_id=owner_id,
                    application_id=application_id,
                    document_version_id=letter_version_id,
                )
            )

        await self._session.flush()
        await self._session.refresh(model)

        contacts, events, docs = await self._load_relations(model.id)
        return self._to_entity(model, contacts, events, docs)

    async def add_event(
        self,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        event: TimelineEvent,
    ) -> TimelineEvent:
        model = ApplicationEventModel(
            id=event.id,
            owner_id=owner_id,
            application_id=application_id,
            kind=event.kind.value,
            from_status=event.from_status.value if event.from_status else None,
            to_status=event.to_status.value if event.to_status else None,
            body=event.body,
            occurred_at=event.occurred_at,
        )
        self._session.add(model)
        await self._session.flush()
        return event

    async def add_contact(
        self,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        contact: ContactInfo,
    ) -> ContactInfo:
        model = ApplicationContactModel(
            id=contact.id,
            owner_id=owner_id,
            application_id=application_id,
            name=contact.name,
            email=contact.email,
            phone=contact.phone,
            role=contact.role,
        )
        self._session.add(model)
        await self._session.flush()
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
        base_query = select(ApplicationModel).where(ApplicationModel.owner_id == owner_id)

        if status:
            base_query = base_query.where(ApplicationModel.status == status.value)

        if has_follow_up_due:
            base_query = base_query.where(ApplicationModel.follow_up_at.is_not(None))

        if company_query or title_query:
            base_query = base_query.join(
                JobOfferModel, ApplicationModel.offer_id == JobOfferModel.id
            )
            if company_query:
                base_query = base_query.where(
                    JobOfferModel.company_name.ilike(f"%{company_query.strip()}%")
                )
            if title_query:
                base_query = base_query.where(JobOfferModel.title.ilike(f"%{title_query.strip()}%"))

        count_query = select(func.count()).select_from(base_query.subquery())
        total_res = await self._session.execute(count_query)
        total = total_res.scalar_one()

        query = base_query.order_by(desc(ApplicationModel.updated_at)).limit(limit).offset(offset)
        res = await self._session.execute(query)
        models = list(res.scalars().all())

        aggregates: list[ApplicationAggregate] = []
        for m in models:
            contacts, events, docs = await self._load_relations(m.id)
            aggregates.append(self._to_entity(m, contacts, events, docs))

        return aggregates, total

    async def list_for_kanban(
        self,
        owner_id: uuid.UUID,
    ) -> dict[ApplicationStatus, list[ApplicationAggregate]]:
        query = (
            select(ApplicationModel)
            .where(ApplicationModel.owner_id == owner_id)
            .order_by(desc(ApplicationModel.updated_at))
        )
        res = await self._session.execute(query)
        models = list(res.scalars().all())

        kanban: dict[ApplicationStatus, list[ApplicationAggregate]] = {
            st: [] for st in ApplicationStatus
        }
        for m in models:
            contacts, events, docs = await self._load_relations(m.id)
            entity = self._to_entity(m, contacts, events, docs)
            kanban[entity.status].append(entity)

        return kanban

    async def get_stats(
        self,
        owner_id: uuid.UUID,
    ) -> ApplicationStats:
        query = select(ApplicationModel).where(ApplicationModel.owner_id == owner_id)
        res = await self._session.execute(query)
        models = list(res.scalars().all())
        entities = [self._to_entity(m) for m in models]
        return compute_application_stats(entities)


class SQLAlchemyDashboardRepository(DashboardRepositoryPort):
    """Repository pour l'agrégation des KPIs réels du tableau de bord (TASK-014-21)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_dashboard_metrics(
        self,
        owner_id: uuid.UUID,
    ) -> DashboardMetrics:
        # 1. Offres trouvées
        offers_query = select(func.count(JobOfferModel.id)).where(
            JobOfferModel.owner_id == owner_id
        )
        total_offers_res = await self._session.execute(offers_query)
        total_offers = total_offers_res.scalar_one()

        # Offres avec statut NEW
        new_offers_query = select(func.count(JobOfferModel.id)).where(
            JobOfferModel.owner_id == owner_id,
            JobOfferModel.status == "new",
        )
        new_res = await self._session.execute(new_offers_query)
        new_offers = new_res.scalar_one()

        # 2. Candidatures
        apps_query = select(ApplicationModel).where(ApplicationModel.owner_id == owner_id)
        apps_res = await self._session.execute(apps_query)
        apps = list(apps_res.scalars().all())

        sent_count = sum(1 for a in apps if a.applied_at is not None or a.status == "sent")
        interviews_count = sum(
            1
            for a in apps
            if a.status
            in {ApplicationStatus.INTERVIEW.value, ApplicationStatus.SECOND_INTERVIEW.value}
        )
        responses_count = sum(
            1
            for a in apps
            if a.response_received_at is not None
            or a.status
            in {
                ApplicationStatus.INTERVIEW.value,
                ApplicationStatus.SECOND_INTERVIEW.value,
                ApplicationStatus.OFFER_RECEIVED.value,
                ApplicationStatus.REJECTED.value,
            }
        )
        response_rate = round((responses_count / sent_count * 100.0), 1) if sent_count > 0 else 0.0

        # 3. Budget IA consommé
        ai_usage_query = select(func.coalesce(func.sum(AIUsageModel.actual_cost), 0)).where(
            AIUsageModel.owner_id == owner_id
        )
        ai_res = await self._session.execute(ai_usage_query)
        total_ai_consumed = float(ai_res.scalar_one() or 0.0)
        consumed_cents = round(total_ai_consumed * 100)

        # Budget global limite
        budget_query = select(AIBudgetModel.amount).where(
            AIBudgetModel.owner_id == owner_id,
            AIBudgetModel.provider.is_(None),
        )
        budget_res = await self._session.execute(budget_query)
        budget_amount = budget_res.scalars().first()
        limit_cents = round(float(budget_amount) * 100) if budget_amount is not None else 0

        return DashboardMetrics(
            total_offers_found=total_offers,
            new_offers_count=new_offers,
            relevant_offers_count=total_offers,
            applications_sent_count=sent_count,
            interviews_count=interviews_count,
            response_rate=response_rate,
            ai_budget_consumed_cents=consumed_cents,
            ai_budget_limit_cents=limit_cents,
        )

