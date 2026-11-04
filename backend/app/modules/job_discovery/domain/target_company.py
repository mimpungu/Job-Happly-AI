"""Entreprises suivies par l'utilisateur et détection de leur source publique d'offres."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlsplit


class AtsKind(StrEnum):
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    ASHBY = "ashby"
    WORKABLE = "workable"
    CAREERS_PAGE = "careers_page"
    UNSUPPORTED = "unsupported"


class DetectionStatus(StrEnum):
    PENDING = "pending"
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class DetectedSource:
    ats_kind: AtsKind
    token: str | None
    region: str | None
    method: str


_HOTES_GREENHOUSE = {"boards.greenhouse.io", "job-boards.greenhouse.io", "boards.eu.greenhouse.io"}
_HOTES_LEVER = {"jobs.lever.co": "global", "jobs.eu.lever.co": "eu"}
_HOTE_ASHBY = "jobs.ashbyhq.com"
_HOTE_WORKABLE = "apply.workable.com"
# Chemins d'apply.workable.com qui ne désignent pas un compte (« /j/<code> » est le lien court
# d'une offre, sans le compte : il ne permet pas de retrouver le board).
_CHEMINS_WORKABLE_RESERVES = frozenset({"j", "api"})


def detect_from_url(url: str) -> DetectedSource | None:
    """Reconnaît un ATS public d'après l'URL d'une page carrières (sans aucun accès réseau).

    Retourne `None` si l'URL n'est pas celle d'un ATS connu : la détection n'invente rien.
    """
    morceaux = urlsplit(url.strip())
    if morceaux.scheme != "https" or not morceaux.hostname:
        return None
    segments = [s for s in morceaux.path.split("/") if s]
    if not segments:
        return None
    jeton = segments[0]
    hote = morceaux.hostname.lower()
    if hote in _HOTES_GREENHOUSE:
        return DetectedSource(AtsKind.GREENHOUSE, jeton, None, "url_pattern")
    if hote in _HOTES_LEVER:
        return DetectedSource(AtsKind.LEVER, jeton, _HOTES_LEVER[hote], "url_pattern")
    if hote == _HOTE_ASHBY:
        return DetectedSource(AtsKind.ASHBY, jeton, None, "url_pattern")
    if hote == _HOTE_WORKABLE and jeton.lower() not in _CHEMINS_WORKABLE_RESERVES:
        return DetectedSource(AtsKind.WORKABLE, jeton, None, "url_pattern")
    return None
