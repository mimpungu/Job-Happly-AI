"""brouillon de profil (dates partielles, champs optionnels) et journal des modifications

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-04 09:00:00.000000

Assouplit le brouillon (un import peut ignorer l'entreprise, le mois ou le niveau de langue)
et rend la validation stricte par des contraintes `validated_is_complete`. Aucune donnée
existante n'est modifiée ; la descente exige qu'aucune ligne ne contienne de valeur nulle.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PRECISION = "IN ('year','month')"
_PROFICIENCY = "('a1','a2','b1','b2','c1','c2','native')"


_ELEMENTS = ("experiences", "educations", "skills", "profile_languages", "certifications")
# `experiences.position` existe depuis 0001 ; les autres éléments l'acquièrent ici.
_SANS_POSITION = ("educations", "skills", "profile_languages", "certifications")


def upgrade() -> None:
    op.add_column(
        "candidate_profiles",
        sa.Column(
            "identity",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    for table in _ELEMENTS:
        op.add_column(table, sa.Column("source_text", sa.Text(), nullable=True))
    for table in _SANS_POSITION:
        op.add_column(
            table, sa.Column("position", sa.Integer(), server_default="0", nullable=False)
        )
    op.alter_column("candidates", "first_name", existing_type=sa.String(120), nullable=True)
    op.alter_column("candidates", "last_name", existing_type=sa.String(120), nullable=True)

    # Expériences
    op.drop_constraint(op.f("ck_experiences_period_valid"), "experiences", type_="check")
    op.alter_column("experiences", "company", existing_type=sa.String(200), nullable=True)
    op.alter_column("experiences", "title", existing_type=sa.String(200), nullable=True)
    op.alter_column("experiences", "start_date", existing_type=sa.Date(), nullable=True)
    for colonne in ("start_precision", "end_precision"):
        op.add_column(
            "experiences",
            sa.Column(colonne, sa.String(5), server_default="month", nullable=False),
        )
    op.add_column(
        "experiences",
        sa.Column("is_current", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_experiences_period_valid"),
        "experiences",
        "end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
    )
    op.create_check_constraint(
        op.f("ck_experiences_start_precision_valid"), "experiences", f"start_precision {_PRECISION}"
    )
    op.create_check_constraint(
        op.f("ck_experiences_end_precision_valid"), "experiences", f"end_precision {_PRECISION}"
    )
    op.create_check_constraint(
        op.f("ck_experiences_current_has_no_end"),
        "experiences",
        "NOT is_current OR end_date IS NULL",
    )
    op.create_check_constraint(
        op.f("ck_experiences_validated_is_complete"),
        "experiences",
        "validated_at IS NULL OR "
        "(company IS NOT NULL AND title IS NOT NULL AND start_date IS NOT NULL)",
    )

    # Formations
    op.alter_column("educations", "institution", existing_type=sa.String(200), nullable=True)
    op.alter_column("educations", "degree", existing_type=sa.String(200), nullable=True)
    for colonne in ("start_precision", "end_precision"):
        op.add_column(
            "educations",
            sa.Column(colonne, sa.String(5), server_default="month", nullable=False),
        )
    op.create_check_constraint(
        op.f("ck_educations_start_precision_valid"), "educations", f"start_precision {_PRECISION}"
    )
    op.create_check_constraint(
        op.f("ck_educations_end_precision_valid"), "educations", f"end_precision {_PRECISION}"
    )
    op.create_check_constraint(
        op.f("ck_educations_validated_is_complete"),
        "educations",
        "validated_at IS NULL OR (institution IS NOT NULL AND degree IS NOT NULL)",
    )

    # Certifications : précision des dates
    for colonne in ("issued_precision", "expires_precision"):
        op.add_column(
            "certifications",
            sa.Column(colonne, sa.String(5), server_default="month", nullable=False),
        )
        op.create_check_constraint(
            op.f(f"ck_certifications_{colonne}_valid"), "certifications", f"{colonne} {_PRECISION}"
        )

    # Langues
    op.drop_constraint(
        op.f("ck_profile_languages_proficiency_valid"), "profile_languages", type_="check"
    )
    op.alter_column("profile_languages", "proficiency", existing_type=sa.String(10), nullable=True)
    op.add_column("profile_languages", sa.Column("level_text", sa.String(80), nullable=True))
    op.create_check_constraint(
        op.f("ck_profile_languages_proficiency_valid"),
        "profile_languages",
        f"proficiency IS NULL OR proficiency IN {_PROFICIENCY}",
    )
    op.create_check_constraint(
        op.f("ck_profile_languages_validated_is_complete"),
        "profile_languages",
        "validated_at IS NULL OR proficiency IS NOT NULL",
    )

    op.create_table(
        "profile_changes",
        sa.Column("profile_id", sa.UUID(), nullable=False),
        sa.Column("entity_type", sa.String(20), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.String(10), nullable=False),
        sa.Column("label", sa.String(200), nullable=True),
        sa.Column(
            "changes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "entity_type IN ('identity','summary','preferences','experience','education',"
            "'skill','language','certification','profile')",
            name=op.f("ck_profile_changes_entity_type_valid"),
        ),
        sa.CheckConstraint(
            "action IN ('create','update','delete','validate','import')",
            name=op.f("ck_profile_changes_action_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_profile_changes_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["candidate_profiles.id"],
            name=op.f("fk_profile_changes_profile_id_candidate_profiles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_profile_changes")),
    )
    op.create_index(
        op.f("ix_profile_changes_owner_id"), "profile_changes", ["owner_id"], unique=False
    )
    op.create_index(
        "ix_profile_changes_profile_id_created_at",
        "profile_changes",
        ["profile_id", sa.text("created_at DESC")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("profile_changes")
    op.drop_column("candidate_profiles", "identity")
    for table in _ELEMENTS:
        op.drop_column(table, "source_text")
    for table in _SANS_POSITION:
        op.drop_column(table, "position")

    op.drop_constraint(
        op.f("ck_profile_languages_validated_is_complete"), "profile_languages", type_="check"
    )
    op.drop_constraint(
        op.f("ck_profile_languages_proficiency_valid"), "profile_languages", type_="check"
    )
    for colonne in ("issued_precision", "expires_precision"):
        op.drop_constraint(
            op.f(f"ck_certifications_{colonne}_valid"), "certifications", type_="check"
        )
        op.drop_column("certifications", colonne)
    op.drop_column("profile_languages", "level_text")
    op.alter_column("profile_languages", "proficiency", existing_type=sa.String(10), nullable=False)
    op.create_check_constraint(
        op.f("ck_profile_languages_proficiency_valid"),
        "profile_languages",
        f"proficiency IN {_PROFICIENCY}",
    )

    for contrainte in ("validated_is_complete", "end_precision_valid", "start_precision_valid"):
        op.drop_constraint(op.f(f"ck_educations_{contrainte}"), "educations", type_="check")
    op.drop_column("educations", "end_precision")
    op.drop_column("educations", "start_precision")
    op.alter_column("educations", "degree", existing_type=sa.String(200), nullable=False)
    op.alter_column("educations", "institution", existing_type=sa.String(200), nullable=False)

    for contrainte in (
        "validated_is_complete",
        "current_has_no_end",
        "end_precision_valid",
        "start_precision_valid",
        "period_valid",
    ):
        op.drop_constraint(op.f(f"ck_experiences_{contrainte}"), "experiences", type_="check")
    op.drop_column("experiences", "is_current")
    op.drop_column("experiences", "end_precision")
    op.drop_column("experiences", "start_precision")
    op.alter_column("experiences", "start_date", existing_type=sa.Date(), nullable=False)
    op.alter_column("experiences", "title", existing_type=sa.String(200), nullable=False)
    op.alter_column("experiences", "company", existing_type=sa.String(200), nullable=False)
    op.create_check_constraint(
        op.f("ck_experiences_period_valid"),
        "experiences",
        "end_date IS NULL OR end_date >= start_date",
    )

    op.alter_column("candidates", "last_name", existing_type=sa.String(120), nullable=False)
    op.alter_column("candidates", "first_name", existing_type=sa.String(120), nullable=False)
