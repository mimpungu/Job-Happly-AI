"""Cas d'usage du suivi de candidatures (EPIC 014).

Principe directeur : l'application prépare et suit, l'utilisateur envoie. Aucune candidature
n'est jamais soumise automatiquement, et l'envoi n'est enregistré que par une confirmation
explicite (`confirm_manual_submission`).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from app.modules.application_management.domain.entities import (
    ApplicationAggregate,
    ApplicationDossier,
    ApplicationStats,
    ContactInfo,
    DocumentVersionInfo,
    TimelineEvent,
)
from app.modules.application_management.domain.enums import ApplicationStatus, EventKind
from app.modules.application_management.domain.exceptions import (
    AlreadySubmittedError,
    ApplicationNotFoundError,
    DocumentKindMismatchError,
    DocumentLockedError,
    DocumentVersionNotFoundError,
    DuplicateApplicationError,
    InvalidDateError,
    InvalidStatusTransitionError,
    NothingToAttachError,
    OfferNotFoundError,
)
from app.modules.application_management.domain.ports import (
    ApplicationFilter,
    ApplicationRepositoryPort,
    DocumentVersionReaderPort,
    KanbanColumn,
    OfferReaderPort,
)
from app.modules.application_management.domain.rules import (
    INITIAL_STATUSES,
    RESPONSE_STATUSES,
    SUBMITTABLE_STATUSES,
    compute_application_stats,
    missing_dossier_elements,
    safe_external_url,
    validate_status_transition,
    verify_dossier_readiness,
)

_CLOCK_TOLERANCE = timedelta(minutes=1)
_KIND_CV = "cv"
_KIND_LETTER = "cover_letter"


def _require_aware(valeur: datetime, libelle: str) -> datetime:
    if valeur.tzinfo is None or valeur.utcoffset() is None:
        raise InvalidDateError(f"{libelle} : la date doit comporter un fuseau horaire.")
    return valeur


class ApplicationTrackingService:
    """Service applicatif central du CRM de candidatures."""

    def __init__(
        self,
        repository: ApplicationRepositoryPort,
        offers: OfferReaderPort,
        documents: DocumentVersionReaderPort,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._repository = repository
        self._offers = offers
        self._documents = documents
        self._clock = clock

    # ------------------------------------------------------------------ création et lecture

    async def create_application(
        self,
        *,
        owner_id: uuid.UUID,
        offer_id: uuid.UUID,
        initial_status: ApplicationStatus = ApplicationStatus.NEW_OFFER,
    ) -> ApplicationAggregate:
        """Crée la candidature d'une offre (TASK-014-01, 02) ; une offre = une candidature."""
        if initial_status not in INITIAL_STATUSES:
            raise InvalidStatusTransitionError(
                f"Une candidature ne peut pas être créée au statut '{initial_status.value}' : "
                "l'envoi et les réponses s'enregistrent après coup."
            )
        if await self._offers.get_summary(owner_id, offer_id) is None:
            raise OfferNotFoundError(f"Offre {offer_id} introuvable.")
        if await self._repository.get_by_offer_id(owner_id, offer_id) is not None:
            raise DuplicateApplicationError(f"Une candidature existe déjà pour l'offre {offer_id}.")

        created = await self._repository.create(owner_id, offer_id, initial_status)
        await self._record(
            owner_id,
            created.id,
            EventKind.STATUS_CHANGE,
            "Création de la candidature dans le CRM.",
            to_status=initial_status,
        )
        return await self.get_application(owner_id=owner_id, application_id=created.id)

    async def get_application(
        self, *, owner_id: uuid.UUID, application_id: uuid.UUID
    ) -> ApplicationAggregate:
        """Fiche complète d'une candidature (TASK-014-14)."""
        return await self._load(owner_id, application_id)

    async def delete_application(self, *, owner_id: uuid.UUID, application_id: uuid.UUID) -> None:
        """Retire une candidature suivie (par exemple ajoutée par erreur). L'offre est conservée."""
        await self._load(owner_id, application_id, for_update=True)
        await self._repository.delete(owner_id, application_id)

    async def _load(
        self, owner_id: uuid.UUID, application_id: uuid.UUID, *, for_update: bool = False
    ) -> ApplicationAggregate:
        app = await self._repository.get_by_id(owner_id, application_id, for_update=for_update)
        if app is None:
            raise ApplicationNotFoundError(f"Candidature {application_id} introuvable.")
        return app

    async def _record(
        self,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        kind: EventKind,
        body: str,
        *,
        from_status: ApplicationStatus | None = None,
        to_status: ApplicationStatus | None = None,
        occurred_at: datetime | None = None,
    ) -> TimelineEvent:
        event = TimelineEvent(
            id=uuid.uuid4(),
            application_id=application_id,
            kind=kind,
            occurred_at=occurred_at or self._clock(),
            from_status=from_status,
            to_status=to_status,
            body=body,
        )
        return await self._repository.add_event(owner_id, application_id, event)

    # ------------------------------------------------------------------ statuts

    async def change_status(
        self,
        *,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        target_status: ApplicationStatus,
        reason: str | None = None,
    ) -> ApplicationAggregate:
        """Fait évoluer le statut selon la machine à états, avec trace (TASK-014-03, 06)."""
        app = await self._load(owner_id, application_id, for_update=True)
        if target_status == app.status:
            return app  # rien à faire, rien à historiser

        precedent = app.status
        validate_status_transition(precedent, target_status)
        if target_status == ApplicationStatus.SENT:
            raise InvalidStatusTransitionError(
                "L'envoi se confirme explicitement (confirmation d'envoi) : "
                "il ne se déduit pas d'un simple changement de statut."
            )
        if target_status == ApplicationStatus.READY_TO_SEND:
            verify_dossier_readiness(await self._dossier(app))

        now = self._clock()
        await self._repository.update_status(
            owner_id,
            application_id,
            target_status,
            response_received_at=(
                now
                if target_status in RESPONSE_STATUSES and app.response_received_at is None
                else None
            ),
        )
        await self._record(
            owner_id,
            application_id,
            EventKind.STATUS_CHANGE,
            (reason or "").strip() or f"Passage du statut à '{target_status.value}'.",
            from_status=precedent,
            to_status=target_status,
            occurred_at=now,
        )
        return await self._load(owner_id, application_id)

    async def confirm_manual_submission(
        self,
        *,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        notes: str | None = None,
        applied_at: datetime | None = None,
    ) -> ApplicationAggregate:
        """Enregistre que l'utilisateur a lui-même envoyé sa candidature (TASK-014-04, 20).

        Ne soumet rien : c'est la trace d'un envoi fait ailleurs. `applied_at` permet de
        saisir la vraie date si l'envoi a précédé son enregistrement.
        """
        app = await self._load(owner_id, application_id, for_update=True)
        if app.applied_at is not None:
            raise AlreadySubmittedError("L'envoi de cette candidature est déjà confirmé.")
        if app.status not in SUBMITTABLE_STATUSES:
            raise InvalidStatusTransitionError(
                f"L'envoi ne peut pas être confirmé depuis le statut '{app.status.value}'."
            )

        precedent = app.status
        now = self._clock()
        envoyee_le = _require_aware(applied_at, "Date d'envoi") if applied_at else now
        if envoyee_le > now + _CLOCK_TOLERANCE:
            raise InvalidDateError("La date d'envoi ne peut pas être dans le futur.")

        await self._repository.update_status(
            owner_id, application_id, ApplicationStatus.SENT, applied_at=envoyee_le
        )
        corps = (notes or "").strip() or "Envoi manuel confirmé par l'utilisateur."
        await self._record(
            owner_id,
            application_id,
            EventKind.STATUS_CHANGE,
            f"{corps} (envoyée le {envoyee_le.astimezone(UTC):%Y-%m-%d %H:%M} UTC)",
            from_status=precedent,
            to_status=ApplicationStatus.SENT,
            occurred_at=now,
        )
        return await self._load(owner_id, application_id)

    # ------------------------------------------------------------------ historique

    async def add_note(
        self, *, owner_id: uuid.UUID, application_id: uuid.UUID, note_body: str
    ) -> TimelineEvent:
        """Ajoute une note à l'historique (TASK-014-07)."""
        await self._load(owner_id, application_id)
        return await self._record(owner_id, application_id, EventKind.NOTE, note_body.strip())

    async def add_interview_event(
        self,
        *,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        description: str,
        interview_time: datetime | None = None,
    ) -> TimelineEvent:
        """Enregistre un entretien ou un échange, daté (TASK-014-08)."""
        await self._load(owner_id, application_id)
        quand = _require_aware(interview_time, "Date de l'entretien") if interview_time else None
        return await self._record(
            owner_id, application_id, EventKind.INTERVIEW, description.strip(), occurred_at=quand
        )

    async def schedule_follow_up(
        self,
        *,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        follow_up_at: datetime | None,
        notes: str | None = None,
    ) -> ApplicationAggregate:
        """Planifie ou annule la relance d'une candidature envoyée (TASK-014-10)."""
        app = await self._load(owner_id, application_id, for_update=True)
        if follow_up_at is not None:
            _require_aware(follow_up_at, "Date de relance")
            if not app.is_sent:
                raise InvalidDateError("On ne relance qu'une candidature déjà envoyée.")
            if follow_up_at < self._clock() - _CLOCK_TOLERANCE:
                raise InvalidDateError("La date de relance doit être dans le futur.")

        await self._repository.update_follow_up(owner_id, application_id, follow_up_at)
        texte = (
            f"Relance planifiée le {follow_up_at.astimezone(UTC):%Y-%m-%d %H:%M} UTC."
            if follow_up_at
            else "Relance annulée."
        )
        if notes and notes.strip():
            texte += f" Note : {notes.strip()}"
        await self._record(owner_id, application_id, EventKind.FOLLOW_UP, texte)
        return await self._load(owner_id, application_id)

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
        """Enregistre le recruteur ou un contact, lorsqu'il est connu (TASK-014-05)."""
        await self._load(owner_id, application_id)
        contact = ContactInfo(
            id=uuid.uuid4(),
            application_id=application_id,
            name=name.strip(),
            email=(email or "").strip() or None,
            phone=(phone or "").strip() or None,
            role=(role or "").strip() or None,
            created_at=self._clock(),
        )
        return await self._repository.add_contact(owner_id, application_id, contact)

    # ------------------------------------------------------------------ documents et dossier

    async def attach_documents(
        self,
        *,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        cv_version_id: uuid.UUID | None = None,
        letter_version_id: uuid.UUID | None = None,
    ) -> ApplicationAggregate:
        """Associe les versions exactes de CV et de lettre (TASK-014-09).

        Chaque version doit exister, appartenir à l'utilisateur et être du bon type. Une fois
        l'envoi confirmé, un document déjà associé ne peut plus être remplacé : il atteste de
        ce qui a réellement été envoyé.
        """
        if cv_version_id is None and letter_version_id is None:
            raise NothingToAttachError("Aucune version de document à associer.")
        app = await self._load(owner_id, application_id, for_update=True)

        cv = await self._checked_version(owner_id, cv_version_id, _KIND_CV)
        lettre = await self._checked_version(owner_id, letter_version_id, _KIND_LETTER)
        if app.applied_at is not None:
            for libelle, actuel, nouveau in (
                ("CV", app.cv_version_id, cv_version_id),
                ("lettre", app.letter_version_id, letter_version_id),
            ):
                if actuel is not None and nouveau is not None and actuel != nouveau:
                    raise DocumentLockedError(
                        f"La {libelle} envoyée ne peut plus être remplacée."
                        if libelle == "lettre"
                        else "Le CV envoyé ne peut plus être remplacé."
                    )

        await self._repository.attach_documents(
            owner_id,
            application_id,
            cv_version_id=cv_version_id,
            letter_version_id=letter_version_id,
        )
        details = [
            f"{'CV' if info.kind == _KIND_CV else 'Lettre'} « {info.title} » v{info.version}"
            for info in (cv, lettre)
            if info is not None
        ]
        await self._record(
            owner_id, application_id, EventKind.OTHER, f"Documents associés : {', '.join(details)}."
        )
        return await self._load(owner_id, application_id)

    async def _checked_version(
        self, owner_id: uuid.UUID, version_id: uuid.UUID | None, expected_kind: str
    ) -> DocumentVersionInfo | None:
        if version_id is None:
            return None
        info = await self._documents.get_info(owner_id, version_id)
        if info is None:
            raise DocumentVersionNotFoundError(f"Version de document {version_id} introuvable.")
        if info.kind != expected_kind:
            raise DocumentKindMismatchError(
                "Cette version est une lettre de motivation, pas un CV."
                if expected_kind == _KIND_CV
                else "Cette version est un CV, pas une lettre de motivation."
            )
        return info

    async def describe_documents(self, app: ApplicationAggregate) -> list[DocumentVersionInfo]:
        """Type, titre, rang et qualité des versions associées, pour la fiche (TASK-014-09)."""
        infos: list[DocumentVersionInfo] = []
        for lien in app.documents:
            info = await self._documents.get_info(app.owner_id, lien.document_version_id)
            if info is not None:
                infos.append(info)
        return infos

    async def prepare_dossier(
        self, *, owner_id: uuid.UUID, application_id: uuid.UUID
    ) -> ApplicationDossier:
        """Dossier de candidature et contrôle de ses pièces (TASK-014-16, 17, 18)."""
        return await self._dossier(await self._load(owner_id, application_id))

    async def _dossier(self, app: ApplicationAggregate) -> ApplicationDossier:
        offre = app.offer
        url = offre.application_url if offre else None
        manquants = missing_dossier_elements(
            has_cv=app.cv_version_id is not None,
            has_letter=app.letter_version_id is not None,
            application_url=url,
        )
        alertes: list[str] = []
        for libelle, version_id in (("CV", app.cv_version_id), ("Lettre", app.letter_version_id)):
            if version_id is None:
                continue
            info = await self._documents.get_info(app.owner_id, version_id)
            if info is not None and info.quality_passed is False:
                note = (
                    f" (score {info.quality_score}/100)" if info.quality_score is not None else ""
                )
                alertes.append(f"{libelle} : l'audit de qualité n'est pas conforme{note}.")
        return ApplicationDossier(
            application_id=app.id,
            offer_id=app.offer_id,
            job_title=offre.title if offre else "",
            company_name=offre.company_name if offre else None,
            application_url=url,
            has_cv=app.cv_version_id is not None,
            cv_version_id=app.cv_version_id,
            has_letter=app.letter_version_id is not None,
            letter_version_id=app.letter_version_id,
            is_ready_to_send=not manquants,
            missing_elements=manquants,
            warnings=tuple(alertes),
        )

    async def get_application_url_action(
        self, *, owner_id: uuid.UUID, application_id: uuid.UUID
    ) -> str:
        """URL vérifiée de l'annonce, à ouvrir par l'utilisateur lui-même (TASK-014-19)."""
        app = await self._load(owner_id, application_id)
        return safe_external_url(app.offer.application_url if app.offer else None)

    # ------------------------------------------------------------------ vues et statistiques

    async def list_applications(
        self,
        *,
        owner_id: uuid.UUID,
        criteria: ApplicationFilter | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ApplicationAggregate], int]:
        """Vue tableau paginée et filtrée (TASK-014-11, 13)."""
        return await self._repository.list_applications(
            owner_id, criteria or ApplicationFilter(), limit, offset
        )

    async def get_kanban_view(
        self, *, owner_id: uuid.UUID, per_column_limit: int = 20
    ) -> dict[ApplicationStatus, KanbanColumn]:
        """Vue Kanban découpée par statut (TASK-014-12)."""
        return await self._repository.list_for_kanban(owner_id, per_column_limit)

    async def get_stats(self, *, owner_id: uuid.UUID) -> ApplicationStats:
        """Statistiques sur les seules données réelles (TASK-014-15, 22)."""
        return compute_application_stats(
            await self._repository.list_for_stats(owner_id), now=self._clock()
        )
