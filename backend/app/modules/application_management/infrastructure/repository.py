"""Persistance SQLAlchemy des candidatures (EPIC 014).

Aucune requête par candidature dans les listes : une seule requête ramène la page, l'offre
liée comprise ; les relations (historique, contacts, documents) ne sont chargées que pour la
fiche d'une candidature. Les mises à jour de statut verrouillent la ligne pour que deux
requêtes simultanées s'enchaînent au lieu de s'écraser.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import desc, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from app.modules.application_management.domain.entities import (
    ApplicationAggregate,
    AssociatedDocument,
    ContactInfo,
    OfferSummary,
    TimelineEvent,
)
from app.modules.application_management.domain.enums import ApplicationStatus, EventKind
from app.modules.application_management.domain.exceptions import DuplicateApplicationError
from app.modules.application_management.domain.ports import (
    ApplicationFilter,
    ApplicationRepositoryPort,
    KanbanColumn,
)
from app.modules.application_management.domain.rules import FOLLOW_UP_STATUSES
from app.modules.application_management.infrastructure.models import (
    ApplicationContactModel,
    ApplicationDocumentModel,
    ApplicationEventModel,
    ApplicationModel,
)
from app.modules.job_discovery.infrastructure.models import JobOfferModel

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _escape_like(texte: str) -> str:
    """Neutralise `%`, `_` et `\\` : la saisie de l'utilisateur est un texte, pas un motif."""
    return texte.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _pair(ligne: Any) -> tuple[ApplicationModel, JobOfferModel]:
    """Ligne d'une requête candidature + offre ; le typage de SQLAlchemy ne la connaît pas."""
    return ligne[0], ligne[1]


def _offer_summary(offre: JobOfferModel) -> OfferSummary:
    return OfferSummary(
        offer_id=offre.id,
        title=offre.title,
        company_name=offre.company_name,
        location=offre.location,
        country_code=offre.country_code,
        application_url=offre.application_url,
    )


def _entity(
    model: ApplicationModel,
    offre: JobOfferModel | None = None,
    *,
    contacts: list[ApplicationContactModel] | None = None,
    events: list[ApplicationEventModel] | None = None,
    documents: list[ApplicationDocumentModel] | None = None,
) -> ApplicationAggregate:
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
        contacts=[
            ContactInfo(c.id, c.application_id, c.name, c.email, c.phone, c.role, c.created_at)
            for c in contacts or []
        ],
        events=[
            TimelineEvent(
                id=e.id,
                application_id=e.application_id,
                kind=EventKind(e.kind),
                occurred_at=e.occurred_at,
                from_status=ApplicationStatus(e.from_status) if e.from_status else None,
                to_status=ApplicationStatus(e.to_status) if e.to_status else None,
                body=e.body,
            )
            for e in events or []
        ],
        documents=[
            AssociatedDocument(d.id, d.application_id, d.document_version_id, d.created_at)
            for d in documents or []
        ],
        offer=_offer_summary(offre) if offre is not None else None,
    )


