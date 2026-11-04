"""Expériences professionnelles : intitulé, entreprise, période, missions."""

from __future__ import annotations

import re
import unicodedata

from app.modules.candidate_profile.domain.extraction.blocks import Block, est_puce, split_blocks
from app.modules.candidate_profile.domain.extraction.dates import DateRange
from app.modules.candidate_profile.domain.extraction.geography import (
    CountryResolver,
    no_countries,
    split_organization_and_place,
)
from app.modules.candidate_profile.domain.extraction.models import Confidence, ExtractedExperience

_MOTS_INTITULE = (
    "ingenieur", "developpeur", "developpeuse", "analyste", "consultant", "consultante", "manager",
    "responsable", "directeur", "directrice", "chef", "stagiaire", "alternant", "alternante",
    "technicien", "technicienne", "assistant", "assistante", "charge", "gestionnaire", "architecte",
    "administrateur", "administratrice", "comptable", "commercial", "commerciale", "redacteur",
    "redactrice", "designer", "scientist", "engineer", "developer", "analyst", "intern",
    "director", "lead", "head", "officer", "specialist", "coordinator", "coordinateur",
    "coordinatrice", "technician", "associate", "advisor", "conseiller", "conseillere", "devops",
    "formateur", "formatrice", "enseignant", "enseignante", "chercheur", "chercheuse", "freelance",
    "apprenti", "apprentie", "agent", "executive", "president", "fondateur", "fondatrice",
    "founder", "cto", "ceo", "coach", "operateur", "operatrice", "vendeur", "vendeuse",
)  # fmt: skip
_MOT = re.compile(r"[a-z]+")
_LIEU_APRES_VIRGULE = re.compile(
    r"^(?P<org>.+?),\s*(?P<lieu>[A-ZÀ-ÖØ-Ý][\w'’.-]*(?:[ -][A-ZÀ-ÖØ-Ý][\w'’.-]*){0,2})$"
)
_CODE_POSTAL = re.compile(r"\b\d{5}\b")


def _sans_accents(texte: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texte) if unicodedata.category(c) != "Mn"
    )


def ressemble_a_un_intitule(texte: str) -> bool:
    mots = set(_MOT.findall(_sans_accents(texte.lower())))
    return any(mot in mots for mot in _MOTS_INTITULE)


MAX_MOTS_APRES_ANNEE = 8


def _est_experience(ligne: str, plage: DateRange) -> bool:
    if plage.end is not None or plage.is_current:
        return True
    # Une année seule est ambiguë (date d'un projet ? d'un diplôme ? d'une phrase ?). Elle n'ouvre
    # une expérience que si elle commence la ligne et précède une organisation (majuscule
    # initiale, courte) : « 2025 Université de Bordeaux Talence, France ».
    reste = ligne[plage.span[1] :].strip(" \t-–—|,;:")
    return (
        plage.span[0] == 0
        and not est_puce(ligne)
        and reste[:1].isupper()
        and len(reste.split()) <= MAX_MOTS_APRES_ANNEE
    )


def extract_experiences(
    lignes: tuple[str, ...], country_of: CountryResolver = no_countries
) -> tuple[ExtractedExperience, ...]:
    return tuple(
        _experience(b, country_of) for b in split_blocks(lignes, is_anchor=_est_experience)
    )


def _experience(bloc: Block, country_of: CountryResolver) -> ExtractedExperience:
    morceaux = list(bloc.header_pieces)
    lieu: str | None = None
    lieu_deduit = False

    # « Entreprise, Ville » : seule forme de lieu acceptée sans référentiel de villes ; signalée.
    for i, morceau in enumerate(morceaux):
        separe = split_organization_and_place(morceau, country_of)
        if separe is not None and not ressemble_a_un_intitule(morceau):
            lieu = ", ".join(p for p in (separe.city, separe.country) if p)
            if separe.organization:
                morceaux[i] = separe.organization
            else:
                morceaux.pop(i)
            break
        m = _LIEU_APRES_VIRGULE.match(morceau)
        if m and not ressemble_a_un_intitule(morceau):
            morceaux[i], lieu, lieu_deduit = m.group("org"), m.group("lieu"), True
            break
        if _CODE_POSTAL.search(morceau):
            lieu = morceaux.pop(i)
            break

    intitules = [m for m in morceaux if ressemble_a_un_intitule(m)]
    autres = [m for m in morceaux if m not in intitules]
    titre: str | None
    entreprise: str | None
    confiance = Confidence.HIGH
    if len(intitules) == 1:
        titre = intitules[0]
        entreprise = autres[0] if autres else None
        if len(autres) > 1:
            confiance = Confidence.LOW
    elif not morceaux:
        titre = entreprise = None
        confiance = Confidence.LOW
    else:
        # Ni intitulé reconnaissable, ni unicité : l'ordre est une hypothèse à faire valider.
        titre = morceaux[0]
        entreprise = morceaux[1] if len(morceaux) > 1 else None
        confiance = Confidence.LOW
    if lieu_deduit:
        confiance = Confidence.LOW

    return ExtractedExperience(
        title=titre,
        company=entreprise,
        location=lieu,
        start=bloc.dates.start,
        end=bloc.dates.end,
        is_current=bloc.dates.is_current,
        description=" ".join(bloc.prose) or None,
        achievements=bloc.bullets,
        confidence=confiance,
        source_text=bloc.source_text,
    )
