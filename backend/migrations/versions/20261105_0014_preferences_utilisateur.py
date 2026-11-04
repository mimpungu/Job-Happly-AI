"""préférences générales et de mobilité (TASK-017-01, 04, 05, 16, 17)

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-05 11:00:00.000000

Table additive : sans ligne, l'application garde son comportement actuel (français, aucun pays).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0014"
down_revision: str | Sequence[str] | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "user_preferences",
        sa.Column("ui_language", sa.String(length=5), server_default="fr", nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("timezone", sa.String(length=60), nullable=True),
        sa.Column("willing_to_relocate", sa.Boolean(), nullable=True),
        sa.Column(
            "target_countries",
            postgresql.ARRAY(sa.String(length=2)),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "work_permit_countries",
            postgresql.ARRAY(sa.String(length=2)),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("needs_sponsorship", sa.Boolean(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "country_code IS NULL OR country_code ~ '^[A-Z]{2}$'",
            name=op.f("ck_user_preferences_country_code_format"),
        ),
        sa.CheckConstraint(
            "currency IS NULL OR currency ~ '^[A-Z]{3}$'",
            name=op.f("ck_user_preferences_currency_format"),
        ),
        sa.CheckConstraint(
            "ui_language IN ('fr', 'en')", name=op.f("ck_user_preferences_ui_language_valid")
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_user_preferences_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_preferences")),
        sa.UniqueConstraint("owner_id", name="uq_user_preferences_owner_id"),
    )
    op.create_index(
        op.f("ix_user_preferences_owner_id"), "user_preferences", ["owner_id"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_user_preferences_owner_id"), table_name="user_preferences")
    op.drop_table("user_preferences")
