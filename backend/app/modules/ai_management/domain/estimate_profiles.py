"""Profils d'estimation des tâches IA de l'application (TASK-010-28).

Chaque profil reprend les bornes réelles de l'appel (niveau, texte maximal envoyé, sortie
maximale) pour afficher, avant l'opération, son coût **maximal** plausible. Un test vérifie que
chaque profil correspond à une tâche déclarée au catalogue des transferts de données.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EstimateProfile:
    task_type: str
    level: int
    max_characters: int
    """Texte maximal envoyé au modèle pour cette tâche (bornes du code appelant)."""
    max_output_tokens: int
    label: str
    baseline: str
    """Traitement déterministe (niveau 0) qui fonctionne sans IA : l'IA ne fait que l'enrichir."""


ESTIMATE_PROFILES: dict[str, EstimateProfile] = {
    p.task_type: p
    for p in (
        EstimateProfile(
            "offer_summary",
            1,
            6_100,
            600,
            "Résumé d'une offre par l'IA",
            "Analyse de l'offre par règles (compétences, expérience, formation)",
        ),
        EstimateProfile(
            "interview_questions",
            1,
            6_300,
            900,
            "Questions d'entretien par l'IA",
            "Préparation d'entretien sans IA (questions types, trames de réponse)",
        ),
        EstimateProfile(
            "interview_review",
            1,
            3_000,
            500,
            "Commentaires sur une réponse",
            "Score et retours de simulation calculés par règles",
        ),
        EstimateProfile(
            "cv_rewrite",
            1,
            4_000,
            4_000,
            "Reformulation des réalisations du CV",
            "CV généré avec les réalisations d'origine, sans reformulation",
        ),
    )
}
