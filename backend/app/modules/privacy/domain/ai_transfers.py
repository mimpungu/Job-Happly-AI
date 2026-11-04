"""Catalogue des données envoyées aux fournisseurs d'IA, par usage (TASK-018-12, 018-21).

Source unique de vérité : l'API de transparence l'expose, la documentation s'en inspire et un test
vérifie que chaque `task_type` du code y figure avec le même indicateur « données personnelles ».
Règle : n'envoyer que le contexte nécessaire, jamais le CV complet.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AITransfer:
    task_type: str
    purpose: str
    data_sent: str
    never_sent: str
    personal_data: bool
    optional: bool = True
    """Vrai si l'usage n'a lieu qu'à la demande explicite de l'utilisateur."""


AI_TRANSFERS: tuple[AITransfer, ...] = (
    AITransfer(
        task_type="offer_summary",
        purpose="Résumer une offre d'emploi",
        data_sent="Intitulé et texte public de l'offre (tronqué)",
        never_sent="Profil, CV, coordonnées",
        personal_data=False,
    ),
    AITransfer(
        task_type="cv_rewrite",
        purpose="Reformuler les réalisations d'un CV (option « local » ou « IA »)",
        data_sent="Texte des réalisations retenues pour le CV, numérotées",
        never_sent="Identité, coordonnées, employeurs, dates, CV complet",
        personal_data=True,
    ),
    AITransfer(
        task_type="interview_questions",
        purpose="Proposer des questions d'entretien spécifiques au poste",
        data_sent="Intitulé, entreprise, compétences et texte public de l'offre",
        never_sent="Profil, CV, réponses de l'utilisateur",
        personal_data=False,
    ),
    AITransfer(
        task_type="interview_review",
        purpose="Commenter la réponse de l'utilisateur lors d'une simulation d'entretien",
        data_sent="La question posée et la réponse saisie par l'utilisateur",
        never_sent="Profil, CV, identité, coordonnées",
        personal_data=True,
    ),
    AITransfer(
        task_type="platform_test",
        purpose="Vérifier que le fournisseur configuré répond (bouton de test)",
        data_sent="Une phrase fixe, sans donnée de l'utilisateur",
        never_sent="Toute donnée de l'utilisateur",
        personal_data=False,
    ),
    AITransfer(
        task_type="estimate",
        purpose="Estimer le coût d'une opération (aucun modèle n'est appelé)",
        data_sent="Rien : seule la taille du texte est utilisée pour le calcul, en local",
        never_sent="Tout contenu, profil, CV",
        personal_data=False,
    ),
)
