"""Dates de CV, souvent partielles : « 2020 », « mars 2021 », « 03/2021 ».

Une date partielle n'est **jamais complétée** : inventer un mois ou un jour fausserait le profil.
Le jour et le mois absents restent `None` et c'est l'utilisateur qui précise.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date

_MOIS = {
    # français
    "janvier": 1, "janv": 1, "fevrier": 2, "fevr": 2, "fev": 2, "mars": 3, "avril": 4, "avr": 4,
    "mai": 5, "juin": 6, "juillet": 7, "juil": 7, "aout": 8, "septembre": 9, "sept": 9,
    "octobre": 10, "oct": 10, "novembre": 11, "nov": 11, "decembre": 12, "dec": 12,
    # anglais
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3, "april": 4, "apr": 4,
    "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7, "august": 8, "aug": 8,
    "september": 9, "sep": 9, "october": 10, "november": 11, "december": 12,
}  # fmt: skip

_ANNEE_MIN, _ANNEE_MAX = 1950, 2100
_COURANT = (
    r"(?:aujourd'?hui|aujourdhui|pr[ée]sent|actuel(?:le(?:ment)?)?|en cours|current|present"
    r"|now|ce jour)"
)
_SEPARATEURS = r"\s*(?:-|–|—|‑|à|a|au|to|until|jusqu'?(?:à|a|au))\s*"


@dataclass(frozen=True, slots=True)
class PartialDate:
    year: int
    month: int | None = None

    def __post_init__(self) -> None:
        if not _ANNEE_MIN <= self.year <= _ANNEE_MAX:
            raise ValueError(f"Année improbable : {self.year}")
        if self.month is not None and not 1 <= self.month <= 12:
            raise ValueError(f"Mois invalide : {self.month}")

    def as_date(self) -> date | None:
        """Date complète uniquement si le mois est connu (premier jour du mois)."""
        return date(self.year, self.month, 1) if self.month else None


@dataclass(frozen=True, slots=True)
class DateRange:
    start: PartialDate | None
    end: PartialDate | None
    is_current: bool
    """« Aujourd'hui », « présent »… : la période est en cours, la fin est inconnue."""
    span: tuple[int, int]
    """Position (début, fin) du texte reconnu dans la ligne, pour le retirer de l'intitulé."""


def _sans_accents(texte: str) -> str:
    decompose = unicodedata.normalize("NFD", texte)
    return "".join(c for c in decompose if unicodedata.category(c) != "Mn")


_MOIS_RE = "|".join(sorted(_MOIS, key=len, reverse=True))
_DATE = (
    rf"(?:(?:(?P<{{p}}m>{_MOIS_RE})\.?\s+)?(?P<{{p}}y>(?:19|20)\d{{{{2}}}})"
    rf"|(?P<{{p}}n>0?[1-9]|1[0-2])[/.](?P<{{p}}ny>(?:19|20)\d{{{{2}}}}))"
)
_PLAGE = re.compile(
    rf"(?<![\w/.])(?:{_DATE.format(p='a')})"
    rf"(?:{_SEPARATEURS}(?:(?P<cur>{_COURANT})|{_DATE.format(p='b')}))?"
    rf"(?![\w/])",
    re.IGNORECASE,
)
_DEPUIS = re.compile(
    rf"(?<![\w/.])(?:depuis|since|from|d[ée]s)\s+{_DATE.format(p='a')}(?![\w/])", re.IGNORECASE
)


def _lire(m: re.Match[str], prefixe: str) -> PartialDate | None:
    annee = m.group(f"{prefixe}y") or m.group(f"{prefixe}ny")
    if not annee:
        return None
    mois_texte = m.group(f"{prefixe}m")
    if mois_texte:
        mois: int | None = _MOIS[_sans_accents(mois_texte.lower())]
    else:
        mois_num = m.group(f"{prefixe}n")
        mois = int(mois_num) if mois_num else None
    try:
        return PartialDate(int(annee), mois)
    except ValueError:
        return None


def find_date_range(ligne: str) -> DateRange | None:
    """Premier intervalle de dates d'une ligne : « 2020 – 2023 », « Jan 2020 - Présent »…

    Une date seule (« 2019 ») est renvoyée comme début **sans fin** : l'appelant décide si elle
    a un sens (formation, certification) ; pour une expérience, elle reste ambiguë.
    """
    texte = _sans_accents_conserve_longueur(ligne)
    depuis = _DEPUIS.search(texte)
    if depuis:
        debut = _lire(depuis, "a")
        if debut:
            return DateRange(debut, None, True, depuis.span())
    for m in _PLAGE.finditer(texte):
        debut = _lire(m, "a")
        if debut is None:
            continue
        courant = m.group("cur") is not None
        fin = None if courant else _lire(m, "b")
        if fin is not None and _avant(fin, debut):
            continue  # « 2023 - 2020 » : incohérent, on ne devine pas l'ordre
        return DateRange(debut, fin, courant, m.span())
    return None


def _avant(a: PartialDate, b: PartialDate) -> bool:
    return (a.year, a.month or 1) < (b.year, b.month or 1)


def _sans_accents_conserve_longueur(texte: str) -> str:
    # NFD ajouterait des caractères et décalerait les positions : on remplace les lettres une à une.
    return "".join(
        next((c for c in unicodedata.normalize("NFD", ch) if unicodedata.category(c) != "Mn"), ch)
        for ch in texte
    )
