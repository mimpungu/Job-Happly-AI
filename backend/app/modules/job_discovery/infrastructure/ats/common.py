"""Éléments communs aux connecteurs d'ATS publics."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from app.modules.job_discovery.domain.connector import InvalidResponseError, NotConfiguredError
from app.modules.job_discovery.domain.criteria import SearchCriteria
from app.modules.job_discovery.domain.filtering import matches_criteria
from app.modules.job_discovery.domain.offers import NormalizedOffer

_JETON = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$")


def validate_token(token: str, *, source: str) -> str:
    """Le jeton est inséré dans un chemin d'URL : il est strictement borné (pas d'injection)."""
    if not _JETON.fullmatch(token):
        raise NotConfiguredError(f"Jeton de {source} invalide.")
    return token


def expect_dict(valeur: Any, *, source_key: str, contexte: str) -> dict[str, Any]:
    if not isinstance(valeur, dict):
        raise InvalidResponseError(f"Structure inattendue : {contexte}.", source_key=source_key)
    return valeur


def expect_list(valeur: Any, *, source_key: str, contexte: str) -> list[Any]:
    if not isinstance(valeur, list):
        raise InvalidResponseError(f"Structure inattendue : {contexte}.", source_key=source_key)
    return valeur


def text_or_none(valeur: Any) -> str | None:
    """Texte nettoyé, ou `None` si la valeur est absente ou vide (jamais une chaîne vide)."""
    if not isinstance(valeur, str):
        return None
    nettoye = valeur.strip()
    return nettoye or None


def parse_iso_datetime(valeur: Any) -> datetime | None:
    texte = text_or_none(valeur)
    if texte is None:
        return None
    try:
        date = datetime.fromisoformat(texte.replace("Z", "+00:00"))
    except ValueError:
        return None
    return date if date.tzinfo else date.replace(tzinfo=UTC)


def paginate(
    offres: list[NormalizedOffer], criteria: SearchCriteria
) -> tuple[list[NormalizedOffer], str | None, int]:
    """Filtre localement puis découpe en pages. Curseur = position dans la liste filtrée."""
    filtrees = [o for o in offres if matches_criteria(o, criteria)]
    debut = 0
    if criteria.cursor is not None:
        try:
            debut = max(0, int(criteria.cursor))
        except ValueError as erreur:
            raise InvalidResponseError("Curseur invalide.") from erreur
    fin = debut + criteria.page_size
    suivant = str(fin) if fin < len(filtrees) else None
    return filtrees[debut:fin], suivant, len(filtrees)
