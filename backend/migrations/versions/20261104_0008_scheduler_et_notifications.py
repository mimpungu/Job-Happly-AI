"""tables des préférences de notification et des tâches planifiées (EPIC 015)

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-04 22:00:00.000000

Deux tables additives :
- notification_preferences : réglages par propriétaire (canaux, alertes, heure du résumé, fuseau).
- scheduled_tasks : définitions des tâches récurrentes planifiées et prochaines exécutions.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_preferences",
        sa.Column("in_app_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("email_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("email_recipient", sa.String(length=320), nullable=True),
        sa.Column(
            "email_consent_given", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "notify_new_offers", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column(
            "notify_relevant_matches", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column("min_relevance_score", sa.Integer(), server_default="70", nullable=False),
        sa.Column(
            "notify_search_errors", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column(
            "notify_follow_up_reminders",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "notify_ai_budget_alerts", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column(
            "daily_digest_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column(
            "daily_digest_time", sa.String(length=10), server_default="08:00", nullable=False
        ),
        sa.Column("timezone", sa.String(length=60), server_default="Europe/Paris", nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "min_relevance_score >= 0 AND min_relevance_score <= 100",
            name=op.f("ck_notification_preferences_min_relevance_score_range"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_notification_preferences_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_preferences")),
    )
    op.create_index(
        op.f("ix_notification_preferences_owner_id"),
        "notification_preferences",
        ["owner_id"],
        unique=False,
    )
    op.create_index(
        "uq_notification_preferences_owner_id",
        "notification_preferences",
        ["owner_id"],
        unique=True,
    )

    op.create_table(
        "scheduled_tasks",
        sa.Column("owner_id", sa.UUID(), nullable=True),
        sa.Column("task_type", sa.String(length=60), nullable=False),
        sa.Column("frequency", sa.String(length=30), nullable=False),
        sa.Column("interval_minutes", sa.Integer(), nullable=True),
        sa.Column("target_hour", sa.Integer(), nullable=True),
        sa.Column("target_minute", sa.Integer(), nullable=True),
        sa.Column("timezone", sa.String(length=60), server_default="Europe/Paris", nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
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
            name=op.f("fk_scheduled_tasks_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scheduled_tasks")),
    )
    op.create_index(
        op.f("ix_scheduled_tasks_owner_id"), "scheduled_tasks", ["owner_id"], unique=False
    )
    op.create_index(
        "ix_scheduled_tasks_enabled_next_run_at",
        "scheduled_tasks",
        ["enabled", "next_run_at"],
        unique=False,
    )
    op.create_index(
        "ix_scheduled_tasks_owner_id_task_type",
        "scheduled_tasks",
        ["owner_id", "task_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("scheduled_tasks")
    op.drop_table("notification_preferences")
