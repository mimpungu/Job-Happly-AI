"""Certifications : intitulé et année d'obtention quand elle est indiquée."""

from __future__ import annotations

import re

from app.modules.candidate_profile.domain.extraction.blocks import split_blocks
from app.modules.candidate_profile.domain.extraction.dates import DateRange
from app.modules.candidate_profile.domain.extraction.models import ExtractedCertification

_ANNEE = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")
_DECORATION = " \t-–—:|,;"
# L'intitulé est la ligne juste au-dessus de la date ; une autre ligne au-dessus est la
# certification précédente (la disposition « organisme / intitulé / date » est propre aux postes).
_LIGNES_AVANT_LA_DATE = 1


def _est_periode_bornee(_ligne: str, plage: DateRange) -> bool:
    return plage.end is not None or plage.is_current


def extract_certifications(lignes: tuple[str, ...]) -> tuple[ExtractedCertification, ...]:
    """Une entrée par certification : par bloc quand le CV date ses certifications d'une période
    (intitulé, organisme, description), sinon une par ligne."""
    blocs = split_blocks(
        lignes, is_anchor=_est_periode_bornee, max_lines_before=_LIGNES_AVANT_LA_DATE
    )
    if not blocs:
        return _par_ligne(lignes)

    premiere = blocs[0].source_text.split("\n")[0]
    debut = next((i for i, ligne in enumerate(lignes) if ligne.strip() == premiere), 0)
    avant = _par_ligne(lignes[:debut])
    datees = tuple(
        ExtractedCertification(
            name=bloc.header_pieces[0],
            # Seule la fin d'une période est une date d'obtention : « en cours » n'en a pas, et
            # « obtention prévue 2025 » est un projet.
            year=bloc.dates.end.year if bloc.dates.end else None,
            source_text=bloc.source_text,
        )
        for bloc in blocs
        if bloc.header_pieces
    )
    return (*avant, *datees)


def _par_ligne(lignes: tuple[str, ...]) -> tuple[ExtractedCertification, ...]:
    certifications: list[ExtractedCertification] = []
    vues: set[str] = set()
    for ligne in lignes:
        texte = ligne.strip()
        texte = texte[2:].strip() if texte.startswith("- ") else texte
        if not texte:
            continue
        annee = _ANNEE.search(texte)
        nom = _ANNEE.sub("", texte).strip(_DECORATION) if annee else texte
        nom = re.sub(r"\(\s*\)", "", nom).strip(_DECORATION)
        if len(nom) < 3 or nom.casefold() in vues:
            continue
        vues.add(nom.casefold())
        certifications.append(
            ExtractedCertification(nom, int(annee.group(1)) if annee else None, texte)
        )
    return tuple(certifications)
