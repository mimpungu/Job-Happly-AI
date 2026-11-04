"""Persistance du mode démonstration : insertion et retrait des offres fictives."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain.value_objects import CountryCode
from app.modules.application_management.infrastructure.models import ApplicationModel
from app.modules.demo.application.ports import DemoCounts, DemoRemoval
from app.modules.demo.domain.catalogue import DEMO_SOURCE_KEY, DEMO_SOURCE_NAME, DemoOffer
from app.modules.document_generation.infrastructure.models import (
    DocumentVersionModel,
    GeneratedDocumentModel,
)
from app.modules.job_discovery.domain.enums import SourceKind
from app.modules.job_discovery.domain.normalization import normalize_offer
from app.modules.job_discovery.domain.offers import NormalizedOffer
from app.modules.job_discovery.domain.text import content_hash
from app.modules.job_discovery.infrastructure.models import JobOfferModel, JobSourceModel
from app.modules.job_discovery.infrastructure.repositories import SqlJobOfferRepository


class SqlDemoRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _compter(self, owner_id: uuid.UUID, *, demo: bool) -> DemoCounts:
        offres = (
            await self._session.scalar(
                select(func.count())
                .select_from(JobOfferModel)
                .where(JobOfferModel.owner_id == owner_id, JobOfferModel.is_demo.is_(demo))
            )
        ) or 0
        candidatures = (
            await self._session.scalar(
                select(func.count())
                .select_from(ApplicationModel)
                .join(JobOfferModel, JobOfferModel.id == ApplicationModel.offer_id)
                .where(ApplicationModel.owner_id == owner_id, JobOfferModel.is_demo.is_(demo))
            )
        ) or 0
        return DemoCounts(offres, candidatures)

    async def demo_counts(self, owner_id: uuid.UUID) -> DemoCounts:
        return await self._compter(owner_id, demo=True)

    async def real_counts(self, owner_id: uuid.UUID) -> DemoCounts:
        return await self._compter(owner_id, demo=False)

    async def _source(self, owner_id: uuid.UUID) -> JobSourceModel:
        source = await self._session.scalar(
            select(JobSourceModel).where(
                JobSourceModel.owner_id == owner_id, JobSourceModel.key == DEMO_SOURCE_KEY
            )
        )
        if source is None:
            source = JobSourceModel(
                owner_id=owner_id,
                key=DEMO_SOURCE_KEY,
                name=DEMO_SOURCE_NAME,
                kind=SourceKind.MANUAL.value,
                enabled=True,
            )
            self._session.add(source)
            await self._session.flush()
        return source

    async def add_offers(
        self, owner_id: uuid.UUID, offers: tuple[DemoOffer, ...], *, now: datetime
    ) -> int:
        source = await self._source(owner_id)
        depot = SqlJobOfferRepository(self._session)
        for indice, offre in enumerate(offers, start=1):
            url = f"https://demo.invalid/offres/{indice}"
            normalisee = normalize_offer(
                NormalizedOffer(
                    title=offre.title,
                    description=offre.description,
                    application_url=url,
                    canonical_url=url,
                    company_name=offre.company,
                    location=offre.location,
                    country_code=CountryCode(offre.country_code),
                    employment_type=offre.employment_type,
                    remote_type=offre.remote_type,
                    published_at=now,
                    content_hash=content_hash(
                        offre.title, offre.company, offre.location, offre.description, url
                    ),
                )
            )
            resultat = await depot.upsert_observation(
                owner_id=owner_id,
                source_id=source.id,
                external_id=hashlib.sha256(url.encode()).hexdigest()[:40],
                offer=normalisee,
                raw_payload={"demo": True},
                observed_at=now,
            )
            await self._session.execute(
                update(JobOfferModel)
                .where(JobOfferModel.id == resultat.offer_id)
                .values(is_demo=True)
            )
        return len(offers)

    async def remove_all(self, owner_id: uuid.UUID) -> DemoRemoval:
        ids_offres = select(JobOfferModel.id).where(
            JobOfferModel.owner_id == owner_id, JobOfferModel.is_demo.is_(True)
        )
        # Documents générés à partir d'une offre fictive : ils en dérivent, ils partent avec elle.
        ids_documents = select(GeneratedDocumentModel.id).where(
            GeneratedDocumentModel.owner_id == owner_id,
            GeneratedDocumentModel.offer_id.in_(ids_offres),
        )
        cles = tuple(
            c
            for c in await self._session.scalars(
                select(DocumentVersionModel.storage_key).where(
                    DocumentVersionModel.document_id.in_(ids_documents)
                )
            )
            if c
        )
        documents = (
            await self._session.execute(
                delete(GeneratedDocumentModel).where(GeneratedDocumentModel.id.in_(ids_documents))
            )
        ).rowcount  # type: ignore[attr-defined]
        candidatures = (
            await self._session.execute(
                delete(ApplicationModel).where(
                    ApplicationModel.owner_id == owner_id,
                    ApplicationModel.offer_id.in_(ids_offres),
                )
            )
        ).rowcount  # type: ignore[attr-defined]
        offres = (
            await self._session.execute(
                delete(JobOfferModel).where(
                    JobOfferModel.owner_id == owner_id, JobOfferModel.is_demo.is_(True)
                )
            )
        ).rowcount  # type: ignore[attr-defined]
        await self._session.execute(
            delete(JobSourceModel).where(
                JobSourceModel.owner_id == owner_id, JobSourceModel.key == DEMO_SOURCE_KEY
            )
        )
        return DemoRemoval(offres, candidatures, documents, cles)
