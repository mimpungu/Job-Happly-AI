"""Certifications : intitulé et année d'obtention quand elle est indiquée."""

from __future__ import annotations

import re

from app.modules.candidate_profile.domain.extraction.models import ExtractedCertification

_ANNEE = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")
_DECORATION = " \t-–—:|,;"


def extract_certifications(lignes: tuple[str, ...]) -> tuple[ExtractedCertification, ...]:
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
