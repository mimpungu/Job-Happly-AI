"""Lieux d'un CV : séparer « Entreprise Ville, Pays » sans liste de villes ni de pays codée en dur.

Seul un pays reconnu par le référentiel (fourni de l'extérieur) autorise la séparation : sans lui,
« Acme Corp, Paris » (entreprise, ville) et « Acme Corp Paris, France » (entreprise ville, pays)
sont indiscernables, et rien n'est deviné.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

CountryResolver = Callable[[str], str | None]
"""Nom de pays (toute langue) -> code ISO 3166-1 alpha-2, ou `None` si ce n'est pas un pays."""


def no_countries(_nom: str) -> str | None:
    """Résolveur par défaut : aucun pays connu, donc aucune séparation de lieu."""
    return None


@dataclass(frozen=True, slots=True)
class OrganizationAndPlace:
    organization: str | None
    city: str | None
    country: str
    country_code: str


_AVANT_PAYS = re.compile(r"^(?P<avant>[^,]+?),\s*(?P<pays>[^,]+)$")


def split_organization_and_place(
    texte: str, country_of: CountryResolver
) -> OrganizationAndPlace | None:
    """« Deuswell Bordeaux, France » -> (Deuswell, Bordeaux, France).

    La ville est le dernier mot (à majuscule) avant la virgule : une ville en plusieurs mots
    (« Le Mans ») laisse son premier mot à l'organisation, d'où la relecture humaine.
    """
    m = _AVANT_PAYS.match(texte.strip())
    if m is None:
        return None
    pays = m.group("pays").strip()
    code = country_of(pays)
    mots = m.group("avant").split()
    if code is None or not mots:
        return None
    if len(mots) == 1:
        return OrganizationAndPlace(None, mots[0], pays, code)
    if mots[-1][:1].isupper():
        return OrganizationAndPlace(" ".join(mots[:-1]), mots[-1], pays, code)
    return OrganizationAndPlace(" ".join(mots), None, pays, code)
