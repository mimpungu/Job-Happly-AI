"""Repositories SQL du contexte job_discovery.

Les repositories ne valident jamais la transaction : c'est le rôle de l'unité de travail.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.job_discovery.domain.enums import OfferStatus
from app.modules.job_discovery.domain.offers import NormalizedOffer, UpsertResult
from app.modules.job_discovery.infrastructure.models import JobOfferModel, JobOfferSourceModel


def _champs_offre(offre: NormalizedOffer) -> dict[str, Any]:
    return {
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
        "canonical_url": offre.canonical_url,
        "language": offre.language,
    }


class SqlJobOfferRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

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
        existante = await self._observation(owner_id, source_id, external_id)
        if existante is not None:
            return await self._rafraichir(existante, offer, raw_payload, observed_at)

        # Création : l'offre puis son observation, dans un point de sauvegarde. Si une exécution
        # concurrente a créé la même observation entre-temps, on annule et on la réutilise.
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
            insertion = (
                insert(JobOfferSourceModel)
                .values(
                    owner_id=owner_id,
                    offer_id=modele.id,
                    source_id=source_id,
                    external_id=external_id,
                    raw_payload=raw_payload,
                    retrieved_at=observed_at,
                    last_seen_at=observed_at,
                )
                .on_conflict_do_nothing(index_elements=["owner_id", "source_id", "external_id"])
                .returning(JobOfferSourceModel.id)
            )
            if (await self._session.execute(insertion)).scalar_one_or_none() is not None:
                return UpsertResult(offer_id=modele.id, created=True, changed=False)
            await sauvegarde.rollback()

        concurrente = await self._observation(owner_id, source_id, external_id)
        if (
            concurrente is None
        ):  # pragma: no cover - ne peut arriver que sous suppression concurrente
            raise RuntimeError("Observation introuvable après conflit d'insertion.")
        return await self._rafraichir(concurrente, offer, raw_payload, observed_at)

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
        changed = modele.content_hash != offer.content_hash
        observation.last_seen_at = observed_at
        observation.retrieved_at = observed_at
        observation.raw_payload = raw_payload
        valeurs: dict[str, Any] = {"last_seen_at": observed_at, "status": OfferStatus.ACTIVE.value}
        if changed:
            valeurs.update(_champs_offre(offer))
        await self._session.execute(
            update(JobOfferModel).where(JobOfferModel.id == modele.id).values(**valeurs)
        )
        return UpsertResult(offer_id=modele.id, created=False, changed=changed)
