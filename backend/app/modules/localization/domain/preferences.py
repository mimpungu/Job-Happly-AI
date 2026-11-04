"""Préférences générales et de mobilité de l'utilisateur (TASK-017-01, 04, 05, 16, 17, 24)."""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass

from app.modules.localization.domain.geography import GeographyReference

# Langues de l'interface réellement traduites : en ajouter une exige d'ajouter ses traductions.
SUPPORTED_UI_LANGUAGES: tuple[str, ...] = ("fr", "en")
DEFAULT_UI_LANGUAGE = "fr"


class InvalidPreferencesError(ValueError):
    """Préférences incohérentes ; le message est rédigé pour l'utilisateur."""


@dataclass(frozen=True, slots=True)
class Preferences:
    """Une valeur `None` signifie « non renseigné » : jamais une valeur par défaut déguisée."""

    ui_language: str = DEFAULT_UI_LANGUAGE
    country_code: str | None = None
    """Pays de résidence ou de recherche principale."""
    currency: str | None = None
    timezone: str | None = None
    """Fuseau IANA (ex. `Europe/Paris`)."""
    willing_to_relocate: bool | None = None
    target_countries: tuple[str, ...] = ()
    """Pays où l'utilisateur accepterait de travailler."""
    work_permit_countries: tuple[str, ...] = ()
    """Pays où l'utilisateur déclare avoir le droit de travailler."""
    needs_sponsorship: bool | None = None
    """A besoin qu'un employeur parraine son visa, `None` si non précisé."""


def validate(
    prefs: Preferences, reference: GeographyReference, timezones: Collection[str]
) -> Preferences:
    """Vérifie les préférences contre le référentiel et renvoie une version normalisée."""
    if prefs.ui_language not in SUPPORTED_UI_LANGUAGES:
        raise InvalidPreferencesError(
            f"Langue d'interface non prise en charge : {prefs.ui_language!r} "
            f"(disponibles : {', '.join(SUPPORTED_UI_LANGUAGES)})."
        )
    connus = {c.code for c in reference.countries("en")}

    def pays(code: str) -> str:
        normalise = code.strip().upper()
        if normalise not in connus:
            raise InvalidPreferencesError(f"Pays inconnu : {code!r}.")
        return normalise

    devise = None
    if prefs.currency is not None:
        devise = prefs.currency.strip().upper()
        if not reference.has_currency(devise):
            raise InvalidPreferencesError(f"Devise inconnue : {prefs.currency!r}.")
    if prefs.timezone is not None and prefs.timezone not in timezones:
        raise InvalidPreferencesError(f"Fuseau horaire inconnu : {prefs.timezone!r}.")
    return Preferences(
        ui_language=prefs.ui_language,
        country_code=pays(prefs.country_code) if prefs.country_code else None,
        currency=devise,
        timezone=prefs.timezone,
        willing_to_relocate=prefs.willing_to_relocate,
        target_countries=tuple(dict.fromkeys(pays(c) for c in prefs.target_countries)),
        work_permit_countries=tuple(dict.fromkeys(pays(c) for c in prefs.work_permit_countries)),
        needs_sponsorship=prefs.needs_sponsorship,
    )
