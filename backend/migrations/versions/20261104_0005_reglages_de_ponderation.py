"""réglages de pondération du score de correspondance

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-04 15:00:00.000000

Une table, additive : aucune donnée existante n'est touchée. Sans ligne pour un propriétaire,
les pondérations par défaut s'appliquent.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "matching_settings",
        sa.Column(
            "weights",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_matching_settings_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_matching_settings")),
    )
    op.create_index(
        op.f("ix_matching_settings_owner_id"), "matching_settings", ["owner_id"], unique=False
    )
    op.create_index("uq_matching_settings_owner_id", "matching_settings", ["owner_id"], unique=True)


def downgrade() -> None:
    op.drop_table("matching_settings")
