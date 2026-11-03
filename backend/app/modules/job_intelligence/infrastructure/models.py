from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import Base, CreatedAtMixin, OwnedMixin, PrimaryKeyMixin, enum_check
from app.modules.job_intelligence.domain.enums import AnalysisKind


class JobAnalysisModel(PrimaryKeyMixin, CreatedAtMixin, OwnedMixin, Base):
    """Analyse d'offre versionnée et réutilisable.

    La clé d'unicité (offre, type, version de prompt, modèle, empreinte du texte) garantit
    qu'une annonce inchangée n'est jamais analysée deux fois.
    """

    __tablename__ = "job_analyses"
    __table_args__ = (
        enum_check("kind_valid", "kind", AnalysisKind),
        CheckConstraint("char_length(content_hash) = 64", name="content_hash_sha256"),
        Index(
            "uq_job_analyses_reuse_key",
            "owner_id",
            "offer_id",
            "kind",
            "prompt_version",
            "model",
            "content_hash",
            unique=True,
        ),
    )

    offer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_offers.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(20))
    prompt_version: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(120))
    content_hash: Mapped[str] = mapped_column(String(64))
    result: Mapped[dict[str, Any]] = mapped_column(JSONB)
    ai_usage_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_usages.id", ondelete="SET NULL")
    )


class JobMatchScoreModel(PrimaryKeyMixin, OwnedMixin, Base):
    """Score déterministe sur 100 (sans IA), reproductible pour une version de pondérations."""

    __tablename__ = "job_match_scores"
    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 100", name="score_range"),
        Index(
            "uq_job_match_scores_offer_id_profile_id_weights_version",
            "offer_id",
            "profile_id",
            "weights_version",
            unique=True,
        ),
        Index("ix_job_match_scores_owner_id_score", "owner_id", "score"),
    )

    offer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_offers.id", ondelete="CASCADE"), index=True
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_profiles.id", ondelete="CASCADE"), index=True
    )
    score: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    # Détail par critère : correspondances, écarts, données manquantes (≠ compétences absentes).
    breakdown: Mapped[dict[str, Any]] = mapped_column(JSONB)
    weights_version: Mapped[str] = mapped_column(String(40))
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
