from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import Base, OwnedMixin, PrimaryKeyMixin, TimestampMixin, enum_check
from app.modules.candidate_profile.domain.enums import (
    DataOrigin,
    LanguageProficiency,
    ProfileStatus,
)

_PAYS = "country_code IS NULL OR country_code ~ '^[A-Z]{2}$'"


class CandidateModel(PrimaryKeyMixin, TimestampMixin, OwnedMixin, Base):
    """Identité professionnelle. Une seule par propriétaire."""

    __tablename__ = "candidates"
    __table_args__ = (
        CheckConstraint(_PAYS, name="country_code_format"),
        Index("uq_candidates_owner_id", "owner_id", unique=True),
    )

    first_name: Mapped[str] = mapped_column(String(120))
    last_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(40))
    city: Mapped[str | None] = mapped_column(String(120))
    country_code: Mapped[str | None] = mapped_column(String(2))
    headline: Mapped[str | None] = mapped_column(String(200))


class CandidateProfileModel(PrimaryKeyMixin, TimestampMixin, OwnedMixin, Base):
    """CV maître versionné. Une version validée n'est jamais écrasée par un CV adapté."""

    __tablename__ = "candidate_profiles"
    __table_args__ = (
        CheckConstraint("version >= 1", name="version_positive"),
        enum_check("status_valid", "status", ProfileStatus),
        Index("uq_candidate_profiles_candidate_id_version", "candidate_id", "version", unique=True),
    )

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), server_default=ProfileStatus.DRAFT.value)
    summary: Mapped[str | None] = mapped_column(Text)
    # Préférences professionnelles (métiers, pays, villes, télétravail, contrats, salaire, langues).
    preferences: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class _ProfileItemMixin(PrimaryKeyMixin, TimestampMixin, OwnedMixin):
    """Élément du profil : rattaché à une version, avec origine et date de validation."""

    source: Mapped[str] = mapped_column(String(20), server_default=DataOrigin.MANUAL.value)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


def _profile_fk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), ForeignKey("candidate_profiles.id", ondelete="CASCADE"), index=True
    )


class ExperienceModel(_ProfileItemMixin, Base):
    __tablename__ = "experiences"
    __table_args__ = (
        CheckConstraint("end_date IS NULL OR end_date >= start_date", name="period_valid"),
        enum_check("source_valid", "source", DataOrigin),
    )

    profile_id: Mapped[uuid.UUID] = _profile_fk()
    company: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(200))
    location: Mapped[str | None] = mapped_column(String(200))
    start_date: Mapped[date] = mapped_column()
    end_date: Mapped[date | None] = mapped_column()
    description: Mapped[str | None] = mapped_column(Text)
    achievements: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    position: Mapped[int] = mapped_column(Integer, server_default="0")


class EducationModel(_ProfileItemMixin, Base):
    __tablename__ = "educations"
    __table_args__ = (
        CheckConstraint(
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date", name="period_valid"
        ),
        enum_check("source_valid", "source", DataOrigin),
    )

    profile_id: Mapped[uuid.UUID] = _profile_fk()
    institution: Mapped[str] = mapped_column(String(200))
    degree: Mapped[str] = mapped_column(String(200))
    field_of_study: Mapped[str | None] = mapped_column(String(200))
    start_date: Mapped[date | None] = mapped_column()
    end_date: Mapped[date | None] = mapped_column()
    description: Mapped[str | None] = mapped_column(Text)


class CertificationModel(_ProfileItemMixin, Base):
    __tablename__ = "certifications"
    __table_args__ = (
        CheckConstraint(
            "expires_on IS NULL OR issued_on IS NULL OR expires_on >= issued_on",
            name="period_valid",
        ),
        enum_check("source_valid", "source", DataOrigin),
    )

    profile_id: Mapped[uuid.UUID] = _profile_fk()
    name: Mapped[str] = mapped_column(String(200))
    issuer: Mapped[str | None] = mapped_column(String(200))
    issued_on: Mapped[date | None] = mapped_column()
    expires_on: Mapped[date | None] = mapped_column()
    credential_url: Mapped[str | None] = mapped_column(Text)


class SkillModel(_ProfileItemMixin, Base):
    __tablename__ = "skills"
    __table_args__ = (
        enum_check("source_valid", "source", DataOrigin),
        CheckConstraint(
            "level IS NULL OR level IN ('beginner','intermediate','advanced','expert')",
            name="level_valid",
        ),
        # Une compétence par profil, sans tenir compte de la casse.
        Index(
            "uq_skills_profile_id_name_lower", "profile_id", func.lower(text("name")), unique=True
        ),
    )

    profile_id: Mapped[uuid.UUID] = _profile_fk()
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str | None] = mapped_column(String(80))
    # NULL = niveau non renseigné (différent de « débutant »).
    level: Mapped[str | None] = mapped_column(String(20))


class ProfileLanguageModel(_ProfileItemMixin, Base):
    __tablename__ = "profile_languages"
    __table_args__ = (
        enum_check("source_valid", "source", DataOrigin),
        enum_check("proficiency_valid", "proficiency", LanguageProficiency),
        CheckConstraint("language_code ~ '^[a-z]{2,3}(-[A-Z]{2})?$'", name="language_code_format"),
        Index(
            "uq_profile_languages_profile_id_language_code",
            "profile_id",
            "language_code",
            unique=True,
        ),
    )

    profile_id: Mapped[uuid.UUID] = _profile_fk()
    language_code: Mapped[str] = mapped_column(String(10))
    proficiency: Mapped[str] = mapped_column(String(10))
