from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import Base, OwnedMixin, PrimaryKeyMixin, TimestampMixin


class UserPreferencesModel(PrimaryKeyMixin, TimestampMixin, OwnedMixin, Base):
    """Préférences générales et de mobilité (TASK-017-01, 04, 05, 16, 17). NULL = non renseigné."""

    __tablename__ = "user_preferences"
    __table_args__ = (
        UniqueConstraint("owner_id", name="uq_user_preferences_owner_id"),
        CheckConstraint("ui_language IN ('fr', 'en')", name="ui_language_valid"),
        CheckConstraint(
            "country_code IS NULL OR country_code ~ '^[A-Z]{2}$'", name="country_code_format"
        ),
        CheckConstraint("currency IS NULL OR currency ~ '^[A-Z]{3}$'", name="currency_format"),
    )

    ui_language: Mapped[str] = mapped_column(String(5), server_default="fr")
    country_code: Mapped[str | None] = mapped_column(String(2))
    currency: Mapped[str | None] = mapped_column(String(3))
    timezone: Mapped[str | None] = mapped_column(String(60))
    willing_to_relocate: Mapped[bool | None] = mapped_column(Boolean)
    target_countries: Mapped[list[str]] = mapped_column(
        ARRAY(String(2)), server_default=text("'{}'")
    )
    work_permit_countries: Mapped[list[str]] = mapped_column(
        ARRAY(String(2)), server_default=text("'{}'")
    )
    needs_sponsorship: Mapped[bool | None] = mapped_column(Boolean)
