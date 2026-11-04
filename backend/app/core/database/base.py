"""Base déclarative, conventions de nommage et mixins communs des tables."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, MetaData, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

# Conventions explicites : les noms de contraintes et d'index sont déterministes, donc stables
# dans les migrations Alembic.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class PrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TimestampMixin(CreatedAtMixin):
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class OwnedMixin:
    """Toute donnée de l'utilisateur porte un `owner_id` (ADR-0008).

    Supprimer l'utilisateur supprime ses données (droit à l'effacement, RGPD).
    """

    @declared_attr
    def owner_id(cls) -> Mapped[uuid.UUID]:
        return mapped_column(
            UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )


def enum_check(constraint_name: str, column: str, enum_cls: type[StrEnum]) -> CheckConstraint:
    """Contrainte CHECK limitant une colonne texte aux valeurs d'une énumération.

    Préféré aux types ENUM PostgreSQL : ajouter une valeur ne demande pas de migration de type.
    """
    valeurs = ", ".join(f"'{membre.value}'" for membre in enum_cls)
    return CheckConstraint(f"{column} IN ({valeurs})", name=constraint_name)
