"""Mesures du banc d'essai des modèles (fonctions pures, testées).

Aucune note de « qualité » n'est inventée : on mesure ce qui l'est objectivement (JSON conforme,
compétences réellement présentes dans le texte, vitesse, tokens) et on produit une comparaison
côte à côte que l'utilisateur relit.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from statistics import median


def _plier(texte: str) -> str:
    sans = "".join(
        c for c in unicodedata.normalize("NFD", texte.casefold()) if not unicodedata.combining(c)
    )
    return re.sub(r"[^a-z0-9+#.]+", " ", sans).strip()


def grounded_ratio(skills: list[str], source_text: str) -> float | None:
    """Part des compétences citées qui figurent réellement dans le texte de l'offre.

    Un ratio bas signale des compétences inventées ou « déduites ». `None` sans compétence.
    """
    if not skills:
        return None
    texte = f" {_plier(source_text)} "
    presentes = sum(1 for s in skills if f" {_plier(s)} " in texte)
    return presentes / len(skills)


def jaccard(a: list[str], b: list[str]) -> float:
    """Recouvrement entre deux listes de compétences (1 = identiques, 0 = rien en commun)."""
    ensemble_a, ensemble_b = {_plier(x) for x in a}, {_plier(x) for x in b}
    if not ensemble_a and not ensemble_b:
        return 1.0
    return len(ensemble_a & ensemble_b) / len(ensemble_a | ensemble_b)


@dataclass(slots=True)
class Run:
    """Résultat d'un modèle sur une offre."""

    ok: bool
    seconds: float
    input_tokens: int = 0
    output_tokens: int = 0
    skills: list[str] = field(default_factory=list)
    grounded: float | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class Summary:
    runs: int
    valid_rate: float
    median_seconds: float
    p90_seconds: float
    mean_grounded: float | None
    mean_skills: float
    input_tokens: int
    output_tokens: int


def summarize(runs: list[Run]) -> Summary:
    if not runs:
        raise ValueError("Aucun résultat à résumer.")
    valides = [r for r in runs if r.ok]
    durees = sorted(r.seconds for r in runs)
    rang = min(len(durees) - 1, max(0, round(0.9 * len(durees)) - 1))
    ancrages = [r.grounded for r in valides if r.grounded is not None]
    return Summary(
        runs=len(runs),
        valid_rate=len(valides) / len(runs),
        median_seconds=median(durees),
        p90_seconds=durees[rang],
        mean_grounded=sum(ancrages) / len(ancrages) if ancrages else None,
        mean_skills=sum(len(r.skills) for r in valides) / len(valides) if valides else 0.0,
        input_tokens=sum(r.input_tokens for r in runs),
        output_tokens=sum(r.output_tokens for r in runs),
    )


def estimated_cost(summary: Summary, input_per_million: float, output_per_million: float) -> float:
    """Coût qu'aurait ce volume de tokens au tarif payant donné (même pour un palier gratuit)."""
    return (
        summary.input_tokens * input_per_million + summary.output_tokens * output_per_million
    ) / 1_000_000
