"""type de source « manuelle » (offres saisies par l'utilisateur)

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-04 18:00:00.000000

Élargit la contrainte CHECK de `job_sources.kind` : aucune donnée existante n'est modifiée ni
supprimée. Le retour arrière échoue volontairement s'il existe déjà une source manuelle (il
faudrait supprimer des données, ce qui exige une décision humaine).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NOM = "ck_job_sources_kind_valid"


def upgrade() -> None:
    op.drop_constraint(op.f(_NOM), "job_sources", type_="check")
    op.create_check_constraint(
        op.f(_NOM), "job_sources", "kind IN ('official_api', 'public_ats', 'public_page', 'manual')"
    )


def downgrade() -> None:
    op.drop_constraint(op.f(_NOM), "job_sources", type_="check")
    op.create_check_constraint(
        op.f(_NOM), "job_sources", "kind IN ('official_api', 'public_ats', 'public_page')"
    )
