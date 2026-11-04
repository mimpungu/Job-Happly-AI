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
from app.modules.job_discovery.application.company_resolution import (
    CompanyResolution,
    CompanyResolver,
)
from app.modules.job_discovery.domain.criteria import SearchCriteria
from app.modules.job_discovery.domain.enums import SearchRunStatus
from app.modules.job_discovery.domain.search import OfferFilter
from app.modules.job_discovery.domain.text import search_words


@dataclass(frozen=True, slots=True)
class GeographicCoverage:
    """Ce que les sources interrogées couvrent réellement, à afficher tel quel (TASK-017-19)."""

    requested: tuple[str, ...]
    """Pays demandés par la recherche."""
    declared: tuple[str, ...]
    """Pays demandés qu'au moins une source interrogée déclare couvrir."""
    undeclared: tuple[str, ...]
    """Pays demandés qu'aucune source interrogée ne déclare couvrir."""
    sources_without_declared_countries: tuple[str, ...]
    """Sources interrogées sans couverture déclarée : elles peuvent avoir des offres dans ces
    pays, mais on ne l'affirme pas."""


def coverage_of(
    requested: tuple[str, ...], sources: tuple[CompanyCollection, ...]
) -> GeographicCoverage:
    couverts = {pays for s in sources for pays in s.countries}
    return GeographicCoverage(
        requested=requested,
        declared=tuple(p for p in requested if p in couverts),
        undeclared=tuple(p for p in requested if p not in couverts),
        sources_without_declared_countries=tuple(s.source_key for s in sources if not s.countries),
    )


@dataclass(frozen=True, slots=True)
class SourceSearchReport:
    status: SearchRunStatus | None
    """`None` : aucune source n'a été interrogée (rien d'activé), pas un échec."""
    sources: tuple[CompanyCollection, ...]
    company: CompanyResolution | None = None
    """Résolution de l'entreprise saisie (site carrières retrouvé, suivi, candidats…)."""


def to_collection_filter(offer_filter: OfferFilter, titles: tuple[str, ...]) -> CollectionFilter:
    """Ce qu'une offre doit satisfaire pour être enregistrée : le même sens que la recherche
    locale (texte et mots-clés dans l'intitulé ou la description), plus les intitulés visés."""
    # Comme la recherche locale : chaque mot saisi doit figurer, dans n'importe quel ordre.
    mots = tuple(search_words(offer_filter.text or ""))
    termes = (*mots, *(k for k in offer_filter.keywords if k))
    return CollectionFilter(
        city=offer_filter.city,
        country_codes=offer_filter.country_codes,
        titles=titles,
        keywords=termes,
        multilingual=offer_filter.multilingual,
    )


def to_criteria(offer_filter: OfferFilter, titles: tuple[str, ...]) -> SearchCriteria | None:
    """Critères pour les sources de recherche ; `None` si aucun terme ne permet de les interroger
    (une source ne se parcourt pas « à vide »)."""
    intitules = tuple(dict.fromkeys(t for t in titles if t))
    # Le texte saisi est un ensemble de mots (chacun doit figurer, dans n'importe quel ordre) ;
    # seuls les intitulés visés explicitement servent d'intitulé (l'un d'eux suffit).
    mots = tuple(search_words(offer_filter.text or ""))
    try:
        return SearchCriteria(
            title=intitules[0] if intitules else None,
            alternative_titles=intitules[1:],
            keywords=(*mots, *offer_filter.keywords),
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
    def __init__(
        self, collection: CollectionService, resolver: CompanyResolver | None = None
    ) -> None:
        self._collection = collection
        self._resolver = resolver

    async def collect(
        self,
        *,
        owner_id: uuid.UUID,
        offer_filter: OfferFilter,
        titles: tuple[str, ...] = (),
        extra_factory: ExtraFactory | None = None,
    ) -> SourceSearchReport:
        criteres = to_criteria(offer_filter, titles)
        entreprise: CompanyResolution | None = None
        seulement: frozenset[uuid.UUID] | None = None
        if offer_filter.company and self._resolver is not None:
            # Une entreprise précise est demandée : on retrouve son site carrières et on ne lit
            # que celui-là (pas les autres entreprises suivies).
            entreprise = await self._resolver.resolve(
                owner_id=owner_id, company=offer_filter.company
            )
            if not entreprise.company_ids:
                return SourceSearchReport(status=None, sources=(), company=entreprise)
            seulement = entreprise.company_ids
        try:
            rapport = await self._collection.run(
                owner_id=owner_id,
                keep=to_collection_filter(offer_filter, titles),
                # Sans terme de recherche, seules les entreprises suivies (catalogue) sont lues.
                extra_factory=extra_factory if criteres is not None else None,
                criteria=criteres,
                only_company_ids=seulement,
            )
        except NoEnabledCompanyError:
            return SourceSearchReport(status=None, sources=(), company=entreprise)
        return SourceSearchReport(
            status=rapport.status, sources=rapport.companies, company=entreprise
        )
