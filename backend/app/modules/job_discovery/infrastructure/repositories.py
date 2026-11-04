"""Repositories SQL du contexte job_discovery.

Les repositories ne valident jamais la transaction : c'est le rôle de l'unité de travail.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import exists, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain.value_objects import CountryCode, EmploymentType, RemoteType
from app.modules.application_management.infrastructure.models import ApplicationModel
from app.modules.job_discovery.domain.deduplication import assess_duplicate, canonicalize_url
from app.modules.job_discovery.domain.enums import OfferState, OfferStatus
from app.modules.job_discovery.domain.offers import NormalizedOffer, UpsertResult
from app.modules.job_discovery.infrastructure.models import (
    JobOfferModel,
    JobOfferRevisionModel,
    JobOfferSourceModel,
    JobOfferStateModel,
)
from app.modules.job_intelligence.domain.matching.offer_requirements import extraire_annees

MAX_CANDIDATS_DOUBLON = 50


def _annees_requises(description: str) -> int | None:
    """Expérience exigée déduite de l'annonce ; `None` si l'annonce n'en parle pas."""
    exigence = extraire_annees(description)
    return exigence.years if exigence else None


def _champs_offre(offre: NormalizedOffer) -> dict[str, Any]:
    return {
        "required_experience_years": _annees_requises(offre.description),
        "title": offre.title,
        "description": offre.description,
        "application_url": offre.application_url,
        "content_hash": offre.content_hash,
        "company_name": offre.company_name,
        "location": offre.location,
        "country_code": offre.country_code.value if offre.country_code else None,
        "employment_type": offre.employment_type.value if offre.employment_type else None,
        "remote_type": offre.remote_type.value if offre.remote_type else None,
        "salary_min": offre.salary_min,
        "salary_max": offre.salary_max,
        "salary_currency": offre.salary_currency,
        "published_at": offre.published_at,
        "expires_at": offre.expires_at,
        "canonical_url": canonicalize_url(offre.canonical_url) if offre.canonical_url else None,
        "language": offre.language,
    }


def _instantane(modele: JobOfferModel) -> dict[str, Any]:
    """État d'une offre conservé dans l'historique (valeurs sérialisables)."""
    instantane: dict[str, Any] = {}
    for cle in (*_champs_offre_cles(), "status"):
        valeur = getattr(modele, cle)
        if isinstance(valeur, datetime):
            valeur = valeur.isoformat()
        elif isinstance(valeur, Decimal):
            valeur = str(valeur)
        instantane[cle] = valeur
    return instantane


def _champs_offre_cles() -> tuple[str, ...]:
    return (
        "title",
        "description",
        "application_url",
        "content_hash",
        "company_name",
        "location",
        "country_code",
        "employment_type",
        "remote_type",
        "salary_min",
        "salary_max",
        "salary_currency",
        "published_at",
        "expires_at",
        "canonical_url",
        "language",
    )


def _vers_offre_normalisee(modele: JobOfferModel) -> NormalizedOffer:
    return NormalizedOffer(
        title=modele.title,
        description=modele.description,
        application_url=modele.application_url,
        content_hash=modele.content_hash,
        company_name=modele.company_name,
        location=modele.location,
        country_code=CountryCode(modele.country_code) if modele.country_code else None,
        employment_type=EmploymentType(modele.employment_type) if modele.employment_type else None,
        remote_type=RemoteType(modele.remote_type) if modele.remote_type else None,
        salary_min=modele.salary_min,
        salary_max=modele.salary_max,
        salary_currency=modele.salary_currency,
        published_at=modele.published_at,
        expires_at=modele.expires_at,
        canonical_url=modele.canonical_url,
        language=modele.language,
    )


class SqlJobOfferRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------ ingestion

    async def upsert_observation(
        self,
        *,
        owner_id: uuid.UUID,
        source_id: uuid.UUID,
        external_id: str,
        offer: NormalizedOffer,
        raw_payload: dict[str, Any],
        observed_at: datetime,
    ) -> UpsertResult:
        """Enregistre une observation, de façon idempotente et sans doublon.

        Décision : (1) observation déjà connue → rafraîchie ; (2) offre existante de même URL
        canonique ou jugée identique → l'observation lui est rattachée (offre multi-sources) ;
        (3) sinon nouvelle offre.
        """
        existante = await self._observation(owner_id, source_id, external_id)
        if existante is not None:
            return await self._rafraichir(existante, offer, raw_payload, observed_at)

        cible = await self._offre_equivalente(owner_id, offer)
        if cible is not None:
            rattachee = await self._rattacher(
                cible, owner_id, source_id, external_id, raw_payload, observed_at
            )
            if rattachee:
                await self._session.execute(
                    update(JobOfferModel)
                    .where(JobOfferModel.id == cible.id)
                    .values(last_seen_at=observed_at, status=OfferStatus.ACTIVE.value)
                )
                return UpsertResult(offer_id=cible.id, created=False, changed=False, merged=True)
            # Observation créée entre-temps par une exécution concurrente : on la rafraîchit.
            concurrente = await self._observation(owner_id, source_id, external_id)
            if concurrente is not None:
                return await self._rafraichir(concurrente, offer, raw_payload, observed_at)

        return await self._creer(owner_id, source_id, external_id, offer, raw_payload, observed_at)

    async def _creer(
        self,
        owner_id: uuid.UUID,
        source_id: uuid.UUID,
        external_id: str,
        offer: NormalizedOffer,
        raw_payload: dict[str, Any],
        observed_at: datetime,
    ) -> UpsertResult:
        # L'offre puis son observation, dans un point de sauvegarde : si une exécution concurrente
        # a créé la même observation entre-temps, on annule et on réutilise la sienne.
        async with self._session.begin_nested() as sauvegarde:
            modele = JobOfferModel(
                owner_id=owner_id,
                primary_source_id=source_id,
                first_seen_at=observed_at,
                last_seen_at=observed_at,
                **_champs_offre(offer),
            )
            self._session.add(modele)
            await self._session.flush()
            if await self._inserer_observation(
                modele.id, owner_id, source_id, external_id, raw_payload, observed_at
            ):
                return UpsertResult(offer_id=modele.id, created=True, changed=False)
            await sauvegarde.rollback()

        concurrente = await self._observation(owner_id, source_id, external_id)
        if concurrente is None:  # pragma: no cover - suppression concurrente seulement
            raise RuntimeError("Observation introuvable après conflit d'insertion.")
        return await self._rafraichir(concurrente, offer, raw_payload, observed_at)

    async def _inserer_observation(
        self,
        offer_id: uuid.UUID,
        owner_id: uuid.UUID,
        source_id: uuid.UUID,
        external_id: str,
        raw_payload: dict[str, Any],
        observed_at: datetime,
    ) -> bool:
        insertion = (
            insert(JobOfferSourceModel)
            .values(
                owner_id=owner_id,
                offer_id=offer_id,
                source_id=source_id,
                external_id=external_id,
                raw_payload=raw_payload,
                retrieved_at=observed_at,
                last_seen_at=observed_at,
            )
            .on_conflict_do_nothing(index_elements=["owner_id", "source_id", "external_id"])
            .returning(JobOfferSourceModel.id)
        )
        return (await self._session.execute(insertion)).scalar_one_or_none() is not None

    async def _rattacher(
        self,
        cible: JobOfferModel,
        owner_id: uuid.UUID,
        source_id: uuid.UUID,
        external_id: str,
        raw_payload: dict[str, Any],
        observed_at: datetime,
    ) -> bool:
        async with self._session.begin_nested():
            return await self._inserer_observation(
                cible.id, owner_id, source_id, external_id, raw_payload, observed_at
            )

    async def _offre_equivalente(
        self, owner_id: uuid.UUID, offre: NormalizedOffer
    ) -> JobOfferModel | None:
        """Offre déjà connue décrivant le même poste (URL canonique puis critères multiples)."""
        champs = _champs_offre(offre)
        if (url := champs["canonical_url"]) is not None:
            requete = select(JobOfferModel).where(
                JobOfferModel.owner_id == owner_id, JobOfferModel.canonical_url == url
            )
            if (trouvee := (await self._session.execute(requete)).scalar_one_or_none()) is not None:
                return trouvee
        if not offre.company_name:
            return None
        candidats = (
            await self._session.execute(
                select(JobOfferModel)
                .where(
                    JobOfferModel.owner_id == owner_id,
                    func.lower(JobOfferModel.company_name) == offre.company_name.lower(),
                    JobOfferModel.status != OfferStatus.ARCHIVED.value,
                )
                .order_by(JobOfferModel.last_seen_at.desc())
                .limit(MAX_CANDIDATS_DOUBLON)
            )
        ).scalars()
        for candidat in candidats:
            if assess_duplicate(_vers_offre_normalisee(candidat), offre).duplicate:
                return candidat
        return None

    async def _observation(
        self, owner_id: uuid.UUID, source_id: uuid.UUID, external_id: str
    ) -> JobOfferSourceModel | None:
        requete = select(JobOfferSourceModel).where(
            JobOfferSourceModel.owner_id == owner_id,
            JobOfferSourceModel.source_id == source_id,
            JobOfferSourceModel.external_id == external_id,
        )
        return (await self._session.execute(requete)).scalar_one_or_none()

    async def _rafraichir(
        self,
        observation: JobOfferSourceModel,
        offer: NormalizedOffer,
        raw_payload: dict[str, Any],
        observed_at: datetime,
    ) -> UpsertResult:
        modele = await self._session.get(JobOfferModel, observation.offer_id)
        if modele is None:  # pragma: no cover - interdit par la clé étrangère
            raise RuntimeError("Offre introuvable pour une observation existante.")
        observation.last_seen_at = observed_at
        observation.retrieved_at = observed_at
        observation.raw_payload = raw_payload
        observation.gone_at = None  # réapparue sur la source
        # Le contenu de référence est celui de la source principale : une source secondaire
        # qui diffère légèrement ne réécrit pas la fiche.
        est_principale = modele.primary_source_id in (None, observation.source_id)
        changed = est_principale and modele.content_hash != offer.content_hash
        valeurs: dict[str, Any] = {"last_seen_at": observed_at, "status": OfferStatus.ACTIVE.value}
        if modele.required_experience_years is None:
            # Offre antérieure à la colonne (ou sans exigence) : on (re)déduit, sans effet de bord.
            valeurs["required_experience_years"] = _annees_requises(modele.description)
        if changed:
            self._session.add(
                JobOfferRevisionModel(
                    owner_id=modele.owner_id,
                    offer_id=modele.id,
                    content_hash=modele.content_hash,
                    snapshot=_instantane(modele),
                    observed_at=observed_at,
                )
            )
            valeurs.update(_champs_offre(offer))
        await self._session.execute(
            update(JobOfferModel).where(JobOfferModel.id == modele.id).values(**valeurs)
        )
        return UpsertResult(offer_id=modele.id, created=False, changed=changed)

    # ------------------------------------------------------------ cycle de vie

    async def mark_unseen_observations_gone(
        self, *, owner_id: uuid.UUID, source_id: uuid.UUID, seen_since: datetime, now: datetime
    ) -> int:
        """À appeler **uniquement après un parcours complet et réussi** de la source : les
        observations non revues depuis `seen_since` sont marquées disparues de cette source."""
        resultat = await self._session.execute(
            update(JobOfferSourceModel)
            .where(
                JobOfferSourceModel.owner_id == owner_id,
                JobOfferSourceModel.source_id == source_id,
                JobOfferSourceModel.last_seen_at < seen_since,
                JobOfferSourceModel.gone_at.is_(None),
            )
            .values(gone_at=now)
        )
        return int(resultat.rowcount or 0)  # type: ignore[attr-defined]

    async def expire_offers(self, *, owner_id: uuid.UUID, now: datetime) -> int:
        """Passe en `expired` les offres actives dont toutes les observations ont disparu, ou dont
        la date d'expiration annoncée est dépassée."""
        encore_visible = exists().where(
            JobOfferSourceModel.offer_id == JobOfferModel.id,
            JobOfferSourceModel.gone_at.is_(None),
        )
        a_des_observations = exists().where(JobOfferSourceModel.offer_id == JobOfferModel.id)
        resultat = await self._session.execute(
            update(JobOfferModel)
            .where(
                JobOfferModel.owner_id == owner_id,
                JobOfferModel.status == OfferStatus.ACTIVE.value,
                (a_des_observations & ~encore_visible)
                | (JobOfferModel.expires_at.is_not(None) & (JobOfferModel.expires_at <= now)),
            )
            .values(status=OfferStatus.EXPIRED.value)
        )
        return int(resultat.rowcount or 0)  # type: ignore[attr-defined]

    async def archive_stale_offers(self, *, owner_id: uuid.UUID, expired_before: datetime) -> int:
        """Archive (sans supprimer) les offres expirées depuis longtemps, sauf si elles sont liées
        à une candidature ou sauvegardées par l'utilisateur."""
        suivie = exists().where(ApplicationModel.offer_id == JobOfferModel.id)
        sauvegardee = exists().where(
            JobOfferStateModel.offer_id == JobOfferModel.id,
            JobOfferStateModel.state == OfferState.SAVED.value,
        )
        resultat = await self._session.execute(
            update(JobOfferModel)
            .where(
                JobOfferModel.owner_id == owner_id,
                JobOfferModel.status == OfferStatus.EXPIRED.value,
                JobOfferModel.last_seen_at < expired_before,
                ~suivie,
                ~sauvegardee,
            )
            .values(status=OfferStatus.ARCHIVED.value)
        )
        return int(resultat.rowcount or 0)  # type: ignore[attr-defined]
