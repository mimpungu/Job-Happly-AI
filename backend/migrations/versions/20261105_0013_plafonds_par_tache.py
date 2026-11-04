"""plafonds journaliers par tâche IA (TASK-010-12)

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-05 10:00:00.000000

Table additive : sans ligne, seuls les plafonds globaux s'appliquent (comportement inchangé).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0013"
down_revision: str | Sequence[str] | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "ai_task_budgets",
        sa.Column("task_type", sa.String(length=60), nullable=False),
        sa.Column("daily_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
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
            "currency ~ '^[A-Z]{3}$'", name=op.f("ck_ai_task_budgets_currency_format")
        ),
        sa.CheckConstraint(
            "daily_amount > 0", name=op.f("ck_ai_task_budgets_daily_amount_positive")
        ),
        sa.CheckConstraint(
            "task_type ~ '^[a-z][a-z0-9_]{1,59}$'",
            name=op.f("ck_ai_task_budgets_task_type_format"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_ai_task_budgets_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_task_budgets")),
        sa.UniqueConstraint("owner_id", "task_type", name="uq_ai_task_budgets_owner_task"),
    )
    op.create_index(
        op.f("ix_ai_task_budgets_owner_id"), "ai_task_budgets", ["owner_id"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_ai_task_budgets_owner_id"), table_name="ai_task_budgets")
    op.drop_table("ai_task_budgets")
