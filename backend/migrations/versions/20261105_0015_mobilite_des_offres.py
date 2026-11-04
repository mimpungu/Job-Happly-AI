"""mobilité des offres : sponsoring de visa et autorisation de travail (TASK-017-17, 017-18)

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-05 12:00:00.000000

Colonnes additives et nullables : NULL = l'annonce n'en parle pas (ou pas encore analysée).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0015"
down_revision: str | Sequence[str] | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("job_offers", sa.Column("visa_sponsorship", sa.String(length=12), nullable=True))
    op.add_column("job_offers", sa.Column("work_authorization_required", sa.Boolean(), nullable=True))
    op.create_check_constraint(
        op.f("ck_job_offers_visa_sponsorship_valid"),
        "job_offers",
        "visa_sponsorship IS NULL OR visa_sponsorship IN ('offered', 'not_offered')",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(op.f("ck_job_offers_visa_sponsorship_valid"), "job_offers", type_="check")
    op.drop_column("job_offers", "work_authorization_required")
    op.drop_column("job_offers", "visa_sponsorship")
