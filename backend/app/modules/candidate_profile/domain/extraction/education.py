"""Formations : diplôme, établissement, période."""

from __future__ import annotations

import re

from app.modules.candidate_profile.domain.extraction.blocks import Block, split_blocks
from app.modules.candidate_profile.domain.extraction.dates import DateRange, PartialDate
from app.modules.candidate_profile.domain.extraction.experience import _sans_accents
from app.modules.candidate_profile.domain.extraction.geography import (
    CountryResolver,
    no_countries,
    split_organization_and_place,
)
from app.modules.candidate_profile.domain.extraction.models import Confidence, ExtractedEducation

_MOTS_DIPLOME = (
    "master", "licence", "bachelor", "diplome", "bts", "dut", "but", "ingenieur", "doctorat",
    "phd", "mba", "baccalaureat", "bac", "certificat", "degree", "msc", "bsc", "magistere",
    "deug", "cap", "bep", "titre", "mastere", "diploma", "associate",
)  # fmt: skip
_MOTS_ETABLISSEMENT = (
    "universite", "university", "ecole", "school", "institut", "institute", "college", "lycee",
    "iut", "faculte", "faculty", "academy", "academie", "polytechnique", "cnam", "campus",
)  # fmt: skip
_MOT = re.compile(r"[a-z]+")
_APRES_EN = re.compile(r"\b(?:en|in|:)\s+(?P<domaine>[^,;()]{3,80})$", re.IGNORECASE)


def _contient(texte: str, mots: tuple[str, ...]) -> bool:
    return any(m in mots for m in _MOT.findall(_sans_accents(texte.lower())))


def _est_formation(_ligne: str, _plage: DateRange) -> bool:
    # Un diplôme est souvent daté d'une seule année : toute date ancre une formation.
    return True


def extract_educations(
    lignes: tuple[str, ...], country_of: CountryResolver = no_countries
) -> tuple[ExtractedEducation, ...]:
    return tuple(_formation(b, country_of) for b in split_blocks(lignes, is_anchor=_est_formation))


def _separer_diplome_et_ecole(morceaux: tuple[str, ...]) -> list[str]:
    """« BSc Informatique, University of Leeds » : séparés par la virgule, mais seulement si l'un
    des côtés est un diplôme et l'autre un établissement (« Paris, France » reste entier)."""
    resultat: list[str] = []
    for morceau in morceaux:
        parties = [p.strip() for p in morceau.split(",") if p.strip()]
        diplome = any(_contient(p, _MOTS_DIPLOME) for p in parties)
        ecole = any(_contient(p, _MOTS_ETABLISSEMENT) for p in parties)
        resultat.extend(parties if len(parties) > 1 and diplome and ecole else [morceau])
    return resultat


def _sans_ville(morceau: str, country_of: CountryResolver) -> str:
    """« Université de Bordeaux Talence, France » -> « Université de Bordeaux » : la formation n'a
    pas de champ de lieu, la ville reste dans le texte source."""
    separe = split_organization_and_place(morceau, country_of)
    return separe.organization if separe is not None and separe.organization else morceau


def _formation(bloc: Block, country_of: CountryResolver) -> ExtractedEducation:
    morceaux = _separer_diplome_et_ecole(
        tuple(_sans_ville(m, country_of) for m in bloc.header_pieces)
    )
    avec_diplome = [m for m in morceaux if _contient(m, _MOTS_DIPLOME)]
    # Un morceau qui n'est pas aussi un établissement est préféré comme diplôme.
    diplomes = [m for m in avec_diplome if not _contient(m, _MOTS_ETABLISSEMENT)] or avec_diplome
    etablissements = [m for m in morceaux if _contient(m, _MOTS_ETABLISSEMENT)]
    diplome = diplomes[0] if diplomes else None
    # Un même morceau (« Université de Lyon ») ne peut pas être à la fois diplôme et école.
    etablissement = next((m for m in etablissements if m != diplome), None)
    reste = [m for m in morceaux if m not in (diplome, etablissement)]

    confiance = Confidence.HIGH if diplome and (etablissement or not reste) else Confidence.LOW
    if diplome is None and etablissement is None and reste:
        diplome = reste.pop(0)  # hypothèse : le premier morceau désigne la formation
        confiance = Confidence.LOW

    domaine = None
    if diplome:
        m = _APRES_EN.search(diplome)
        domaine = m.group("domaine").strip() if m else None
    if domaine is None and diplome is not None and reste:
        domaine = reste[0]
        confiance = Confidence.LOW

    # Une année seule est la fin des études (date d'obtention), pas un début.
    debut: PartialDate | None = bloc.dates.start
    fin = bloc.dates.end
    if fin is None and not bloc.dates.is_current:
        debut, fin = None, bloc.dates.start

    return ExtractedEducation(
        degree=diplome,
        institution=etablissement,
        field_of_study=domaine,
        start=debut,
        end=fin,
        confidence=confiance,
        source_text=bloc.source_text,
    )
