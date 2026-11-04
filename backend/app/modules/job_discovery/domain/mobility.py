"""Mobilité internationale (TASK-017-17, 017-18) : sponsoring de visa et autorisation de travail.

Détection par règles sur le texte de l'annonce, en français et en anglais. Une annonce muette
reste « inconnue » (`None`) : l'absence d'information n'est jamais présentée comme un refus.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class VisaSponsorship(StrEnum):
    OFFERED = "offered"
    NOT_OFFERED = "not_offered"


@dataclass(frozen=True, slots=True)
class MobilityInfo:
    visa_sponsorship: VisaSponsorship | None
    """`None` : l'annonce n'en parle pas."""
    work_authorization_required: bool | None
    """`True` : l'annonce exige un droit de travailler ; `None` : elle ne le dit pas."""


_OFFRE = re.compile(
    r"visa\s+sponsorship\s+(?:is\s+)?(?:available|provided|offered|possible)"
    r"|\b(?:we|will|can|able to)\s+(?:also\s+)?(?:offer\s+|provide\s+)?sponsor"
    r"|\bsponsor(?:s|ing)?\s+(?:your\s+|a\s+|the\s+)?(?:work\s+)?visa"
    r"|\boffer(?:s|ing)?\s+(?:\w+\s+){0,2}?(?:visa\s+)?sponsorship"
    r"|\bvisa\s+support\b"
    r"|sponsoris\w*\s+(?:de\s+|du\s+|votre\s+)?(?:visa|permis)"
    r"|prise\s+en\s+charge\s+(?:du|de\s+votre|des\s+frais\s+de)\s+(?:visa|permis)"
    r"|accompagnement\s+(?:pour|dans)\s+(?:l['\u2019]obtention\s+(?:du|d['\u2019]un)|votre)\s+(?:visa|permis)",
    re.IGNORECASE,
)
_REFUS = re.compile(
    r"\b(?:no|not|unable\s+to|cannot|can['\u2019]?t|won['\u2019]?t|do\s+not|does\s+not|don['\u2019]?t|"
    r"doesn['\u2019]?t|never)\s+(?:\w+\s+){0,3}?sponsor"
    r"|sponsorship\s+(?:is\s+)?not\s+(?:available|provided|offered)"
    r"|without\s+(?:the\s+need\s+for\s+)?(?:visa\s+)?sponsorship"
    r"|(?:pas|sans|aucun(?:e)?)\s+(?:de\s+)?(?:sponsoris|prise\s+en\s+charge\s+du\s+visa)",
    re.IGNORECASE,
)
_AUTORISATION = re.compile(
    r"must\s+(?:already\s+)?(?:be|have)\s+(?:legally\s+)?(?:authori[sz]ed|eligible|the\s+right)"
    r"\s+to\s+work"
    r"|(?:right|authori[sz]ation|eligibility)\s+to\s+work\s+(?:in|is\s+required)"
    r"|(?:être|etre)\s+(?:autoris\w+|en\s+droit)\s+(?:de|à|a)\s+travailler"
    r"|permis\s+de\s+travail\s+(?:valide\s+)?(?:requis|obligatoire|exigé)"
    r"|(?:autorisation|droit)\s+de\s+travail(?:ler)?\s+(?:en|dans|sur)",
    re.IGNORECASE,
)


def extract_mobility(texte: str) -> MobilityInfo:
    """Sponsoring et autorisation de travail déduits ligne par ligne.

    Sur une même ligne, une négation l'emporte (« no visa sponsorship » ne contient pas « offre »).
    Si l'annonce affirme et nie à des endroits différents, on ne tranche pas : `None`.
    """
    offert = refuse = autorisation = False
    for ligne in texte.splitlines():
        if _REFUS.search(ligne):
            refuse = True
        elif _OFFRE.search(ligne):
            offert = True
        if _AUTORISATION.search(ligne):
            autorisation = True
    if offert and refuse:
        sponsoring = None
    elif offert:
        sponsoring = VisaSponsorship.OFFERED
    elif refuse:
        sponsoring = VisaSponsorship.NOT_OFFERED
    else:
        sponsoring = None
    return MobilityInfo(sponsoring, True if autorisation else None)
