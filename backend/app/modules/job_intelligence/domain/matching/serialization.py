"""Sérialisation JSON d'un résultat de correspondance (colonne `breakdown`)."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from decimal import Decimal
from enum import Enum
from typing import Any

from app.modules.job_intelligence.domain.matching.models import MatchResult


def _jsonable(valeur: Any) -> Any:
    if isinstance(valeur, Enum):
        return valeur.value
    if isinstance(valeur, Decimal):
        return str(valeur)  # jamais de flottant : pas de perte de précision
    if is_dataclass(valeur) and not isinstance(valeur, type):
        return {f.name: _jsonable(getattr(valeur, f.name)) for f in fields(valeur)}
    if isinstance(valeur, dict):
        return {_jsonable(k): _jsonable(v) for k, v in valeur.items()}
    if isinstance(valeur, list | tuple):
        return [_jsonable(v) for v in valeur]
    return valeur


def match_to_dict(resultat: MatchResult) -> dict[str, Any]:
    """Résultat complet (critères, correspondances, écarts, explications) prêt pour JSONB."""
    return _jsonable(resultat)  # type: ignore[no-any-return]
