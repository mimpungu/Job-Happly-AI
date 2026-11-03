from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import (
    Base,
    CreatedAtMixin,
    OwnedMixin,
    PrimaryKeyMixin,
    TimestampMixin,
    enum_check,
)
from app.modules.application_management.domain.enums import ApplicationStatus, EventKind


class ApplicationModel(PrimaryKeyMixin, TimestampMixin, OwnedMixin, Base):
    """Candidature. L'envoi externe est toujours confirmé par l'utilisateur (`applied_at`)."""

    __tablename__ = "applications"
    __table_args__ = (
        enum_check("status_valid", "status", ApplicationStatus),
        Index("uq_applications_owner_id_offer_id", "owner_id", "offer_id", unique=True),
        Index("ix_applications_owner_id_status", "owner_id", "status"),
        Index(
            "ix_applications_owner_id_follow_up_at",
            "owner_id",
            "follow_up_at",
            postgresql_where=text("follow_up_at IS NOT NULL"),
        ),
    )

    # RESTRICT : une offre liée à une candidature ne peut pas être supprimée par erreur.
    offer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_offers.id", ondelete="RESTRICT")
    )
    status: Mapped[str] = mapped_column(
        String(30), server_default=ApplicationStatus.NEW_OFFER.value
    )
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    follow_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    response_received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cv_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_versions.id", ondelete="SET NULL")
    )
    letter_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_versions.id", ondelete="SET NULL")
    )


class ApplicationEventModel(PrimaryKeyMixin, CreatedAtMixin, OwnedMixin, Base):
    """Historique : changements de statut, notes, entretiens, relances."""

    __tablename__ = "application_events"
    __table_args__ = (
        enum_check("kind_valid", "kind", EventKind),
        CheckConstraint(
            "kind <> 'status_change' OR to_status IS NOT NULL", name="status_change_has_target"
        ),
        Index("ix_application_events_application_id_occurred_at", "application_id", "occurred_at"),
    )

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(String(20))
    from_status: Mapped[str | None] = mapped_column(String(30))
    to_status: Mapped[str | None] = mapped_column(String(30))
    body: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ApplicationContactModel(PrimaryKeyMixin, TimestampMixin, OwnedMixin, Base):
    __tablename__ = "application_contacts"

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(40))
    role: Mapped[str | None] = mapped_column(String(200))


class ApplicationDocumentModel(PrimaryKeyMixin, CreatedAtMixin, OwnedMixin, Base):
    """Documents associés à une candidature (version exacte envoyée)."""

    __tablename__ = "application_documents"
    __table_args__ = (
        Index(
            "uq_application_documents_application_id_document_version_id",
            "application_id",
            "document_version_id",
            unique=True,
        ),
    )

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE")
    )
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_versions.id", ondelete="RESTRICT"), index=True
    )
