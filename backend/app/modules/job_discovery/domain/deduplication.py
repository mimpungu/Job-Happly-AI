"""Déduplication déterministe des offres (aucun appel IA, ADR-0006).

Ordre de décision, du plus sûr au moins sûr :
1. même identifiant externe sur la même source (géré par la base : contrainte d'unicité) ;
2. même URL canonique ;
3. même entreprise + même intitulé normalisé + lieu compatible + descriptions très proches.

Prudence : en cas de doute on garde deux offres. Fusionner à tort deux offres distinctes
(même poste dans deux villes) fait perdre une opportunité ; garder un doublon est sans gravité.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.modules.job_discovery.domain.normalization import parse_location, title_key
from app.modules.job_discovery.domain.offers import NormalizedOffer
from app.modules.job_discovery.domain.text import normalize_text

_PARAMETRES_DE_SUIVI_EXACTS = frozenset(
    {"gclid", "fbclid", "msclkid", "mc_cid", "mc_eid", "ref", "referrer", "source", "src", "trk"}
)
_PORTS_PAR_DEFAUT = {"http": 80, "https": 443}


def canonicalize_url(url: str) -> str | None:
    """URL canonique : hôte en minuscules, sans fragment ni paramètre de suivi, paramètres triés.

    Retourne `None` pour une URL inexploitable (on ne fabrique pas de clé de comparaison).
    """
    morceaux = urlsplit(url.strip())
    if morceaux.scheme not in ("http", "https") or not morceaux.hostname:
        return None
    hote = morceaux.hostname.lower().removeprefix("www.")
    port = morceaux.port
    netloc = hote if port in (None, _PORTS_PAR_DEFAUT[morceaux.scheme]) else f"{hote}:{port}"
    chemin = morceaux.path.rstrip("/") or "/"
    parametres = sorted(
        (cle, valeur)
        for cle, valeur in parse_qsl(morceaux.query, keep_blank_values=False)
        if not cle.lower().startswith("utm_") and cle.lower() not in _PARAMETRES_DE_SUIVI_EXACTS
    )
    return urlunsplit(("https", netloc, chemin, urlencode(parametres), ""))


def _mots(texte: str) -> list[str]:
    return normalize_text(texte).split()


def description_similarity(a: str, b: str, *, taille_motif: int = 4) -> float:
    """Similarité de Jaccard sur des suites de mots (0 à 1). Deux textes vides ne sont pas
    « identiques » : sans contenu on ne peut rien affirmer."""
    mots_a, mots_b = _mots(a), _mots(b)
    if len(mots_a) < taille_motif or len(mots_b) < taille_motif:
        return 0.0
    motifs_a = {tuple(mots_a[i : i + taille_motif]) for i in range(len(mots_a) - taille_motif + 1)}
    motifs_b = {tuple(mots_b[i : i + taille_motif]) for i in range(len(mots_b) - taille_motif + 1)}
    return len(motifs_a & motifs_b) / len(motifs_a | motifs_b)


@dataclass(frozen=True, slots=True)
class DuplicateVerdict:
    duplicate: bool
    score: float
    reasons: tuple[str, ...]


def assess_duplicate(
    a: NormalizedOffer,
    b: NormalizedOffer,
    *,
    seuil_description: float = 0.85,
    ecart_publication: timedelta = timedelta(days=60),
) -> DuplicateVerdict:
    """Deux offres décrivent-elles le même poste ? Toutes les conditions doivent être réunies."""
    ca, cb = canonicalize_url(a.canonical_url or ""), canonicalize_url(b.canonical_url or "")
    if ca is not None and ca == cb:
        return DuplicateVerdict(True, 1.0, ("même URL canonique",))

    if not a.company_name or not b.company_name:
        return DuplicateVerdict(False, 0.0, ("entreprise inconnue",))
    if normalize_text(a.company_name) != normalize_text(b.company_name):
        return DuplicateVerdict(False, 0.0, ("entreprises différentes",))
    if title_key(a.title) != title_key(b.title):
        return DuplicateVerdict(False, 0.0, ("intitulés différents",))

    lieu_a, lieu_b = parse_location(a.location), parse_location(b.location)
    if lieu_a.key and lieu_b.key and lieu_a.key != lieu_b.key:
        return DuplicateVerdict(False, 0.0, ("lieux différents",))
    if lieu_a.country_code and lieu_b.country_code and lieu_a.country_code != lieu_b.country_code:
        return DuplicateVerdict(False, 0.0, ("pays différents",))
    if (
        a.published_at
        and b.published_at
        and abs(a.published_at - b.published_at) > ecart_publication
    ):
        return DuplicateVerdict(False, 0.0, ("publications très éloignées",))

    similarite = description_similarity(a.description, b.description)
    if similarite < seuil_description:
        return DuplicateVerdict(False, similarite, ("descriptions trop différentes",))
    raisons = ["même entreprise", "même intitulé", "lieu compatible", "descriptions très proches"]
    return DuplicateVerdict(True, similarite, tuple(raisons))
