"""Cas d'usage : interroger en parallèle toutes les sources utiles à une recherche (EPIC 008).

Les offres des sources sont d'abord enregistrées (dédupliquées) dans la base locale ; la liste
affichée est ensuite lue dans cette base, ce qui agrège naturellement toutes les sources sans
doublon. Une source en échec n'empêche jamais les autres : son erreur est rapportée telle quelle.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from pydantic import ValidationError

from app.modules.job_discovery.application.collection import (
    CollectionFilter,
    CollectionService,
    CompanyCollection,
    ExtraFactory,
    NoEnabledCompanyError,
)
from app.modules.job_discovery.domain.criteria import SearchCriteria
from app.modules.job_discovery.domain.enums import SearchRunStatus
from app.modules.job_discovery.domain.search import OfferFilter


@dataclass(frozen=True, slots=True)
class SourceSearchReport:
    status: SearchRunStatus | None
    """`None` : aucune source n'a été interrogée (rien d'activé), pas un échec."""
    sources: tuple[CompanyCollection, ...]


def to_collection_filter(offer_filter: OfferFilter, titles: tuple[str, ...]) -> CollectionFilter:
    """Ce qu'une offre doit satisfaire pour être enregistrée : le même sens que la recherche
    locale (texte et mots-clés dans l'intitulé ou la description), plus les intitulés visés."""
    termes = tuple(t for t in (offer_filter.text, *offer_filter.keywords) if t)
    return CollectionFilter(
        city=offer_filter.city,
        country_codes=offer_filter.country_codes,
        titles=titles,
        keywords=termes,
    )


def to_criteria(offer_filter: OfferFilter, titles: tuple[str, ...]) -> SearchCriteria | None:
    """Critères pour les sources de recherche ; `None` si aucun terme ne permet de les interroger
    (une source ne se parcourt pas « à vide »)."""
    intitules = tuple(dict.fromkeys(t for t in (offer_filter.text, *titles) if t))
    try:
        return SearchCriteria(
            title=intitules[0] if intitules else None,
            alternative_titles=intitules[1:],
            keywords=offer_filter.keywords,
            company=offer_filter.company,
            city=offer_filter.city,
            country_codes=offer_filter.country_codes,
            remote_types=offer_filter.remote_types,
            employment_types=offer_filter.employment_types,
            salary_min=offer_filter.salary_min,
            salary_currency=offer_filter.salary_currency,
            published_since=offer_filter.published_since,
            language=offer_filter.language,
        )
    except ValidationError:
        return None


class SourceSearchService:
    def __init__(self, collection: CollectionService) -> None:
        self._collection = collection

    async def collect(
        self,
        *,
        owner_id: uuid.UUID,
        offer_filter: OfferFilter,
        titles: tuple[str, ...] = (),
        extra_factory: ExtraFactory | None = None,
    ) -> SourceSearchReport:
        criteres = to_criteria(offer_filter, titles)
        try:
            rapport = await self._collection.run(
                owner_id=owner_id,
                keep=to_collection_filter(offer_filter, titles),
                # Sans terme de recherche, seules les entreprises suivies (catalogue) sont lues.
                extra_factory=extra_factory if criteres is not None else None,
                criteria=criteres,
            )
        except NoEnabledCompanyError:
            return SourceSearchReport(status=None, sources=())
        return SourceSearchReport(status=rapport.status, sources=rapport.companies)
