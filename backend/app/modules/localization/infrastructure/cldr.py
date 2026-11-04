"""Référentiel géographique adossé à Babel (données CLDR / ISO), sans aucune liste codée en dur."""

from __future__ import annotations

from functools import lru_cache

from babel import Locale, UnknownLocaleError
from babel.core import get_global
from babel.languages import get_official_languages
from babel.numbers import (
    get_currency_name,
    get_currency_symbol,
    get_territory_currencies,
    list_currencies,
)

from app.modules.localization.domain.geography import Country, Currency

_LOCALE_PAR_DEFAUT = "en"


def _locale(code: str) -> Locale:
    try:
        return Locale.parse(code)
    except (UnknownLocaleError, ValueError):
        return Locale.parse(_LOCALE_PAR_DEFAUT)


def _reserve_par_iso(code: str) -> bool:
    """Plages que la norme ISO 3166-1 laisse à l'usage de l'utilisateur (jamais des pays) :
    AA, QM à QZ, XA à XZ et ZZ."""
    return code in {"AA", "ZZ"} or code[0] == "X" or ("QM" <= code <= "QZ")


class BabelGeographyReference:
    """Un pays est un territoire à deux lettres dont le CLDR connaît au moins une langue, hors
    plages réservées par l'ISO : cela écarte les regroupements (UE, ONU) et les codes réservés
    sans énumérer de liste de pays."""

    def countries(self, locale: str) -> tuple[Country, ...]:
        return _pays(_locale(locale).language)

    def country(self, code: str, locale: str) -> Country | None:
        recherche = code.strip().upper()
        return next((c for c in self.countries(locale) if c.code == recherche), None)

    def currencies(self, locale: str) -> tuple[Currency, ...]:
        return _devises(_locale(locale).language)

    def has_currency(self, code: str) -> bool:
        return code.strip().upper() in _codes_devises()


@lru_cache(maxsize=8)
def _pays(langue: str) -> tuple[Country, ...]:
    locale = _locale(langue)
    avec_langues = get_global("territory_languages")
    pays = [
        Country(
            code=code,
            name=nom,
            # `de_facto` : les États-Unis, l'Australie ou le Mexique n'ont pas de langue officielle
            # légale mais une langue d'usage, qu'il serait faux de déclarer absente.
            official_languages=tuple(get_official_languages(code, de_facto=True)),
            currencies=tuple(get_territory_currencies(code)),
        )
        for code, nom in locale.territories.items()
        if len(code) == 2 and code.isalpha() and code in avec_langues and not _reserve_par_iso(code)
    ]
    return tuple(sorted(pays, key=lambda c: c.name.casefold()))


@lru_cache(maxsize=1)
def _codes_devises() -> frozenset[str]:
    return frozenset(list_currencies())


@lru_cache(maxsize=8)
def _devises(langue: str) -> tuple[Currency, ...]:
    return tuple(
        sorted(
            (
                Currency(
                    code=code,
                    name=get_currency_name(code, locale=langue),
                    symbol=get_currency_symbol(code, locale=langue),
                )
                for code in _codes_devises()
            ),
            key=lambda d: d.name.casefold(),
        )
    )
