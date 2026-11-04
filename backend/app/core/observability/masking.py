"""Affichage masqué d'un secret : reconnaître la clé active sans la révéler (TASK-018-34)."""

from __future__ import annotations

from pydantic import SecretStr

_VISIBLES = 4
_MIN_POUR_INDICE = 12  # une clé courte révélerait une part trop grande de son contenu


def key_hint(secret: SecretStr | None) -> str | None:
    """« …a1b2 » : les 4 derniers caractères, uniquement pour une clé assez longue."""
    if secret is None:
        return None
    valeur = secret.get_secret_value()
    if len(valeur) < _MIN_POUR_INDICE:
        return "…"
    return f"…{valeur[-_VISIBLES:]}"