class SQLAlchemyApplicationRepository(ApplicationRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------ lecture d'une fiche

    def _joined(self, owner_id: uuid.UUID) -> Any:
        return (
            select(ApplicationModel, JobOfferModel)
            .join(JobOfferModel, ApplicationModel.offer_id == JobOfferModel.id)
            .where(ApplicationModel.owner_id == owner_id)
        )

    async def _fiche(self, requete: Any) -> ApplicationAggregate | None:
        ligne = (await self._session.execute(requete)).first()
        if ligne is None:
            return None
        model, offre = _pair(ligne)
        id_ = model.id
        contacts = await self._session.scalars(
            select(ApplicationContactModel)
            .where(ApplicationContactModel.application_id == id_)
            .order_by(ApplicationContactModel.created_at)
        )
        events = await self._session.scalars(
            select(ApplicationEventModel)
            .where(ApplicationEventModel.application_id == id_)
            .order_by(ApplicationEventModel.occurred_at, ApplicationEventModel.created_at)
        )
        documents = await self._session.scalars(
            select(ApplicationDocumentModel)
            .where(ApplicationDocumentModel.application_id == id_)
            .order_by(ApplicationDocumentModel.created_at)
        )
        return _entity(
            model,
            offre,
            contacts=list(contacts),
            events=list(events),
            documents=list(documents),
        )

    async def get_by_id(
        self, owner_id: uuid.UUID, application_id: uuid.UUID, *, for_update: bool = False
    ) -> ApplicationAggregate | None:
        requete = self._joined(owner_id).where(ApplicationModel.id == application_id)
        if for_update:
            requete = requete.with_for_update(of=ApplicationModel)
        return await self._fiche(requete)

    async def get_by_offer_id(
        self, owner_id: uuid.UUID, offer_id: uuid.UUID
    ) -> ApplicationAggregate | None:
        return await self._fiche(
            self._joined(owner_id).where(ApplicationModel.offer_id == offer_id)
        )

    # ------------------------------------------------------------------ écriture

    async def create(
        self, owner_id: uuid.UUID, offer_id: uuid.UUID, status: ApplicationStatus
    ) -> ApplicationAggregate:
        model = ApplicationModel(owner_id=owner_id, offer_id=offer_id, status=status.value)
        try:
            # Point de sauvegarde : un doublon concurrent ne doit pas invalider la transaction.
            async with self._session.begin_nested():
                self._session.add(model)
                await self._session.flush()
        except IntegrityError as err:
            raise DuplicateApplicationError(
                f"Une candidature existe déjà pour l'offre {offer_id}."
            ) from err
        await self._session.refresh(model)
        return _entity(model)

    async def _model(self, owner_id: uuid.UUID, application_id: uuid.UUID) -> ApplicationModel:
        return (
            await self._session.execute(
                select(ApplicationModel)
                .where(ApplicationModel.id == application_id, ApplicationModel.owner_id == owner_id)
                .with_for_update()
            )
        ).scalar_one()

    async def update_status(
        self,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        new_status: ApplicationStatus,
        applied_at: datetime | None = None,
        response_received_at: datetime | None = None,
    ) -> None:
        model = await self._model(owner_id, application_id)
        model.status = new_status.value
        if applied_at is not None:
            model.applied_at = applied_at
        if response_received_at is not None:
            model.response_received_at = response_received_at
        await self._session.flush()

    async def update_follow_up(
        self, owner_id: uuid.UUID, application_id: uuid.UUID, follow_up_at: datetime | None
    ) -> None:
        model = await self._model(owner_id, application_id)
        model.follow_up_at = follow_up_at
        await self._session.flush()

    async def attach_documents(
        self,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        cv_version_id: uuid.UUID | None = None,
        letter_version_id: uuid.UUID | None = None,
    ) -> None:
        model = await self._model(owner_id, application_id)
        if cv_version_id is not None:
            model.cv_version_id = cv_version_id
        if letter_version_id is not None:
            model.letter_version_id = letter_version_id

        for version_id in (cv_version_id, letter_version_id):
            if version_id is None:
                continue
            # Réassocier une version déjà liée (retour à une version précédente) est sans effet.
            await self._session.execute(
                insert(ApplicationDocumentModel)
                .values(
                    id=uuid.uuid4(),
                    owner_id=owner_id,
                    application_id=application_id,
                    document_version_id=version_id,
                )
                .on_conflict_do_nothing(index_elements=["application_id", "document_version_id"])
            )
        await self._session.flush()

    async def add_event(
        self, owner_id: uuid.UUID, application_id: uuid.UUID, event: TimelineEvent
    ) -> TimelineEvent:
        self._session.add(
            ApplicationEventModel(
                id=event.id,
                owner_id=owner_id,
                application_id=application_id,
                kind=event.kind.value,
                from_status=event.from_status.value if event.from_status else None,
                to_status=event.to_status.value if event.to_status else None,
                body=event.body,
                occurred_at=event.occurred_at,
            )
        )
        await self._session.flush()
        return event

    async def add_contact(
        self, owner_id: uuid.UUID, application_id: uuid.UUID, contact: ContactInfo
    ) -> ContactInfo:
        self._session.add(
            ApplicationContactModel(
                id=contact.id,
                owner_id=owner_id,
                application_id=application_id,
                name=contact.name,
                email=contact.email,
                phone=contact.phone,
                role=contact.role,
            )
        )
        await self._session.flush()
        return contact

    # ------------------------------------------------------------------ vues

    async def list_applications(
        self, owner_id: uuid.UUID, criteria: ApplicationFilter, limit: int, offset: int
    ) -> tuple[list[ApplicationAggregate], int]:
        requete = self._joined(owner_id)
        if criteria.status is not None:
            requete = requete.where(ApplicationModel.status == criteria.status.value)
        if criteria.has_follow_up:
            requete = requete.where(ApplicationModel.follow_up_at.is_not(None))
        if criteria.follow_up_due:
            requete = requete.where(
                ApplicationModel.follow_up_at <= func.now(),
                ApplicationModel.status.in_([s.value for s in FOLLOW_UP_STATUSES]),
            )
        if criteria.company_query and criteria.company_query.strip():
            motif = f"%{_escape_like(criteria.company_query.strip())}%"
            requete = requete.where(JobOfferModel.company_name.ilike(motif, escape="\\"))
        if criteria.title_query and criteria.title_query.strip():
            motif = f"%{_escape_like(criteria.title_query.strip())}%"
            requete = requete.where(JobOfferModel.title.ilike(motif, escape="\\"))

        total = int(
            await self._session.scalar(
                select(func.count()).select_from(
                    requete.with_only_columns(ApplicationModel.id).subquery()
                )
            )
            or 0
        )
        page = await self._session.execute(
            requete.order_by(desc(ApplicationModel.updated_at), desc(ApplicationModel.id))
            .limit(limit)
            .offset(offset)
        )
        return [_entity(*_pair(ligne)) for ligne in page.all()], total

    async def list_for_kanban(
        self, owner_id: uuid.UUID, per_column_limit: int
    ) -> dict[ApplicationStatus, KanbanColumn]:
        resultat = await self._session.execute(
            select(ApplicationModel.status, func.count())
            .where(ApplicationModel.owner_id == owner_id)
            .group_by(ApplicationModel.status)
        )
        comptes = {ligne[0]: int(ligne[1]) for ligne in resultat}
        rang = (
            func.row_number()
            .over(
                partition_by=ApplicationModel.status,
                order_by=[ApplicationModel.updated_at.desc(), ApplicationModel.id.desc()],
            )
            .label("rang")
        )
        recentes = (
            select(ApplicationModel.id.label("id"), rang)
            .where(ApplicationModel.owner_id == owner_id)
            .subquery()
        )
        lignes = await self._session.execute(
            self._joined(owner_id)
            .join(recentes, recentes.c.id == ApplicationModel.id)
            .where(recentes.c.rang <= per_column_limit)
            .order_by(desc(ApplicationModel.updated_at), desc(ApplicationModel.id))
        )
        par_statut: dict[ApplicationStatus, list[ApplicationAggregate]] = {
            s: [] for s in ApplicationStatus
        }
        for ligne in lignes.all():
            entite = _entity(*_pair(ligne))
            par_statut[entite.status].append(entite)
        return {
            s: KanbanColumn(count=int(comptes.get(s.value, 0)), items=par_statut[s])
            for s in ApplicationStatus
        }

    async def list_for_stats(self, owner_id: uuid.UUID) -> list[ApplicationAggregate]:
        lignes = await self._session.scalars(
            select(ApplicationModel).where(ApplicationModel.owner_id == owner_id)
        )
        return [_entity(m) for m in lignes]
