"""Pondérations par défaut et validation des pondérations personnalisées (TASK-009-08, 009-13)."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal

from app.modules.job_intelligence.domain.matching.models import Criterion, Weights

ALGORITHM_VERSION = "m1"
"""À incrémenter dès que la logique de calcul change : un score est reproductible pour une
version d'algorithme *et* une version de pondérations."""

MAX_WEIGHT = Decimal(100)

# Total 100 pour lire les poids comme des pourcentages. Les compétences et le métier portent le
# plus : ce sont les critères les plus discriminants et ceux que l'offre renseigne le mieux.
DEFAULT_WEIGHTS = Weights(
    {
        Criterion.JOB_TITLE: Decimal(20),
        Criterion.SKILLS: Decimal(25),
        Criterion.EXPERIENCE: Decimal(12),
        Criterion.EDUCATION: Decimal(5),
        Criterion.LOCATION: Decimal(10),
        Criterion.CONTRACT: Decimal(5),
        Criterion.SALARY: Decimal(5),
        Criterion.REMOTE: Decimal(5),
        Criterion.FRESHNESS: Decimal(3),
        Criterion.MANDATORY: Decimal(10),
    }
)


class InvalidWeightsError(ValueError):
    """Pondérations refusées (critère inconnu, poids négatif ou nul pour tous)."""


def validate_weights(brutes: dict[str, object]) -> Weights:
    """Construit des pondérations à partir d'une saisie utilisateur.

    Un critère absent garde son poids par défaut ; un poids à 0 le désactive. Au moins un
    critère doit rester actif, sinon aucun score n'est calculable.
    """
    valeurs = dict(DEFAULT_WEIGHTS.values)
    for cle, valeur in brutes.items():
        try:
            critere = Criterion(cle)
        except ValueError as erreur:
            raise InvalidWeightsError(f"Critère inconnu : {cle!r}.") from erreur
        if isinstance(valeur, bool) or not isinstance(valeur, int | float | str | Decimal):
            raise InvalidWeightsError(f"Poids invalide pour « {cle} ».")
        try:
            nombre = Decimal(str(valeur))
        except ArithmeticError as erreur:
            raise InvalidWeightsError(f"Poids invalide pour « {cle} ».") from erreur
        if not nombre.is_finite() or nombre < 0 or nombre > MAX_WEIGHT:
            raise InvalidWeightsError(f"Le poids de « {cle} » doit être compris entre 0 et 100.")
        valeurs[critere] = nombre
    resultat = Weights(valeurs)
    if resultat.total() <= 0:
        raise InvalidWeightsError("Au moins un critère doit avoir un poids supérieur à 0.")
    return resultat


def weights_version(poids: Weights) -> str:
    """Identifiant stable : version d'algorithme + empreinte des poids (indépendante de l'ordre)."""
    canonique = json.dumps(
        {c.value: format(poids.get(c).normalize(), "f") for c in Criterion}, sort_keys=True
    )
    return f"{ALGORITHM_VERSION}-{hashlib.sha256(canonique.encode()).hexdigest()[:8]}"
