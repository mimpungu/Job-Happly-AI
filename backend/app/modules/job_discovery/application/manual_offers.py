"""Cas d'usage : enregistrer une offre saisie par l'utilisateur (copiée depuis un site).

Le geste reste humain : aucune requête n'est faite vers le site d'origine. L'offre suit ensuite
le même chemin que les offres collectées (normalisation, déduplication, score, suivi).
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain.value_objects import (
    CountryCode,
    DomainValueError,
    EmploymentType,
    RemoteType,
)
from app.modules.job_discovery.domain.normalization import normalize_offer
from app.modules.job_discovery.domain.offers import NormalizedOffer
from app.modules.job_discovery.domain.text import content_hash
from app.modules.job_discovery.infrastructure.repositories import SqlJobOfferRepository
from app.modules.job_discovery.infrastructure.source_repository import SqlJobSourceRepository


class InvalidManualOfferError(ValueError):
    """Saisie refusée (message rédigé par nos soins, affichable tel quel)."""


@dataclass(frozen=True, slots=True)
class ManualOfferInput:
    title: str
    description: str
    application_url: str
    company_name: str | None = None
    location: str | None = None
    country_code: str | None = None
    employment_type: EmploymentType | None = None
    remote_type: RemoteType | None = None
    published_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ManualOfferResult:
    offer_id: uuid.UUID
    created: bool
    merged: bool
    changed: bool


def canonical_url(url: str) -> str:
    """URL comparable : HTTPS exigé, sans identifiants ni fragment, hôte en minuscules.

    La requête (`?id=…`) est conservée : sur beaucoup de sites elle identifie l'offre.
    """
    morceaux = urlsplit(url.strip())
    if morceaux.scheme != "https" or not morceaux.hostname:
        raise InvalidManualOfferError("L'adresse de l'offre doit commencer par https://.")
    if morceaux.username or morceaux.password:
        raise InvalidManualOfferError("L'adresse ne doit pas contenir d'identifiants.")
    hote = morceaux.hostname.lower() + (f":{morceaux.port}" if morceaux.port else "")
    return urlunsplit(("https", hote, morceaux.path.rstrip("/") or "/", morceaux.query, ""))


class ManualOfferService:
    def __init__(self, *, clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self._clock = clock

    async def add(
        self, session: AsyncSession, owner_id: uuid.UUID, saisie: ManualOfferInput
    ) -> ManualOfferResult:
        titre = saisie.title.strip()
        description = saisie.description.strip()
        if not titre:
            raise InvalidManualOfferError("L'intitulé est obligatoire.")
        if not description:
            raise InvalidManualOfferError("Le texte de l'offre est obligatoire.")
        url = canonical_url(saisie.application_url)
        entreprise = (saisie.company_name or "").strip() or None
        lieu = (saisie.location or "").strip() or None
        try:
            pays = CountryCode(saisie.country_code) if saisie.country_code else None
        except (ValueError, DomainValueError) as erreur:
            raise InvalidManualOfferError("Code pays invalide (ex. FR).") from erreur

        offre = normalize_offer(
            NormalizedOffer(
                title=titre,
                description=description,
                application_url=url,
                canonical_url=url,
                company_name=entreprise,
                location=lieu,
                country_code=pays,
                employment_type=saisie.employment_type,
                remote_type=saisie.remote_type,
                published_at=saisie.published_at,
                content_hash=content_hash(titre, entreprise, lieu, description, url),
            )
        )
        source = await SqlJobSourceRepository(session).ensure_manual(owner_id)
        resultat = await SqlJobOfferRepository(session).upsert_observation(
            owner_id=owner_id,
            source_id=source.id,
            # L'adresse identifie l'offre : saisir deux fois la même ne crée pas de doublon.
            external_id=hashlib.sha256(url.encode()).hexdigest()[:40],
            offer=offre,
            raw_payload={"entered_by": "user", "application_url": url},
            observed_at=self._clock(),
        )
        return ManualOfferResult(
            offer_id=resultat.offer_id,
            created=resultat.created,
            merged=resultat.merged,
            changed=resultat.changed,
        )
