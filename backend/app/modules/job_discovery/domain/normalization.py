"""Normalisation des champs d'une offre (titres, lieux, contrats, salaires, dates).

Principes :
- On ne déduit que ce qui est sûr : une valeur ambiguë reste `None` (« Full-time » n'est ni CDI
  ni CDD, « $ » n'est ni USD ni CAD).
- Fonctions pures et déterministes, sans accès réseau ni appel IA.
- La donnée d'origine n'est jamais perdue : elle reste dans `job_offer_sources.raw_payload`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from app.core.domain.value_objects import CountryCode, DomainValueError, EmploymentType
from app.modules.job_discovery.domain.offers import NormalizedOffer
from app.modules.job_discovery.domain.text import normalize_text

# ------------------------------------------------------------------ intitulés

_MARQUEUR_GENRE = re.compile(
    r"\s*[(\[]?\s*(?:h\s*/\s*f|f\s*/\s*h|m\s*/\s*f(?:\s*/\s*[dx])?|m\s*/\s*w(?:\s*/\s*[dx])?|"
    r"h\s*/\s*f\s*/\s*x|f\s*/\s*h\s*/\s*x)\s*[)\]]?\s*$",
    re.IGNORECASE,
)


def clean_title(titre: str) -> str:
    """Intitulé lisible : espaces normalisés, marqueur de genre final (H/F, m/f/d…) retiré."""
    espaces = " ".join(titre.split())
    return _MARQUEUR_GENRE.sub("", espaces).strip(" -\u2013\u2014|,")


def title_key(titre: str) -> str:
    """Clé de comparaison d'un intitulé (sans accents, casse, ponctuation ni marqueur de genre)."""
    return normalize_text(clean_title(titre))


# ------------------------------------------------------------------ lieux

# Données de référence minimales (alias courants d'écriture). Les codes ISO valides sont
# toujours acceptés : cette table n'est pas une liste fermée de pays (EPIC 017 la remplacera
# par un référentiel complet).
_ALIAS_PAYS = {
    "france": "FR",
    "germany": "DE",
    "allemagne": "DE",
    "deutschland": "DE",
    "belgium": "BE",
    "belgique": "BE",
    "luxembourg": "LU",
    "switzerland": "CH",
    "suisse": "CH",
    "spain": "ES",
    "espagne": "ES",
    "italy": "IT",
    "italie": "IT",
    "netherlands": "NL",
    "pays bas": "NL",
    "ireland": "IE",
    "irlande": "IE",
    "portugal": "PT",
    "united kingdom": "GB",
    "royaume uni": "GB",
    "uk": "GB",
    "united states": "US",
    "usa": "US",
    "etats unis": "US",
    "canada": "CA",
    "australia": "AU",
    "australie": "AU",
    "new zealand": "NZ",
    "nouvelle zelande": "NZ",
    "japan": "JP",
    "japon": "JP",
}
_TELETRAVAIL = ("remote", "teletravail", "a distance", "work from home", "anywhere")


@dataclass(frozen=True, slots=True)
class NormalizedLocation:
    city: str | None
    region: str | None
    country_code: CountryCode | None
    remote_hint: bool
    """Le texte évoque du télétravail (indice, pas une certitude sur le mode de travail)."""

    @property
    def key(self) -> str | None:
        """Clé de comparaison : ville normalisée, ou `None` si le lieu est inconnu."""
        return normalize_text(self.city) if self.city else None


def parse_country(texte: str | None) -> CountryCode | None:
    if not texte or not texte.strip():
        return None
    brut = texte.strip()
    if len(brut) == 2 and brut.isalpha():
        try:
            return CountryCode(brut)
        except DomainValueError:
            return None
    code = _ALIAS_PAYS.get(normalize_text(brut))
    return CountryCode(code) if code else None


def parse_location(texte: str | None) -> NormalizedLocation:
    """Découpe « Ville, Région, Pays ». Ce qui n'est pas reconnu avec certitude reste `None`."""
    if not texte or not texte.strip():
        return NormalizedLocation(None, None, None, False)
    normalise = normalize_text(texte)
    teletravail = any(mot in normalise for mot in _TELETRAVAIL)
    parties = [p.strip() for p in re.split(r"[,;/|]", texte) if p.strip()]
    pays: CountryCode | None = None
    if len(parties) > 1 and (candidat := parse_country(parties[-1])) is not None:
        pays = candidat
        parties = parties[:-1]
    elif len(parties) == 1:
        pays = parse_country(parties[0])
        if pays is not None:
            parties = []
    parties = [p for p in parties if not any(m in normalize_text(p) for m in _TELETRAVAIL)]
    ville = parties[0] if parties else None
    region = parties[1] if len(parties) > 1 else None
    return NormalizedLocation(ville, region, pays, teletravail)


# ------------------------------------------------------------------ contrats

_CONTRATS: dict[str, EmploymentType] = {
    "cdi": EmploymentType.PERMANENT,
    "permanent": EmploymentType.PERMANENT,
    "contrat a duree indeterminee": EmploymentType.PERMANENT,
    "cdd": EmploymentType.FIXED_TERM,
    "fixed term": EmploymentType.FIXED_TERM,
    "contrat a duree determinee": EmploymentType.FIXED_TERM,
    "stage": EmploymentType.INTERNSHIP,
    "internship": EmploymentType.INTERNSHIP,
    "intern": EmploymentType.INTERNSHIP,
    "alternance": EmploymentType.APPRENTICESHIP,
    "apprentissage": EmploymentType.APPRENTICESHIP,
    "apprenticeship": EmploymentType.APPRENTICESHIP,
    "freelance": EmploymentType.FREELANCE,
    "independant": EmploymentType.FREELANCE,
    "contractor": EmploymentType.FREELANCE,
    "interim": EmploymentType.TEMPORARY,
    "temporary": EmploymentType.TEMPORARY,
    "temps partiel": EmploymentType.PART_TIME,
    "part time": EmploymentType.PART_TIME,
}


