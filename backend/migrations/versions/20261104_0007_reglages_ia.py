"""réglages de la plateforme IA (mode, préférence local/API, limites, consentement)

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-04 20:00:00.000000

Une table, additive. Sans ligne pour un propriétaire : IA économique, hybride, aucun plafond
défini (donc aucun appel payant possible) et aucun consentement.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_settings",
        sa.Column("mode", sa.String(20), server_default="economy", nullable=False),
        sa.Column("backend_preference", sa.String(20), server_default="hybrid", nullable=False),
        sa.Column("per_operation_level1", sa.Numeric(12, 4), server_default="0.02", nullable=False),
        sa.Column("per_operation_level2", sa.Numeric(12, 4), server_default="0.30", nullable=False),
        sa.Column("currency", sa.String(3), server_default="EUR", nullable=False),
        sa.Column("api_consent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "mode IN ('disabled', 'economy', 'balanced', 'quality')",
            name=op.f("ck_ai_settings_mode_valid"),
        ),
        sa.CheckConstraint(
            "backend_preference IN ('local_only', 'api_only', 'hybrid')",
            name=op.f("ck_ai_settings_backend_preference_valid"),
        ),
        sa.CheckConstraint(
            "per_operation_level1 > 0 AND per_operation_level2 > 0",
            name=op.f("ck_ai_settings_per_operation_positive"),
        ),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name=op.f("ck_ai_settings_currency_format")),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_ai_settings_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_settings")),
    )
    op.create_index(op.f("ix_ai_settings_owner_id"), "ai_settings", ["owner_id"], unique=False)
    op.create_index("uq_ai_settings_owner_id", "ai_settings", ["owner_id"], unique=True)


def downgrade() -> None:
    op.drop_table("ai_settings")
