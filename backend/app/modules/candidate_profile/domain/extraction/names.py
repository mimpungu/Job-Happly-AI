"""Reconnaissance prudente d'un nom de personne (deux à quatre mots, lettres seulement)."""

from __future__ import annotations

import re

_NOM = re.compile(r"^[^\W\d_]+(?:[ '’-][^\W\d_]+){1,3}$")
MAX_LONGUEUR_NOM = 50


def ressemble_a_un_nom(texte: str) -> bool:
    """Vrai pour « Marie Dupont » ; faux pour une adresse, un titre ou une phrase."""
    brut = texte.strip()
    return len(brut) <= MAX_LONGUEUR_NOM and _NOM.match(brut) is not None
