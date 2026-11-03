from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import (
    Base,
    CreatedAtMixin,
    OwnedMixin,
    PrimaryKeyMixin,
    TimestampMixin,
    enum_check,
)
from app.modules.document_generation.domain.enums import DocumentKind


class GeneratedDocumentModel(PrimaryKeyMixin, TimestampMixin, OwnedMixin, Base):
    """Document logique (un CV ou une lettre pour une offre) ; ses versions sont immuables."""

    __tablename__ = "generated_documents"
    __table_args__ = (
        enum_check("kind_valid", "kind", DocumentKind),
        CheckConstraint("language ~ '^[a-z]{2,3}(-[A-Z]{2})?$'", name="language_format"),
        Index("ix_generated_documents_owner_id_kind", "owner_id", "kind"),
    )

    kind: Mapped[str] = mapped_column(String(20))
    # Une offre supprimée n'efface pas les documents déjà produits.
    offer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_offers.id", ondelete="SET NULL"), index=True
    )
    language: Mapped[str] = mapped_column(String(10))
    title: Mapped[str] = mapped_column(String(300))


class DocumentVersionModel(PrimaryKeyMixin, CreatedAtMixin, OwnedMixin, Base):
    """Version immuable : jamais de mise à jour, on crée une nouvelle version."""

    __tablename__ = "document_versions"
    __table_args__ = (
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint("size_bytes >= 0", name="size_positive"),
        CheckConstraint("char_length(sha256) = 64", name="sha256_length"),
        Index("uq_document_versions_document_id_version", "document_id", "version", unique=True),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("generated_documents.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    latex_source: Mapped[str | None] = mapped_column(Text)
    # Clé de stockage généré (ADR-0007), jamais un nom de fichier fourni par l'utilisateur.
    storage_key: Mapped[str] = mapped_column(String(200))
    sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    ats_report: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
