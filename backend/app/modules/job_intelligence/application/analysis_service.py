"""Cas d'usage : analyse d'une offre, versionnée et réutilisée tant que l'annonce ne change pas.

L'analyse est déterministe (règles) : elle ne coûte rien et ne dépend d'aucun fournisseur. Son
empreinte porte sur le texte analysé *et* la version des règles : une annonce modifiée, ou une règle
corrigée, produit une nouvelle analyse sans écraser l'historique.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from app.modules.job_intelligence.domain.analysis.extraction import analyze_offer
from app.modules.job_intelligence.domain.analysis.models import ANALYSIS_VERSION
from app.modules.job_intelligence.domain.matching.models import OfferFacts

RULES_MODEL = "rules"


@dataclass(frozen=True, slots=True)
class StoredAnalysis:
    analysis_id: uuid.UUID
    content_hash: str
    result: dict[str, Any]
    created_at: datetime
    reused: bool
    """Vrai si l'analyse existait déjà pour ce texte et cette version de règles."""


class AnalysisStore(Protocol):
    async def get_or_create(
        self,
        *,
        owner_id: uuid.UUID,
        offer_id: uuid.UUID,
        content_hash: str,
        result: dict[str, Any],
    ) -> StoredAnalysis: ...

    async def history(self, *, owner_id: uuid.UUID, offer_id: uuid.UUID) -> list[StoredAnalysis]:
        """Analyses de l'offre, de la plus récente à la plus ancienne."""
        ...


class OfferReader(Protocol):
    async def get(self, *, owner_id: uuid.UUID, offer_id: uuid.UUID) -> OfferFacts: ...


def content_hash(offre: OfferFacts) -> str:
    """Empreinte de ce qui est analysé, plus la version des règles.

    Les champs structurés (salaire, contrat…) y figurent aussi : ils alimentent « informations
    manquantes », donc un salaire ajouté après coup ne doit pas laisser une analyse périmée.
    """
    morceaux = [
        ANALYSIS_VERSION,
        offre.title,
        offre.description,
        offre.location or "",
        str(offre.salary_min),
        str(offre.salary_max),
        str(offre.employment_type),
        str(offre.remote_type),
        str(offre.country_code),
    ]
    return hashlib.sha256("\x1f".join(morceaux).encode("utf-8")).hexdigest()


class AnalysisService:
    def __init__(self, offers: OfferReader, store: AnalysisStore) -> None:
        self._offers = offers
        self._store = store

    async def analyze(self, *, owner_id: uuid.UUID, offer_id: uuid.UUID) -> StoredAnalysis:
        offre = await self._offers.get(owner_id=owner_id, offer_id=offer_id)
        return await self._store.get_or_create(
            owner_id=owner_id,
            offer_id=offer_id,
            content_hash=content_hash(offre),
            result=analyze_offer(offre).to_dict(),
        )

    async def history(self, *, owner_id: uuid.UUID, offer_id: uuid.UUID) -> list[StoredAnalysis]:
        await self._offers.get(owner_id=owner_id, offer_id=offer_id)  # 404 si introuvable
        return await self._store.history(owner_id=owner_id, offer_id=offer_id)
