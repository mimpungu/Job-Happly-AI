"""Service applicatif de gestion et suivi des candidatures (EPIC 014).

Orchestre la création, l'évolution du statut, l'historique des événements,
les dossiers de candidature, l'association documentaire et les métriques CRM.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.modules.application_management.domain.entities import (
    ApplicationAggregate,
    ApplicationDossier,
    ApplicationStats,
    ContactInfo,
    TimelineEvent,
)
from app.modules.application_management.domain.enums import ApplicationStatus, EventKind
from app.modules.application_management.domain.exceptions import (
    ApplicationNotFoundError,
    DuplicateApplicationError,
    ExternalOfferLinkMissingError,
)
from app.modules.application_management.domain.rules import (
    validate_status_transition,
)

if TYPE_CHECKING:
    from app.modules.application_management.domain.ports import ApplicationRepositoryPort


class ApplicationTrackingService:
    """Service applicatif central pour le CRM de candidatures."""

    def __init__(self, repository: ApplicationRepositoryPort) -> None:
        self._repository = repository

    async def create_application(
        self,
        *,
        owner_id: uuid.UUID,
        offer_id: uuid.UUID,
        initial_status: ApplicationStatus = ApplicationStatus.NEW_OFFER,
    ) -> ApplicationAggregate:
        """Crée une nouvelle candidature associée à une offre d'emploi (TASK-014-01, 02)."""
        existing = await self._repository.get_by_offer_id(owner_id, offer_id)
        if existing is not None:
            raise DuplicateApplicationError(f"Une candidature existe déjà pour l'offre {offer_id}.")

        app = await self._repository.create(
            owner_id=owner_id,
            offer_id=offer_id,
            status=initial_status,
        )

        event = TimelineEvent(
            id=uuid.uuid4(),
            application_id=app.id,
            kind=EventKind.STATUS_CHANGE,
            occurred_at=datetime.now(UTC),
            from_status=None,
            to_status=initial_status,
            body="Création de la candidature dans le CRM.",
        )
        await self._repository.add_event(owner_id, app.id, event)
        if event not in app.events:
            app.events.append(event)
        return app

    async def get_application(
        self,
        *,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
    ) -> ApplicationAggregate:
        """Récupère la fiche détaillée d'une candidature (TASK-014-14)."""
        app = await self._repository.get_by_id(owner_id, application_id)
        if app is None:
            raise ApplicationNotFoundError(f"Candidature {application_id} introuvable.")
        return app

    async def change_status(
        self,
        *,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        target_status: ApplicationStatus,
        reason: str | None = None,
    ) -> ApplicationAggregate:
        """Fait évoluer le statut avec validation et traçabilité historique (TASK-014-03, 06)."""
        app = await self.get_application(owner_id=owner_id, application_id=application_id)
        current = app.status

        # Validation de la transition d'état
        validate_status_transition(current, target_status)

        applied_at = app.applied_at
        response_received_at = app.response_received_at
        now = datetime.now(UTC)

        if target_status == ApplicationStatus.SENT and applied_at is None:
            applied_at = now

        if (
            target_status
            in {
                ApplicationStatus.INTERVIEW,
                ApplicationStatus.SECOND_INTERVIEW,
                ApplicationStatus.OFFER_RECEIVED,
                ApplicationStatus.REJECTED,
            }
            and response_received_at is None
        ):
            response_received_at = now

        updated_app = await self._repository.update_status(
            owner_id=owner_id,
            application_id=application_id,
            new_status=target_status,
            applied_at=applied_at,
            response_received_at=response_received_at,
        )

        event = TimelineEvent(
            id=uuid.uuid4(),
            application_id=application_id,
            kind=EventKind.STATUS_CHANGE,
            occurred_at=now,
            from_status=current,
            to_status=target_status,
            body=reason or f"Passage du statut à '{target_status.value}'.",
        )
        await self._repository.add_event(owner_id, application_id, event)
        if event not in updated_app.events:
            updated_app.events.append(event)
        return updated_app

    async def confirm_manual_submission(
        self,
        *,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        notes: str | None = None,
    ) -> ApplicationAggregate:
        """Confirme manuellement l'envoi externe par l'utilisateur (TASK-014-04, 20).

        Ne soumet jamais automatiquement : l'utilisateur confirme qu'il a postulé.
        """
        app = await self.get_application(owner_id=owner_id, application_id=application_id)
        now = datetime.now(UTC)

        updated_app = await self._repository.update_status(
            owner_id=owner_id,
            application_id=application_id,
            new_status=ApplicationStatus.SENT,
            applied_at=now,
        )

        event = TimelineEvent(
            id=uuid.uuid4(),
            application_id=application_id,
            kind=EventKind.STATUS_CHANGE,
            occurred_at=now,
            from_status=app.status,
            to_status=ApplicationStatus.SENT,
            body=notes or "Envoi manuel confirmé par l'utilisateur.",
        )
        await self._repository.add_event(owner_id, application_id, event)
        if event not in updated_app.events:
            updated_app.events.append(event)
        return updated_app

    async def add_note(
        self,
        *,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        note_body: str,
    ) -> TimelineEvent:
        """Ajoute une note personnelle dans l'historique (TASK-014-07)."""
        await self.get_application(owner_id=owner_id, application_id=application_id)
        event = TimelineEvent(
            id=uuid.uuid4(),
            application_id=application_id,
            kind=EventKind.NOTE,
            occurred_at=datetime.now(UTC),
            body=note_body.strip(),
        )
        return await self._repository.add_event(owner_id, application_id, event)

    async def add_interview_event(
        self,
        *,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        description: str,
        interview_time: datetime | None = None,
    ) -> TimelineEvent:
        """Enregistre un événement d'entretien ou d'échange (TASK-014-08)."""
        await self.get_application(owner_id=owner_id, application_id=application_id)
        event = TimelineEvent(
            id=uuid.uuid4(),
            application_id=application_id,
            kind=EventKind.INTERVIEW,
            occurred_at=interview_time or datetime.now(UTC),
            body=description.strip(),
        )
        return await self._repository.add_event(owner_id, application_id, event)

    async def schedule_follow_up(
        self,
        *,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        follow_up_at: datetime | None,
        notes: str | None = None,
    ) -> ApplicationAggregate:
        """Définit ou annule une date de relance (TASK-014-10)."""
        await self.get_application(owner_id=owner_id, application_id=application_id)
        updated_app = await self._repository.update_follow_up(
            owner_id=owner_id,
            application_id=application_id,
            follow_up_at=follow_up_at,
        )

        event_text = (
            f"Relance planifiée pour le {follow_up_at.isoformat()}."
            if follow_up_at
            else "Relance annulée."
        )
        if notes:
            event_text += f" Note : {notes}"

        event = TimelineEvent(
            id=uuid.uuid4(),
            application_id=application_id,
            kind=EventKind.FOLLOW_UP,
            occurred_at=datetime.now(UTC),
            body=event_text,
        )
        await self._repository.add_event(owner_id, application_id, event)
        if event not in updated_app.events:
            updated_app.events.append(event)
        return updated_app

    async def attach_documents(
        self,
        *,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        cv_version_id: uuid.UUID | None = None,
        letter_version_id: uuid.UUID | None = None,
    ) -> ApplicationAggregate:
        """Associe les versions de CV et/ou lettre envoyées (TASK-014-09)."""
        await self.get_application(owner_id=owner_id, application_id=application_id)
        updated_app = await self._repository.attach_documents(
            owner_id=owner_id,
            application_id=application_id,
            cv_version_id=cv_version_id,
            letter_version_id=letter_version_id,
        )

        details = []
        if cv_version_id:
            details.append(f"CV v-{str(cv_version_id)[:8]}")
        if letter_version_id:
            details.append(f"Lettre v-{str(letter_version_id)[:8]}")

        event = TimelineEvent(
            id=uuid.uuid4(),
            application_id=application_id,
            kind=EventKind.OTHER,
            occurred_at=datetime.now(UTC),
            body=f"Documents associés : {', '.join(details) if details else 'aucun'}.",
        )
        await self._repository.add_event(owner_id, application_id, event)
        if event not in updated_app.events:
            updated_app.events.append(event)
        return updated_app

    async def add_contact(
        self,
        *,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        name: str,
        email: str | None = None,
        phone: str | None = None,
        role: str | None = None,
    ) -> ContactInfo:
        """Enregistre les coordonnées d'un recruteur (TASK-014-05)."""
        await self.get_application(owner_id=owner_id, application_id=application_id)
        contact = ContactInfo(
            id=uuid.uuid4(),
            application_id=application_id,
            name=name.strip(),
            email=email.strip() if email else None,
            phone=phone.strip() if phone else None,
            role=role.strip() if role else None,
            created_at=datetime.now(UTC),
        )
        return await self._repository.add_contact(owner_id, application_id, contact)

    async def list_applications(
        self,
        *,
        owner_id: uuid.UUID,
        status: ApplicationStatus | None = None,
        company_query: str | None = None,
        title_query: str | None = None,
        has_follow_up_due: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ApplicationAggregate], int]:
        """Vue tableau avec filtrage et pagination (TASK-014-11, 13)."""
        return await self._repository.list_applications(
            owner_id=owner_id,
            status=status,
            company_query=company_query,
            title_query=title_query,
            has_follow_up_due=has_follow_up_due,
            limit=limit,
            offset=offset,
        )

    async def get_kanban_view(
        self,
        *,
        owner_id: uuid.UUID,
    ) -> dict[ApplicationStatus, list[ApplicationAggregate]]:
        """Vue Kanban regroupée par colonne de statut (TASK-014-12)."""
        return await self._repository.list_for_kanban(owner_id)

    async def prepare_dossier(
        self,
        *,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        job_title: str,
        company_name: str | None,
        application_url: str | None,
    ) -> ApplicationDossier:
        """Prépare et vérifie le dossier de candidature (TASK-014-16, 17, 18)."""
        app = await self.get_application(owner_id=owner_id, application_id=application_id)
        manquants: list[str] = []

        if not app.cv_version_id:
            manquants.append("CV personnalisé manquant")
        if not app.letter_version_id:
            manquants.append("Lettre de motivation manquante")
        if not application_url:
            manquants.append("Lien de candidature externe manquant")

        is_ready = len(manquants) == 0

        return ApplicationDossier(
            application_id=app.id,
            offer_id=app.offer_id,
            job_title=job_title,
            company_name=company_name,
            application_url=application_url,
            has_cv=app.cv_version_id is not None,
            cv_version_id=app.cv_version_id,
            has_letter=app.letter_version_id is not None,
            letter_version_id=app.letter_version_id,
            is_ready_to_send=is_ready,
            missing_elements=tuple(manquants),
        )

    async def get_application_url_action(
        self,
        *,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        offer_application_url: str | None,
    ) -> str:
        """Génère l'action sécurisée d'ouverture du site de candidature (TASK-014-19)."""
        await self.get_application(owner_id=owner_id, application_id=application_id)
        if not offer_application_url or not offer_application_url.strip():
            raise ExternalOfferLinkMissingError(
                "Cette offre ne dispose pas d'URL externe de candidature."
            )
        url = offer_application_url.strip()
        if not url.startswith(("http://", "https://")):
            raise ExternalOfferLinkMissingError("URL de candidature invalide.")
        return url

    async def get_stats(
        self,
        *,
        owner_id: uuid.UUID,
    ) -> ApplicationStats:
        """Statistiques consolidées sur données réelles (TASK-014-15, 22)."""
        return await self._repository.get_stats(owner_id)
