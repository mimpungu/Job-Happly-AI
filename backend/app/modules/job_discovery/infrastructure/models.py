from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import (
    Base,
    CreatedAtMixin,
    OwnedMixin,
    PrimaryKeyMixin,
    TimestampMixin,
    enum_check,
)
from app.core.domain.value_objects import EmploymentType, RemoteType
from app.modules.job_discovery.domain.enums import (
    OfferState,
    OfferStatus,
    SearchRunStatus,
    SourceKind,
)


class JobSourceModel(PrimaryKeyMixin, TimestampMixin, OwnedMixin, Base):
    """Source d'offres configurée. `enabled=False` ne supprime ni l'historique ni les offres."""

    __tablename__ = "job_sources"
    __table_args__ = (
        enum_check("kind_valid", "kind", SourceKind),
        Index("uq_job_sources_owner_id_key", "owner_id", "key", unique=True),
    )

    key: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20))
    countries: Mapped[list[str]] = mapped_column(ARRAY(String(2)), server_default=text("'{}'"))
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    requires_api_key: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)


class JobOfferModel(PrimaryKeyMixin, TimestampMixin, OwnedMixin, Base):
    """Offre normalisée (fiche unique, éventuellement vue sur plusieurs sources).

    Les données d'origine sont conservées dans `job_offer_sources.raw_payload`.
    Une information absente est NULL, jamais 0 ni chaîne vide.
    """

    __tablename__ = "job_offers"
    __table_args__ = (
        enum_check("status_valid", "status", OfferStatus),
        CheckConstraint(
            "employment_type IS NULL OR employment_type IN "
            + "("
            + ",".join(f"'{m.value}'" for m in EmploymentType)
            + ")",
            name="employment_type_valid",
        ),
        CheckConstraint(
            "remote_type IS NULL OR remote_type IN "
            + "("
            + ",".join(f"'{m.value}'" for m in RemoteType)
            + ")",
            name="remote_type_valid",
        ),
        CheckConstraint(
            "country_code IS NULL OR country_code ~ '^[A-Z]{2}$'", name="country_code_format"
        ),
        CheckConstraint(
            "salary_currency IS NULL OR salary_currency ~ '^[A-Z]{3}$'",
            name="salary_currency_format",
        ),
        CheckConstraint(
            "salary_min IS NULL OR salary_max IS NULL OR salary_max >= salary_min",
            name="salary_range_valid",
        ),
        CheckConstraint(
            "(salary_min IS NULL AND salary_max IS NULL) OR salary_currency IS NOT NULL",
            name="salary_requires_currency",
        ),
        CheckConstraint("salary_min IS NULL OR salary_min >= 0", name="salary_min_positive"),
        CheckConstraint(
            "required_experience_years IS NULL OR required_experience_years BETWEEN 0 AND 40",
            name="required_experience_valid",
        ),
        CheckConstraint(
            "visa_sponsorship IS NULL OR visa_sponsorship IN ('offered', 'not_offered')",
            name="visa_sponsorship_valid",
        ),
        CheckConstraint("char_length(content_hash) = 64", name="content_hash_sha256"),
        CheckConstraint("last_seen_at >= first_seen_at", name="seen_dates_valid"),
        Index("ix_job_offers_owner_id_country_code", "owner_id", "country_code"),
        Index(
            "ix_job_offers_owner_id_published_at", "owner_id", text("published_at DESC NULLS LAST")
        ),
        Index("ix_job_offers_owner_id_title_lower", "owner_id", func.lower(text("title"))),
        Index("ix_job_offers_owner_id_company_lower", "owner_id", func.lower(text("company_name"))),
        Index("ix_job_offers_owner_id_status", "owner_id", "status"),
        Index("ix_job_offers_owner_id_content_hash", "owner_id", "content_hash"),
        Index(
            "uq_job_offers_owner_id_canonical_url",
            "owner_id",
            "canonical_url",
            unique=True,
            postgresql_where=text("canonical_url IS NOT NULL"),
        ),
    )

    primary_source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_sources.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(300))
    company_name: Mapped[str | None] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(300))
    country_code: Mapped[str | None] = mapped_column(String(2))
    employment_type: Mapped[str | None] = mapped_column(String(20))
    remote_type: Mapped[str | None] = mapped_column(String(20))
    salary_min: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    salary_max: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    salary_currency: Mapped[str | None] = mapped_column(String(3))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    application_url: Mapped[str] = mapped_column(Text)
    canonical_url: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(10))
    # Années d'expérience exigées, déduites de l'annonce ; NULL = inconnu (jamais 0 par défaut).
    required_experience_years: Mapped[int | None] = mapped_column(SmallInteger)
    # Mobilité (TASK-017-17/18), déduite de l'annonce ; NULL = l'annonce n'en parle pas.
    visa_sponsorship: Mapped[str | None] = mapped_column(String(12))
    work_authorization_required: Mapped[bool | None] = mapped_column(Boolean)
    # Offre fictive du mode démonstration (TASK-002-10) : jamais mêlée aux données réelles.
    is_demo: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    content_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), server_default=OfferStatus.ACTIVE.value)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class JobOfferSourceModel(PrimaryKeyMixin, CreatedAtMixin, OwnedMixin, Base):
    """Observation d'une offre sur une source : attribution, date de récupération, donnée brute."""

    __tablename__ = "job_offer_sources"
    __table_args__ = (
        Index(
            "uq_job_offer_sources_owner_id_source_id_external_id",
            "owner_id",
            "source_id",
            "external_id",
            unique=True,
        ),
    )

    offer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_offers.id", ondelete="CASCADE"), index=True
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_sources.id", ondelete="RESTRICT"), index=True
    )
    external_id: Mapped[str] = mapped_column(String(300))
    source_url: Mapped[str | None] = mapped_column(Text)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # Renseigné quand la source, parcourue entièrement, ne présente plus cette offre ;
    # effacé si elle réapparaît.
    gone_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class JobOfferRevisionModel(PrimaryKeyMixin, CreatedAtMixin, OwnedMixin, Base):
    """Historique des modifications d'une offre : état précédent conservé à chaque changement."""

    __tablename__ = "job_offer_revisions"
    __table_args__ = (
        CheckConstraint("char_length(content_hash) = 64", name="content_hash_sha256"),
        Index("ix_job_offer_revisions_offer_id_observed_at", "offer_id", "observed_at"),
    )

    offer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_offers.id", ondelete="CASCADE")
    )
    content_hash: Mapped[str] = mapped_column(String(64))
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class JobOfferStateModel(PrimaryKeyMixin, TimestampMixin, OwnedMixin, Base):
    """Offre sauvegardée ou ignorée par l'utilisateur."""

    __tablename__ = "job_offer_states"
    __table_args__ = (
        enum_check("state_valid", "state", OfferState),
        Index("uq_job_offer_states_owner_id_offer_id", "owner_id", "offer_id", unique=True),
    )

    offer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_offers.id", ondelete="CASCADE")
    )
    state: Mapped[str] = mapped_column(String(20))


