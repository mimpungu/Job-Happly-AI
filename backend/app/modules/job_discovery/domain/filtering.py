"""Filtrage déterministe des offres selon les critères (niveau 0 : aucun appel IA).

Règle : une information absente de l'offre n'exclut jamais l'offre (on ne confond pas
« inconnu » et « ne correspond pas »). L'intitulé, la description, les mots-clés et les
compétences sont toujours présents et filtrent strictement.
"""

from __future__ import annotations

from collections.abc import Callable

from app.modules.job_discovery.domain.criteria import SearchCriteria
from app.modules.job_discovery.domain.offers import NormalizedOffer
from app.modules.job_discovery.domain.text import normalize_text


def _inconnu_ou[T](valeur: T | None, test: Callable[[T], bool]) -> bool:
    """Vrai si l'information est inconnue (non exclusion) ou si elle satisfait le test."""
    return valeur is None or test(valeur)


def _contient(motif: str) -> Callable[[str], bool]:
    cible = normalize_text(motif)
    return lambda texte: cible in normalize_text(texte)


def matches_criteria(offer: NormalizedOffer, criteria: SearchCriteria) -> bool:
    titre = normalize_text(offer.title)
    texte = normalize_text(f"{offer.title} {offer.description}")

    intitules = [t for t in (criteria.title, *criteria.alternative_titles) if t]
    if intitules and not any(normalize_text(i) in titre for i in intitules):
        return False
    if any(normalize_text(terme) not in texte for terme in (*criteria.keywords, *criteria.skills)):
        return False

    verifications = (
        not criteria.company or _inconnu_ou(offer.company_name, _contient(criteria.company)),
        not criteria.city or _inconnu_ou(offer.location, _contient(criteria.city)),
        not criteria.country_codes
        or _inconnu_ou(offer.country_code, lambda p: p.value in criteria.country_codes),
        not criteria.remote_types
        or _inconnu_ou(offer.remote_type, lambda r: r in criteria.remote_types),
        not criteria.employment_types
        or _inconnu_ou(offer.employment_type, lambda e: e in criteria.employment_types),
        criteria.published_since is None
        or _inconnu_ou(offer.published_at, lambda d: d >= criteria.published_since),  # type: ignore[operator]
        not criteria.language
        or _inconnu_ou(
            offer.language,
            lambda lang: lang.split("-")[0] == (criteria.language or "").split("-")[0],
        ),
    )
    return all(verifications)
