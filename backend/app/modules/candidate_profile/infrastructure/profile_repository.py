"""Persistance SQL du profil maître versionné."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.candidate_profile.domain.enums import DataOrigin, ProfileStatus
from app.modules.candidate_profile.domain.profile import (
    CertificationDoc,
    Change,
    DocDate,
    EducationDoc,
    ExperienceDoc,
    Identity,
    LanguageDoc,
    Preferences,
    ProfileDocument,
    SkillDoc,
)
from app.modules.candidate_profile.domain.repository import (
    ChangeRecord,
    ProfileMeta,
    ProfileNotFoundError,
    StoredProfile,
    UnknownItemError,
)
from app.modules.candidate_profile.infrastructure.models import (
    CandidateModel,
    CandidateProfileModel,
    CertificationModel,
    EducationModel,
    ExperienceModel,
    ProfileChangeModel,
    ProfileLanguageModel,
    SkillModel,
)

# Les modèles sont manipulés de façon générique (même schéma : `profile_id`, `id`, dates…).
_ELEMENTS: tuple[tuple[str, Any], ...] = (
    ("experiences", ExperienceModel),
    ("educations", EducationModel),
    ("skills", SkillModel),
    ("languages", ProfileLanguageModel),
    ("certifications", CertificationModel),
)


# --- Document -> colonnes -----------------------------------------------------------------


def _colonnes_communes(element: Any, now: datetime, existant: Any | None) -> dict[str, Any]:
    # Une confirmation déjà enregistrée garde sa date ; une nouvelle prend `now`.
    ancienne = existant.validated_at if existant is not None else None
    return {
        "source": element.origin.value,
        "source_text": element.source_text,
        "validated_at": (ancienne or now) if element.validated else None,
    }


def _experience(e: ExperienceDoc, now: datetime, existant: Any | None) -> dict[str, Any]:
    return {
        **_colonnes_communes(e, now, existant),
        "title": e.title,
        "company": e.company,
        "location": e.location,
        "start_date": e.start.as_date() if e.start else None,
        "start_precision": e.start.precision if e.start else "month",
        "end_date": e.end.as_date() if e.end else None,
        "end_precision": e.end.precision if e.end else "month",
        "is_current": e.is_current,
        "description": e.description,
        "achievements": list(e.achievements),
    }


def _education(e: EducationDoc, now: datetime, existant: Any | None) -> dict[str, Any]:
    return {
        **_colonnes_communes(e, now, existant),
        "degree": e.degree,
        "institution": e.institution,
        "field_of_study": e.field_of_study,
        "start_date": e.start.as_date() if e.start else None,
        "start_precision": e.start.precision if e.start else "month",
        "end_date": e.end.as_date() if e.end else None,
        "end_precision": e.end.precision if e.end else "month",
        "description": e.description,
    }


def _skill(s: SkillDoc, now: datetime, existant: Any | None) -> dict[str, Any]:
    return {
        **_colonnes_communes(s, now, existant),
        "name": s.name,
        "category": s.category,
        "level": s.level.value if s.level else None,
    }


def _language(lg: LanguageDoc, now: datetime, existant: Any | None) -> dict[str, Any]:
    return {
        **_colonnes_communes(lg, now, existant),
        "language_code": lg.language_code,
        "proficiency": lg.proficiency.value if lg.proficiency else None,
        "level_text": lg.level_text,
    }


def _certification(c: CertificationDoc, now: datetime, existant: Any | None) -> dict[str, Any]:
    return {
        **_colonnes_communes(c, now, existant),
        "name": c.name,
        "issuer": c.issuer,
        "issued_on": c.issued_on.as_date() if c.issued_on else None,
        "issued_precision": c.issued_on.precision if c.issued_on else "month",
        "expires_on": c.expires_on.as_date() if c.expires_on else None,
        "expires_precision": c.expires_on.precision if c.expires_on else "month",
        "credential_url": c.credential_url,
    }


_CONVERTISSEURS: dict[str, Callable[[Any, datetime, Any | None], dict[str, Any]]] = {
    "experiences": _experience,
    "educations": _education,
    "skills": _skill,
    "languages": _language,
    "certifications": _certification,
}


# --- Colonnes -> document -----------------------------------------------------------------


def _commun(m: Any) -> dict[str, Any]:
    return {
        "id": m.id,
        "origin": DataOrigin(m.source),
        "validated": m.validated_at is not None,
        "source_text": m.source_text,
    }


def _vers_experience(m: ExperienceModel) -> ExperienceDoc:
    return ExperienceDoc(
        **_commun(m),
        title=m.title,
        company=m.company,
        location=m.location,
        start=DocDate.from_storage(m.start_date, m.start_precision),
        end=DocDate.from_storage(m.end_date, m.end_precision),
        is_current=m.is_current,
        description=m.description,
        achievements=tuple(m.achievements),
    )


def _vers_education(m: EducationModel) -> EducationDoc:
    return EducationDoc(
        **_commun(m),
        degree=m.degree,
        institution=m.institution,
        field_of_study=m.field_of_study,
        start=DocDate.from_storage(m.start_date, m.start_precision),
        end=DocDate.from_storage(m.end_date, m.end_precision),
        description=m.description,
    )


def _vers_skill(m: SkillModel) -> SkillDoc:
    return SkillDoc.model_validate(
        {**_commun(m), "name": m.name, "category": m.category, "level": m.level}
    )


def _vers_language(m: ProfileLanguageModel) -> LanguageDoc:
    return LanguageDoc.model_validate(
        {
            **_commun(m),
            "language_code": m.language_code,
            "proficiency": m.proficiency,
            "level_text": m.level_text,
        }
    )


def _vers_certification(m: CertificationModel) -> CertificationDoc:
    return CertificationDoc(
        **_commun(m),
        name=m.name,
        issuer=m.issuer,
        issued_on=DocDate.from_storage(m.issued_on, m.issued_precision),
        expires_on=DocDate.from_storage(m.expires_on, m.expires_precision),
        credential_url=m.credential_url,
    )


class SqlProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- Lecture ---------------------------------------------------------------------------

    async def latest(self, *, owner_id: uuid.UUID) -> StoredProfile | None:
        modele = await self._session.scalar(
            select(CandidateProfileModel)
            .where(CandidateProfileModel.owner_id == owner_id)
            .order_by(CandidateProfileModel.version.desc())
            .limit(1)
        )
        return await self._charger(modele) if modele else None

    async def get_version(self, *, owner_id: uuid.UUID, version: int) -> StoredProfile:
        modele = await self._session.scalar(
            select(CandidateProfileModel).where(
                CandidateProfileModel.owner_id == owner_id,
                CandidateProfileModel.version == version,
            )
        )
        if modele is None:
            raise ProfileNotFoundError(f"Version {version} introuvable.")
        return await self._charger(modele)

    async def list_versions(self, *, owner_id: uuid.UUID) -> tuple[ProfileMeta, ...]:
        lignes = await self._session.scalars(
            select(CandidateProfileModel)
            .where(CandidateProfileModel.owner_id == owner_id)
            .order_by(CandidateProfileModel.version.desc())
        )
        return tuple(_meta(m) for m in lignes)

    async def _charger(self, profil: CandidateProfileModel) -> StoredProfile:
        elements: dict[str, tuple[Any, ...]] = {}
        for nom, modele in _ELEMENTS:
            lignes = await self._session.scalars(
                select(modele)
                .where(modele.profile_id == profil.id)
                .order_by(modele.position, modele.id)
            )
            elements[nom] = tuple(lignes)
        document = ProfileDocument(
            identity=Identity.model_validate(profil.identity or {}),
            summary=profil.summary,
            experiences=tuple(_vers_experience(m) for m in elements["experiences"]),
            educations=tuple(_vers_education(m) for m in elements["educations"]),
            skills=tuple(_vers_skill(m) for m in elements["skills"]),
            languages=tuple(_vers_language(m) for m in elements["languages"]),
            certifications=tuple(_vers_certification(m) for m in elements["certifications"]),
            preferences=Preferences.model_validate(profil.preferences or {}),
        )
        return StoredProfile(_meta(profil), document)

    # --- Écriture --------------------------------------------------------------------------

    async def create_version(
        self, *, owner_id: uuid.UUID, document: ProfileDocument, version: int, now: datetime
    ) -> StoredProfile:
        candidat = await self._candidat(owner_id)
        profil = CandidateProfileModel(
            owner_id=owner_id,
            candidate_id=candidat.id,
            version=version,
            status=ProfileStatus.DRAFT.value,
            summary=document.summary,
            identity=document.identity.model_dump(mode="json"),
            preferences=document.preferences.model_dump(mode="json"),
        )
        self._session.add(profil)
        await self._session.flush()
        for nom, modele in _ELEMENTS:
            for position, element in enumerate(getattr(document, nom)):
                colonnes = _CONVERTISSEURS[nom](element, now, None)
                colonnes["position"] = position
                self._session.add(modele(owner_id=owner_id, profile_id=profil.id, **colonnes))
        await self._session.flush()
        await self._session.refresh(profil)
        return await self._charger(profil)

    async def replace_content(
        self,
        *,
        owner_id: uuid.UUID,
        profile_id: uuid.UUID,
        document: ProfileDocument,
        now: datetime,
    ) -> StoredProfile:
        profil = await self._profil(owner_id, profile_id)
        profil.summary = document.summary
        profil.identity = document.identity.model_dump(mode="json")
        profil.preferences = document.preferences.model_dump(mode="json")

        for nom, modele in _ELEMENTS:
            existants = {
                m.id: m
                for m in await self._session.scalars(
                    select(modele).where(modele.profile_id == profile_id)
                )
            }
            conserves: set[uuid.UUID] = set()
            for position, element in enumerate(getattr(document, nom)):
                existant = None
                if element.id is not None:
                    existant = existants.get(element.id)
                    if existant is None:
                        raise UnknownItemError(f"{nom} : identifiant inconnu {element.id}.")
                colonnes = _CONVERTISSEURS[nom](element, now, existant)
                colonnes["position"] = position
                if existant is None:
                    self._session.add(modele(owner_id=owner_id, profile_id=profile_id, **colonnes))
                else:
                    conserves.add(existant.id)
                    for champ, valeur in colonnes.items():
                        setattr(existant, champ, valeur)
            a_supprimer = set(existants) - conserves
            if a_supprimer:
                await self._session.execute(delete(modele).where(modele.id.in_(a_supprimer)))
        await self._session.flush()
        await self._session.refresh(profil)
        return await self._charger(profil)

    async def mark_validated(
        self, *, owner_id: uuid.UUID, profile_id: uuid.UUID, now: datetime
    ) -> StoredProfile:
        profil = await self._profil(owner_id, profile_id)
        profil.status = ProfileStatus.VALIDATED.value
        profil.validated_at = now
        # `candidates` reflète l'identité de la dernière version validée.
        candidat = await self._candidat(owner_id)
        identite = Identity.model_validate(profil.identity or {})
        for champ in (
            "first_name",
            "last_name",
            "email",
            "phone",
            "city",
            "country_code",
            "headline",
        ):
            setattr(candidat, champ, getattr(identite, champ))
        await self._session.flush()
        await self._session.refresh(profil)
        return await self._charger(profil)

    async def record_changes(
        self, *, owner_id: uuid.UUID, profile_id: uuid.UUID, changes: list[Change], now: datetime
    ) -> None:
        for changement in changes:
            self._session.add(
                ProfileChangeModel(
                    owner_id=owner_id,
                    profile_id=profile_id,
                    entity_type=changement.entity_type,
                    entity_id=changement.entity_id,
                    action=changement.action,
                    label=changement.label[:200] if changement.label else None,
                    changes=changement.changes,
                    created_at=now,
                )
            )
        await self._session.flush()

    async def list_changes(self, *, owner_id: uuid.UUID, limit: int) -> tuple[ChangeRecord, ...]:
        lignes = await self._session.execute(
            select(ProfileChangeModel, CandidateProfileModel.version)
            .join(CandidateProfileModel, CandidateProfileModel.id == ProfileChangeModel.profile_id)
            .where(ProfileChangeModel.owner_id == owner_id)
            .order_by(ProfileChangeModel.created_at.desc(), ProfileChangeModel.id.asc())
            .limit(limit)
        )
        return tuple(
            ChangeRecord(
                id=m.id,
                profile_version=version,
                created_at=m.created_at,
                entity_type=m.entity_type,
                entity_id=m.entity_id,
                action=m.action,
                label=m.label,
                changes=m.changes,
            )
            for m, version in lignes
        )

    # --- Utilitaires -----------------------------------------------------------------------

    async def _profil(self, owner_id: uuid.UUID, profile_id: uuid.UUID) -> CandidateProfileModel:
        profil = await self._session.scalar(
            select(CandidateProfileModel).where(
                CandidateProfileModel.id == profile_id, CandidateProfileModel.owner_id == owner_id
            )
        )
        if profil is None:
            raise ProfileNotFoundError(str(profile_id))
        return profil

    async def _candidat(self, owner_id: uuid.UUID) -> CandidateModel:
        candidat = await self._session.scalar(
            select(CandidateModel).where(CandidateModel.owner_id == owner_id)
        )
        if candidat is None:
            candidat = CandidateModel(owner_id=owner_id)
            self._session.add(candidat)
            await self._session.flush()
        return candidat


def _meta(m: CandidateProfileModel) -> ProfileMeta:
    return ProfileMeta(
        id=m.id,
        version=m.version,
        status=ProfileStatus(m.status),
        created_at=m.created_at,
        updated_at=m.updated_at,
        validated_at=m.validated_at,
    )