class SavedSearchModel(PrimaryKeyMixin, TimestampMixin, OwnedMixin, Base):
    __tablename__ = "saved_searches"
    __table_args__ = (
        Index(
            "uq_saved_searches_owner_id_name_lower",
            "owner_id",
            func.lower(text("name")),
            unique=True,
        ),
    )

    name: Mapped[str] = mapped_column(String(200))
    # Critères (SearchCriteria) validés par le domaine avant stockage.
    criteria: Mapped[dict[str, Any]] = mapped_column(JSONB)
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class SearchRunModel(PrimaryKeyMixin, CreatedAtMixin, OwnedMixin, Base):
    """Historique d'exécution des recherches."""

    __tablename__ = "search_runs"
    __table_args__ = (
        enum_check("status_valid", "status", SearchRunStatus),
        CheckConstraint("result_count IS NULL OR result_count >= 0", name="result_count_positive"),
        CheckConstraint(
            "finished_at IS NULL OR finished_at >= started_at", name="finished_after_started"
        ),
        Index("ix_search_runs_owner_id_started_at", "owner_id", text("started_at DESC")),
    )

    saved_search_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("saved_searches.id", ondelete="SET NULL"), index=True
    )
    criteria: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), server_default=SearchRunStatus.RUNNING.value)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_count: Mapped[int | None] = mapped_column(Integer)
    # Résultat par source : succès, échec, nombre d'offres. Une source en échec
    # n'arrête pas les autres.
    source_outcomes: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb")
    )


class TargetCompanyModel(PrimaryKeyMixin, TimestampMixin, OwnedMixin, Base):
    """Entreprise suivie. La lecture de pages publiques exige une vérification humaine des CGU."""

    __tablename__ = "target_companies"
    __table_args__ = (
        CheckConstraint(
            "ats_kind IS NULL OR ats_kind IN ('greenhouse','lever','careers_page','unsupported')",
            name="ats_kind_valid",
        ),
        CheckConstraint(
            "detection_status IN ('pending','supported','unsupported')",
            name="detection_status_valid",
        ),
        CheckConstraint(
            "ats_kind NOT IN ('greenhouse','lever') OR ats_token IS NOT NULL",
            name="ats_requires_token",
        ),
        CheckConstraint(
            "enabled = false OR detection_status = 'supported'", name="enabled_requires_supported"
        ),
        CheckConstraint(
            "NOT (enabled AND ats_kind = 'careers_page') OR tos_verified_at IS NOT NULL",
            name="careers_page_requires_tos_check",
        ),
        Index(
            "uq_target_companies_owner_id_name_lower",
            "owner_id",
            func.lower(text("name")),
            unique=True,
        ),
    )

    name: Mapped[str] = mapped_column(String(200))
    careers_url: Mapped[str | None] = mapped_column(Text)
    ats_kind: Mapped[str | None] = mapped_column(String(20))
    ats_token: Mapped[str | None] = mapped_column(String(100))
    ats_region: Mapped[str | None] = mapped_column(String(10))
    detection_method: Mapped[str | None] = mapped_column(String(40))
    detection_status: Mapped[str] = mapped_column(String(20), server_default="pending")
    detected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    # Date à laquelle une personne a lu les CGU et robots.txt du site (pages non ATS).
    tos_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