def parse_employment_type(texte: str | None) -> EmploymentType | None:
    """Type de contrat. Les libellés ambigus (« Full-time », « Contract ») donnent `None`."""
    if not texte:
        return None
    return _CONTRATS.get(normalize_text(texte))


# ------------------------------------------------------------------ devises et salaires

_DEVISES = {
    "eur": "EUR",
    "euro": "EUR",
    "euros": "EUR",
    "€": "EUR",
    "gbp": "GBP",
    "£": "GBP",
    "chf": "CHF",
    "usd": "USD",
    "cad": "CAD",
    "aud": "AUD",
    "jpy": "JPY",
    "¥": "JPY",
    "sek": "SEK",
    "nok": "NOK",
    "dkk": "DKK",
}
# Le symbole « $ » seul est ambigu (USD, CAD, AUD…) : il n'est jamais converti.


def parse_currency(texte: str | None) -> str | None:
    """Code ISO 4217 d'après un code, un nom ou un symbole non ambigu ; sinon `None`."""
    if not texte:
        return None
    brut = texte.strip()
    if re.fullmatch(r"[A-Za-z]{3}", brut):
        return brut.upper()
    return _DEVISES.get(brut.lower())


def parse_amount(texte: str) -> Decimal | None:
    """Montant décimal depuis « 45 000 », « 45k », « 45.000,50 » ou « 45,000.50 »."""
    brut = re.sub(r"\s+", "", texte.strip().lower())
    multiplicateur = Decimal(1)
    if brut.endswith("k"):
        multiplicateur, brut = Decimal(1000), brut[:-1]
    if not re.fullmatch(r"\d[\d.,]*", brut):
        return None
    if "," in brut and "." in brut:
        # Le dernier séparateur est le séparateur décimal.
        decimal, milliers = (",", ".") if brut.rfind(",") > brut.rfind(".") else (".", ",")
        brut = brut.replace(milliers, "").replace(decimal, ".")
    elif "," in brut or "." in brut:
        separateur = "," if "," in brut else "."
        parties = brut.split(separateur)
        # « 45.000 » : groupes de 3 chiffres → séparateur de milliers ; sinon décimal.
        if len(parties) > 2 or (
            len(parties) == 2 and len(parties[1]) == 3 and len(parties[0]) <= 3
        ):
            brut = "".join(parties)
        else:
            brut = brut.replace(separateur, ".")
    try:
        montant = Decimal(brut) * multiplicateur
    except InvalidOperation:
        return None
    return montant if montant.is_finite() and montant >= 0 else None


_PERIODES = {
    "an": "year", "annee": "year", "annuel": "year", "year": "year", "yearly": "year",
    "annual": "year", "per year": "year", "par an": "year",
    "mois": "month", "mensuel": "month", "month": "month", "monthly": "month", "par mois": "month",
    "heure": "hour", "hour": "hour", "hourly": "hour", "horaire": "hour",
}  # fmt: skip


def parse_period(texte: str | None) -> str | None:
    return _PERIODES.get(normalize_text(texte)) if texte else None


def annual_amount(montant: Decimal, periode: str | None) -> Decimal | None:
    """Montant annuel : annuel tel quel, mensuel multiplié par 12 (hypothèse de 12 mois,
    à présenter comme telle) ; horaire ou période inconnue : `None`, sans conversion hasardeuse."""
    if periode == "year":
        return montant
    if periode == "month":
        return montant * 12
    return None


# ------------------------------------------------------------------ dates


def to_utc(date: datetime, *, assume_timezone: str | None = None) -> datetime | None:
    """Date en UTC. Une date sans fuseau n'est interprétée que si `assume_timezone` est fourni
    (fuseau documenté de la source) ; sinon `None` : on ne devine pas un fuseau."""
    if date.tzinfo is not None:
        return date.astimezone(UTC)
    if assume_timezone is None:
        return None
    try:
        return date.replace(tzinfo=ZoneInfo(assume_timezone)).astimezone(UTC)
    except (KeyError, ValueError):
        return None


# ------------------------------------------------------------------ offre complète


def normalize_offer(offre: NormalizedOffer) -> NormalizedOffer:
    """Applique les normalisations sûres à une offre. Aucune valeur n'est inventée.

    - intitulé nettoyé (marqueur de genre final retiré) ;
    - pays déduit du lieu **seulement s'il est écrit explicitement** et absent du champ pays ;
    - devise ramenée à un code ISO, ou `None` si elle n'est pas fiable (alors le salaire est
      aussi ignoré : un montant sans devise n'a pas de sens) ;
    - dates ramenées en UTC ; une date sans fuseau est écartée plutôt que devinée.
    """
    lieu = parse_location(offre.location)
    devise = parse_currency(offre.salary_currency)
    salaire_utilisable = devise is not None and (
        offre.salary_min is not None or offre.salary_max is not None
    )
    return replace(
        offre,
        title=clean_title(offre.title) or offre.title,
        country_code=offre.country_code or lieu.country_code,
        salary_currency=devise if salaire_utilisable else None,
        salary_min=offre.salary_min if salaire_utilisable else None,
        salary_max=offre.salary_max if salaire_utilisable else None,
        published_at=to_utc(offre.published_at) if offre.published_at else None,
        expires_at=to_utc(offre.expires_at) if offre.expires_at else None,
    )
