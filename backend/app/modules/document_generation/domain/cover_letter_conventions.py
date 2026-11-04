"""Conventions de la lettre selon la langue et le pays (TASK-013-16, 013-18)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

_MONTHS_FR = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)
_MONTHS_EN = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
# Usage britannique : jour avant le mois, « Dear Sir or Madam / Yours faithfully ».
_BRITISH_STYLE = frozenset({"GB", "IE", "AU", "NZ"})


@dataclass(frozen=True)
class LetterLabels:
    subject_label: str  # « Objet » / « Subject »
    attention: str  # « À l'attention de » / « Attn: »


@dataclass(frozen=True)
class LetterConventions:
    salutation: str
    complimentary_close: str
    labels: LetterLabels


def format_letter_date(
    today: date, *, language: str, country_code: str | None, city: str | None
) -> str:
    """Date et lieu au format du pays : « Lyon, le 4 novembre 2026 », « London, 4 November… »."""
    if language == "en":
        mois = _MONTHS_EN[today.month - 1]
        texte = (
            f"{today.day} {mois} {today.year}"
            if country_code in _BRITISH_STYLE
            else f"{mois} {today.day}, {today.year}"
        )
        return f"{city}, {texte}" if city else texte
    texte = f"{today.day} {_MONTHS_FR[today.month - 1]} {today.year}"
    return f"{city}, le {texte}" if city else f"Le {texte}"


def conventions_for(
    *, language: str, country_code: str | None, recipient_name: str | None
) -> LetterConventions:
    """Salutation et formule de politesse adaptées à la langue, au pays et au destinataire."""
    if language == "en":
        labels = LetterLabels("Subject", "Attn:")
        if country_code in _BRITISH_STYLE:
            if recipient_name:
                return LetterConventions(f"Dear {recipient_name},", "Yours sincerely,", labels)
            return LetterConventions("Dear Sir or Madam,", "Yours faithfully,", labels)
        salutation = f"Dear {recipient_name}," if recipient_name else "Dear Hiring Manager,"
        return LetterConventions(salutation, "Sincerely,", labels)
    # Le genre du destinataire est inconnu : « Madame, Monsieur » reste la seule forme sûre.
    return LetterConventions(
        "Madame, Monsieur,",
        "Je vous prie d'agréer, Madame, Monsieur, l'expression de mes salutations distinguées.",
        LetterLabels("Objet", "À l'attention de"),
    )
