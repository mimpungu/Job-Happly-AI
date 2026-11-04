"""Extraction des offres `JobPosting` (schema.org) publiées dans une page, au format JSON-LD.

Les données sont publiques et destinées aux moteurs de recherche. Le contenu de la page est non
fiable : seul du texte est conservé, jamais du HTML ni du script.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from typing import Any

from app.core.domain.value_objects import (
    CountryCode,
    DomainValueError,
    EmploymentType,
    RemoteType,
)
from app.modules.job_discovery.domain.connector import ConnectorOffer
from app.modules.job_discovery.domain.offers import NormalizedOffer
from app.modules.job_discovery.domain.text import content_hash, html_to_text
from app.modules.job_discovery.infrastructure.ats.common import parse_iso_datetime, text_or_none

MAX_BLOCS = 50
MAX_OFFRES = 500

# Valeurs ambiguës (FULL_TIME) volontairement absentes : on n'invente pas CDI ou CDD.
_CONTRATS = {
    "PART_TIME": EmploymentType.PART_TIME,
    "CONTRACTOR": EmploymentType.FREELANCE,
    "INTERN": EmploymentType.INTERNSHIP,
    "TEMPORARY": EmploymentType.TEMPORARY,
}


class _CollecteurJsonLd(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocs: list[str] = []
        self._courant: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script" and any(
            k == "type" and (v or "").lower().split(";")[0].strip() == "application/ld+json"
            for k, v in attrs
        ):
            self._courant = []

    def handle_data(self, data: str) -> None:
        if self._courant is not None:
            self._courant.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._courant is not None:
            if len(self.blocs) < MAX_BLOCS:
                self.blocs.append("".join(self._courant))
            self._courant = None


def _aplatir(noeud: Any) -> list[dict[str, Any]]:
    """Retrouve tous les objets d'un document JSON-LD (listes, `@graph`, imbrications)."""
    if isinstance(noeud, list):
        return [x for element in noeud for x in _aplatir(element)]
    if isinstance(noeud, dict):
        trouves = [noeud]
        for cle in ("@graph", "itemListElement", "item"):
            if cle in noeud:
                trouves.extend(_aplatir(noeud[cle]))
        return trouves
    return []


def _est_job_posting(objet: dict[str, Any]) -> bool:
    type_ = objet.get("@type")
    return type_ == "JobPosting" or (isinstance(type_, list) and "JobPosting" in type_)


def extract_job_postings(html: str, *, page_url: str) -> list[ConnectorOffer]:
    """Offres `JobPosting` d'une page. Un bloc JSON invalide est ignoré, jamais fatal."""
    collecteur = _CollecteurJsonLd()
    collecteur.feed(html)
    collecteur.close()
    offres: list[ConnectorOffer] = []
    for bloc in collecteur.blocs:
        try:
            document = json.loads(bloc)
        except ValueError:
            continue
        for objet in _aplatir(document):
            if _est_job_posting(objet) and (offre := _convertir(objet, page_url)) is not None:
                offres.append(offre)
                if len(offres) >= MAX_OFFRES:
                    return offres
    return offres


def _convertir(objet: dict[str, Any], page_url: str) -> ConnectorOffer | None:
    titre = text_or_none(objet.get("title"))
    description = html_to_text(text_or_none(objet.get("description")) or "")
    url = text_or_none(objet.get("url")) or page_url
    if titre is None:
        return None
    entreprise = objet.get("hiringOrganization")
    nom_entreprise = text_or_none(entreprise.get("name")) if isinstance(entreprise, dict) else None
    localisation, pays = _lieu(objet.get("jobLocation"))
    salaire_min, salaire_max, devise = _salaire(objet.get("baseSalary"))
    contrat = objet.get("employmentType")
    if isinstance(contrat, list):
        contrat = contrat[0] if len(contrat) == 1 else None
    teletravail = (
        RemoteType.REMOTE
        if str(objet.get("jobLocationType", "")).upper() == "TELECOMMUTE"
        else None
    )
    offre = NormalizedOffer(
        title=titre,
        description=description,
        application_url=url,
        canonical_url=url,
        company_name=nom_entreprise,
        location=localisation,
        country_code=pays,
        employment_type=_CONTRATS.get(str(contrat).upper()) if contrat else None,
        remote_type=teletravail,
        salary_min=salaire_min,
        salary_max=salaire_max,
        salary_currency=devise,
        published_at=_date(objet.get("datePosted")),
        expires_at=_date(objet.get("validThrough")),
        content_hash=content_hash(titre, nom_entreprise, localisation, description, url),
    )
    return ConnectorOffer(
        external_id=_identifiant(objet, url), offer=offre, raw_payload=objet, source_url=url
    )


def _identifiant(objet: dict[str, Any], url: str) -> str:
    identifiant = objet.get("identifier")
    if isinstance(identifiant, dict):
        valeur = identifiant.get("value")
        if isinstance(valeur, str | int) and not isinstance(valeur, bool) and str(valeur).strip():
            return str(valeur).strip()
    if (
        isinstance(identifiant, str | int)
        and not isinstance(identifiant, bool)
        and str(identifiant).strip()
    ):
        return str(identifiant).strip()
    return url


def _date(valeur: Any) -> datetime | None:
    if (parsee := parse_iso_datetime(valeur)) is not None:
        return parsee
    texte = text_or_none(valeur)
    if texte is not None:
        try:
            return datetime.strptime(texte[:10], "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError:
            return None
    return None


def _lieu(valeur: Any) -> tuple[str | None, CountryCode | None]:
    lieu = valeur[0] if isinstance(valeur, list) and valeur else valeur
    if not isinstance(lieu, dict):
        return None, None
    adresse = lieu.get("address")
    if not isinstance(adresse, dict):
        return text_or_none(lieu.get("name")), None
    pays_brut = adresse.get("addressCountry")
    if isinstance(pays_brut, dict):
        pays_brut = pays_brut.get("name")
    pays_texte = text_or_none(pays_brut)
    parties = [
        text_or_none(adresse.get("addressLocality")),
        text_or_none(adresse.get("addressRegion")),
        pays_texte,
    ]
    pays: CountryCode | None = None
    if pays_texte is not None:
        try:
            pays = CountryCode(pays_texte)
        except DomainValueError:
            pays = None
    texte = ", ".join(p for p in parties if p)
    return (texte or None), pays


def _salaire(valeur: Any) -> tuple[Decimal | None, Decimal | None, str | None]:
    """Salaire annuel uniquement (YEAR) ; toute autre unité est ignorée plutôt que convertie."""
    if not isinstance(valeur, dict):
        return None, None, None
    montant = valeur.get("value")
    devise = text_or_none(valeur.get("currency"))
    if not isinstance(montant, dict) or str(montant.get("unitText", "")).upper() != "YEAR":
        return None, None, None
    try:
        minimum = Decimal(str(montant["minValue"])) if montant.get("minValue") is not None else None
        maximum = Decimal(str(montant["maxValue"])) if montant.get("maxValue") is not None else None
    except InvalidOperation:
        return None, None, None
    if devise is None or len(devise) != 3 or (minimum is None and maximum is None):
        return None, None, None
    if any(m is not None and (not m.is_finite() or m < 0) for m in (minimum, maximum)):
        return None, None, None
    if minimum is not None and maximum is not None and maximum < minimum:
        return None, None, None
    return minimum, maximum, devise.upper()
