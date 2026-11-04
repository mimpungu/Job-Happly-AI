"""Résolveur de noms de pays pour l'import de CV, adossé au référentiel géographique."""

from __future__ import annotations

import re
import unicodedata

from app.modules.candidate_profile.domain.extraction.geography import CountryResolver
from app.modules.localization.domain.geography import GeographyReference

# Langues des CV lus : un CV français cite « Royaume-Uni », un CV anglais « United Kingdom ».
_LANGUES = ("fr", "en")


def _cle(nom: str) -> str:
    """Comparaison sans casse, accents, points ni espaces multiples."""
    sans_accents = "".join(
        c for c in unicodedata.normalize("NFD", nom) if unicodedata.category(c) != "Mn"
    )
    return re.sub(
        r"\s+", " ", sans_accents.casefold().replace("\u2019", "'").replace(".", "")
    ).strip()


def build_country_resolver(
    reference: GeographyReference, langues: tuple[str, ...] = _LANGUES
) -> CountryResolver:
    table = {
        _cle(pays.name): pays.code for langue in langues for pays in reference.countries(langue)
    }

    def resoudre(nom: str) -> str | None:
        cle = _cle(nom)
        return table.get(cle) if cle else None

    return resoudre
