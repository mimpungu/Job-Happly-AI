"""expérience exigée des offres (TASK-008-08)

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-05 09:00:00.000000

Colonne additive et nullable : NULL = inconnu. Les offres existantes sont renseignées à leur
prochaine observation ; d'ici là, elles restent incluses par le filtre (jamais exclues à tort).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0012"
down_revision: str | Sequence[str] | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("job_offers", sa.Column("required_experience_years", sa.SmallInteger()))
    op.create_check_constraint(
        op.f("ck_job_offers_required_experience_valid"),
        "job_offers",
        "required_experience_years IS NULL OR required_experience_years BETWEEN 0 AND 40",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(op.f("ck_job_offers_required_experience_valid"), "job_offers", type_="check")
    op.drop_column("job_offers", "required_experience_years")
