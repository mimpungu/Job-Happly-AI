"""ats ashby et workable : élargir les contraintes des entreprises suivies (TASK-006-23)

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-05 18:00:00.000000

Seules deux contraintes CHECK changent : aucune donnée ni colonne n'est modifiée. Le retour
arrière échoue volontairement si des entreprises Ashby ou Workable existent encore (elles
violeraient l'ancienne contrainte) : on ne les supprime jamais en silence.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0016"
down_revision: str | Sequence[str] | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "target_companies"
# Noms déjà complets (convention appliquée par la migration 0002) : `op.f` les garde tels quels,
# mais ne peut être appelé qu'à l'intérieur d'une opération, pas au chargement du module.
_TYPE = "ck_target_companies_ats_kind_valid"
_JETON = "ck_target_companies_ats_requires_token"


def _remplacer(types_avec_jeton: str, tous_les_types: str) -> None:
    op.drop_constraint(op.f(_TYPE), _TABLE, type_="check")
    op.drop_constraint(op.f(_JETON), _TABLE, type_="check")
    op.create_check_constraint(
        op.f(_TYPE), _TABLE, f"ats_kind IS NULL OR ats_kind IN ({tous_les_types})"
    )
    op.create_check_constraint(
        op.f(_JETON), _TABLE, f"ats_kind NOT IN ({types_avec_jeton}) OR ats_token IS NOT NULL"
    )


def upgrade() -> None:
    """Upgrade schema."""
    _remplacer(
        "'greenhouse','lever','ashby','workable'",
        "'greenhouse','lever','ashby','workable','careers_page','unsupported'",
    )


def downgrade() -> None:
    """Downgrade schema."""
    _remplacer("'greenhouse','lever'", "'greenhouse','lever','careers_page','unsupported'")
