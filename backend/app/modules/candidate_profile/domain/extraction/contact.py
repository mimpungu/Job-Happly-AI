"""Coordonnées : e-mail, téléphone, liens, nom et ville quand ils sont sûrs."""

from __future__ import annotations

import re

from app.modules.candidate_profile.domain.extraction.geography import (
    CountryResolver,
    no_countries,
)
from app.modules.candidate_profile.domain.extraction.models import ExtractedContact
from app.modules.candidate_profile.domain.extraction.names import ressemble_a_un_nom
from app.modules.candidate_profile.domain.extraction.sections import section_kind

_EMAIL = re.compile(
    r"(?<![\w.+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}"
)
_TELEPHONE = re.compile(r"(?<![\w/])(?:\+|00)?\(?\d[\d .()-]{7,18}\d(?![\w/])")
_URL = re.compile(r"(?:https?://|www\.)[^\s<>\"')]+", re.IGNORECASE)
_LINKEDIN = re.compile(
    r"(?:https?://)?(?:[a-z]{2,3}\.)?linkedin\.com/in/[^\s<>\"')]+", re.IGNORECASE
)
_CODE_POSTAL_VILLE = re.compile(r"\b\d{5}\s+([A-ZÀ-ÖØ-Ý][\w'’ -]{1,40}?)(?=\s*(?:[,;|·•\n]|$))")
_MOTS_NON_NOMINAUX = {"curriculum vitae", "cv", "resume", "résumé", "profil", "profile"}
_MIN_CHIFFRES, _MAX_CHIFFRES = 9, 15


def extract_contact(
    preambule: tuple[str, ...],
    texte_complet: str,
    entetes_colonnes: tuple[tuple[str, ...], ...] = (),
    country_of: CountryResolver = no_countries,
) -> ExtractedContact:
    """Cherche d'abord dans l'en-tête, puis dans tout le document pour e-mail et liens.

    `entetes_colonnes` : texte sans titre en tête des colonnes suivantes d'un CV à colonne
    latérale, où se trouve souvent le nom.
    """
    entete = "\n".join(ligne for bloc in (preambule, *entetes_colonnes) for ligne in bloc)
    nom = next((n for bloc in (preambule, *entetes_colonnes) if (n := _nom(bloc))), None)
    ville, code_pays = _lieu(entete, country_of)
    return ExtractedContact(
        full_name=nom,
        email=_premier(_EMAIL, entete) or _premier(_EMAIL, texte_complet),
        phone=_telephone(entete) or _telephone(texte_complet),
        city=_ville(entete) or ville,
        country_code=code_pays,
        linkedin_url=_linkedin(entete) or _linkedin(texte_complet),
        website_url=_site(entete) or _site(texte_complet),
    )


def _premier(motif: re.Pattern[str], texte: str) -> str | None:
    m = motif.search(texte)
    return m.group(0).rstrip(".,;") if m else None


def _telephone(texte: str) -> str | None:
    for m in _TELEPHONE.finditer(texte):
        brut = m.group(0).strip()
        chiffres = re.sub(r"\D", "", brut)
        if not _MIN_CHIFFRES <= len(chiffres) <= _MAX_CHIFFRES:
            continue
        # Une période « 2020 2023 » ou une date « 01 02 2020 » a trop peu de chiffres ou des
        # années en tête : on exige un format téléphonique (indicatif ou 0 initial).
        if brut.startswith(("+", "00", "0", "(")):
            return re.sub(r"\s+", " ", brut)
    return None


def _linkedin(texte: str) -> str | None:
    lien = _premier(_LINKEDIN, texte)
    if lien is None:
        return None
    return lien if lien.lower().startswith("http") else f"https://{lien}"


def _site(texte: str) -> str | None:
    for m in _URL.finditer(texte):
        lien = m.group(0).rstrip(".,;")
        if "linkedin.com" in lien.lower():
            continue
        return lien if lien.lower().startswith("http") else f"https://{lien}"
    return None


def _ville(entete: str) -> str | None:
    # Seul « 75011 Paris » est assez fiable ; « Paris » seul pourrait être un nom ou une rue.
    m = _CODE_POSTAL_VILLE.search(entete)
    return m.group(1).strip() if m else None


_VILLE_ET_PAYS = re.compile(
    r"^(?P<ville>[A-ZÀ-ÖØ-Ý][\w'’.-]*(?:[ -][A-ZÀ-ÖØ-Ý][\w'’.-]*){0,2}),\s*(?P<pays>[^,\d]{2,40})$"
)


def _lieu(entete: str, country_of: CountryResolver) -> tuple[str | None, str | None]:
    """« Talence, France » -> (Talence, FR), seulement si « France » est un pays du référentiel :
    « Talence, Gironde » n'est pas deviné (région, pays ou faute ?)."""
    for ligne in entete.split("\n"):
        m = _VILLE_ET_PAYS.match(ligne.strip())
        if m and (code := country_of(m.group("pays"))) is not None:
            return m.group("ville"), code
    return None, None


def _nom(preambule: tuple[str, ...]) -> str | None:
    for ligne in preambule:
        texte = ligne.strip()
        if not texte:
            continue
        if texte.lower() in _MOTS_NON_NOMINAUX or section_kind(texte) is not None:
            continue
        # Seule la première ligne utile est candidate : un nom en milieu de page serait un pari.
        return texte if ressemble_a_un_nom(texte) else None
    return None
