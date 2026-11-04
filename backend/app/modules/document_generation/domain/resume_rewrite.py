"""Garde-fou de la reformulation IA des réalisations du CV (TASK-012-08).

L'IA améliore la rédaction, elle ne crée pas de données : une reformulation n'est acceptée que
si elle n'ajoute ni chiffre, ni nom propre, ni sigle, ni technologie absents de la réalisation
d'origine ou du profil (compétences). Sinon on garde le texte de l'utilisateur, sans erreur :
la reformulation est un confort, pas une condition de génération.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.candidate_profile.domain.profile import ProfileDocument

_NOMBRE = re.compile(r"\d+(?:[.,]\d+)?")
_MOT = re.compile(r"[\w+#.\-]+", re.UNICODE)
_MAX_RATIO = 1.6
_MAX_EXTRA_CHARS = 40
_MAX_LENGTH = 400


@dataclass(frozen=True, slots=True)
class RewriteReport:
    """Bilan d'une reformulation, conservé avec la version du CV."""

    requested: str
    status: str
    """`not_requested` | `applied` | `partial` | `unchanged` | `unavailable`."""
    rewritten: int = 0
    rejected: int = 0
    provider: str | None = None
    model: str | None = None
    cache_hit: bool = False
    reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "requested": self.requested,
            "status": self.status,
            "rewritten": self.rewritten,
            "rejected": self.rejected,
            "provider": self.provider,
            "model": self.model,
            "cache_hit": self.cache_hit,
            "reason": self.reason,
        }


def _mots_remarquables(texte: str) -> set[str]:
    """Mots qui désignent une entité : majuscule interne, sigle, chiffre ou symbole techno."""
    remarquables: set[str] = set()
    mots = _MOT.findall(texte)
    for rang, mot in enumerate(mots):
        nu = mot.strip(".-")
        if not nu:
            continue
        sigle = len(nu) > 1 and nu.isupper()
        technique = any(c.isdigit() or c in "+#" for c in nu)
        majuscule = nu[0].isupper() and rang > 0
        if sigle or technique or majuscule:
            remarquables.add(nu.casefold())
    return remarquables


def known_terms(profile: ProfileDocument) -> set[str]:
    """Noms que le profil autorise : compétences, entreprises, établissements, certifications."""
    sources: list[str] = [s.name for s in profile.skills]
    sources += [e.company or "" for e in profile.experiences]
    sources += [e.institution or "" for e in profile.educations]
    sources += [c.name for c in profile.certifications]
    termes: set[str] = set()
    for texte in sources:
        termes.update(m.strip(".-").casefold() for m in _MOT.findall(texte))
    return termes


def is_acceptable_rewrite(original: str, candidate: str, *, allowed: Iterable[str] = ()) -> bool:
    """Vrai si `candidate` reformule `original` sans rien y ajouter."""
    texte = candidate.strip()
    if not texte or texte == original.strip() or len(texte) > _MAX_LENGTH:
        return False
    if len(texte) > len(original) * _MAX_RATIO + _MAX_EXTRA_CHARS:
        return False
    if "\n" in texte:
        return False
    if not set(_NOMBRE.findall(texte)) <= set(_NOMBRE.findall(original)):
        return False
    autorises = _mots_remarquables(original) | {t.casefold() for t in allowed}
    autorises |= {m.strip(".-").casefold() for m in _MOT.findall(original)}
    return _mots_remarquables(texte) <= autorises


def apply_rewrites(profile: ProfileDocument, rewrites: Mapping[str, str]) -> ProfileDocument:
    """Remplace les réalisations dont l'original figure dans `rewrites` (profil immuable)."""
    experiences = [
        exp.model_copy(update={"achievements": tuple(rewrites.get(a, a) for a in exp.achievements)})
        for exp in profile.experiences
    ]
    return profile.model_copy(update={"experiences": experiences})
