"""Lecteurs des offres et des documents générés : le CRM n'interroge pas leurs modules."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.modules.application_management.domain.entities import DocumentVersionInfo, OfferSummary
from app.modules.application_management.domain.ports import (
    DocumentVersionReaderPort,
    OfferReaderPort,
)
from app.modules.document_generation.infrastructure.models import (
    DocumentVersionModel,
    GeneratedDocumentModel,
)
from app.modules.job_discovery.infrastructure.models import JobOfferModel

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class SqlOfferReader(OfferReaderPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_summary(self, owner_id: uuid.UUID, offer_id: uuid.UUID) -> OfferSummary | None:
        offre = await self._session.scalar(
            select(JobOfferModel).where(
                JobOfferModel.id == offer_id, JobOfferModel.owner_id == owner_id
            )
        )
        if offre is None:
            return None
        return OfferSummary(
            offer_id=offre.id,
            title=offre.title,
            company_name=offre.company_name,
            location=offre.location,
            country_code=offre.country_code,
            application_url=offre.application_url,
        )


class SqlDocumentVersionReader(DocumentVersionReaderPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_info(
        self, owner_id: uuid.UUID, version_id: uuid.UUID
    ) -> DocumentVersionInfo | None:
        ligne = (
            await self._session.execute(
                select(DocumentVersionModel, GeneratedDocumentModel)
                .join(
                    GeneratedDocumentModel,
                    DocumentVersionModel.document_id == GeneratedDocumentModel.id,
                )
                .where(
                    DocumentVersionModel.id == version_id,
                    DocumentVersionModel.owner_id == owner_id,
                    GeneratedDocumentModel.owner_id == owner_id,
                )
            )
        ).first()
        if ligne is None:
            return None
        version, document = ligne
        rapport = version.ats_report or {}
        passe = rapport.get("passed")
        score = rapport.get("score")
        return DocumentVersionInfo(
            version_id=version.id,
            document_id=document.id,
            kind=document.kind,
            title=document.title,
            version=version.version,
            quality_passed=passe if isinstance(passe, bool) else None,
            quality_score=score if isinstance(score, int) else None,
        )
