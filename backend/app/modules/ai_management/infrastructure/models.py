from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import (
    Base,
    CreatedAtMixin,
    OwnedMixin,
    PrimaryKeyMixin,
    TimestampMixin,
    enum_check,
)
from app.modules.ai_management.domain.enums import BudgetPeriod, CallOutcome

_DEVISE = "currency ~ '^[A-Z]{3}$'"


class AIUsageModel(PrimaryKeyMixin, CreatedAtMixin, OwnedMixin, Base):
    """Journal de chaque appel IA (y compris refusés et servis par le cache)."""

    __tablename__ = "ai_usages"
    __table_args__ = (
        enum_check("outcome_valid", "outcome", CallOutcome),
        CheckConstraint("level BETWEEN 0 AND 2", name="level_range"),
        CheckConstraint("input_tokens >= 0 AND output_tokens >= 0", name="tokens_positive"),
        CheckConstraint("estimated_cost >= 0", name="estimated_cost_positive"),
        CheckConstraint("actual_cost IS NULL OR actual_cost >= 0", name="actual_cost_positive"),
        CheckConstraint("duration_ms >= 0", name="duration_positive"),
        CheckConstraint(_DEVISE, name="currency_format"),
        Index("ix_ai_usages_owner_id_created_at", "owner_id", text("created_at DESC")),
        Index("ix_ai_usages_owner_id_provider_created_at", "owner_id", "provider", "created_at"),
        Index("ix_ai_usages_operation_id", "operation_id"),
    )

    provider: Mapped[str] = mapped_column(String(60))
    model: Mapped[str] = mapped_column(String(120))
    task_type: Mapped[str] = mapped_column(String(80))
    level: Mapped[int] = mapped_column(SmallInteger)
    input_tokens: Mapped[int] = mapped_column(Integer, server_default="0")
    output_tokens: Mapped[int] = mapped_column(Integer, server_default="0")
    estimated_cost: Mapped[Decimal] = mapped_column(Numeric(12, 6), server_default="0")
    actual_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    currency: Mapped[str] = mapped_column(String(3))
    duration_ms: Mapped[int] = mapped_column(Integer, server_default="0")
    operation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    outcome: Mapped[str] = mapped_column(String(20))
    cache_hit: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))


class AIBudgetModel(PrimaryKeyMixin, TimestampMixin, OwnedMixin, Base):
    """Plafonds de dépense. Aucun appel payant sans plafond défini (ADR-0005)."""

    __tablename__ = "ai_budgets"
    __table_args__ = (
        enum_check("period_valid", "period", BudgetPeriod),
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint(_DEVISE, name="currency_format"),
        # `provider` NULL = plafond global ; deux plafonds globaux de même période sont interdits.
        UniqueConstraint(
            "owner_id",
            "period",
            "provider",
            name="uq_ai_budgets_owner_period_provider",
            postgresql_nulls_not_distinct=True,
        ),
    )

    period: Mapped[str] = mapped_column(String(20))
    provider: Mapped[str | None] = mapped_column(String(60))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3))
    alert_thresholds: Mapped[list[int]] = mapped_column(
        ARRAY(SmallInteger), server_default=text("'{50,80,100}'")
    )


class AICacheEntryModel(PrimaryKeyMixin, CreatedAtMixin, OwnedMixin, Base):
    __tablename__ = "ai_cache_entries"
    __table_args__ = (
        CheckConstraint("hit_count >= 0", name="hit_count_positive"),
        Index("uq_ai_cache_entries_owner_id_cache_key", "owner_id", "cache_key", unique=True),
        Index(
            "ix_ai_cache_entries_expires_at",
            "expires_at",
            postgresql_where=text("expires_at IS NOT NULL"),
        ),
    )

    # Empreinte de (tâche, version du prompt, modèle, contenu).
    cache_key: Mapped[str] = mapped_column(String(128))
    task_type: Mapped[str] = mapped_column(String(80))
    prompt_version: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(120))
    result: Mapped[dict[str, Any]] = mapped_column(JSONB)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    hit_count: Mapped[int] = mapped_column(Integer, server_default="0")
