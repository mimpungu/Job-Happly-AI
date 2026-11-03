"""Utilisateur local (ADR-0008) : propriétaire de toutes les données."""

from __future__ import annotations

from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import Base, CreatedAtMixin, PrimaryKeyMixin


class UserModel(PrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "users"

    display_name: Mapped[str | None] = mapped_column(nullable=True)
