"""Compétences : listes séparées par des virgules, puces ou « Catégorie : a, b, c »."""

from __future__ import annotations

import re

from app.modules.candidate_profile.domain.extraction.models import ExtractedSkill

_SEPARATEURS = re.compile(r"\s*[,;|•·/]\s*|\s{3,}")
_CATEGORIE = re.compile(r"^(?P<cat>[^:,;]{2,40}):\s*(?P<reste>.+)$")
MAX_MOTS = 5
MAX_LONGUEUR = 60


def extract_skills(lignes: tuple[str, ...]) -> tuple[ExtractedSkill, ...]:
    vues: set[str] = set()
    competences: list[ExtractedSkill] = []
    for ligne in lignes:
        texte = ligne.strip()
        if not texte:
            continue
        texte = texte[2:].strip() if texte.startswith("- ") else texte
        categorie: str | None = None
        m = _CATEGORIE.match(texte)
        if m and "http" not in texte.lower():
            categorie, texte = m.group("cat").strip(), m.group("reste")
        for morceau in _SEPARATEURS.split(texte):
            nom = morceau.strip(" .:-–—")
            # Une phrase n'est pas une compétence : on la laisse à l'utilisateur plutôt que de la
            # découper en mots-clés approximatifs.
            if not nom or len(nom) > MAX_LONGUEUR or len(nom.split()) > MAX_MOTS:
                continue
            cle = nom.casefold()
            if cle in vues:
                continue
            vues.add(cle)
            competences.append(ExtractedSkill(nom, categorie, ligne.strip()))
    return tuple(competences)
