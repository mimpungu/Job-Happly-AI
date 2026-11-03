"""Erreurs métier de la plateforme IA. Les messages sont affichables tels quels à l'utilisateur."""

from __future__ import annotations


class AIError(Exception):
    """Base des erreurs de la plateforme IA."""

    code = "ai_error"


class AIDisabledError(AIError):
    code = "ai_disabled"


class AINotConfiguredError(AIError):
    """Aucun fournisseur configuré (ou clé absente)."""

    code = "ai_not_configured"


class ConsentRequiredError(AIError):
    """L'utilisateur n'a pas encore vu ni accepté quelles données partent vers le fournisseur."""

    code = "ai_consent_required"


class BudgetNotDefinedError(AIError):
    """Aucun plafond défini : aucun appel payant n'est possible (ADR-0005)."""

    code = "ai_budget_not_defined"


class BudgetExceededError(AIError):
    """Le coût estimé ferait dépasser un plafond : l'appel n'est pas lancé."""

    code = "ai_budget_exceeded"


class ProviderFailureError(AIError):
    """Le fournisseur a échoué (réseau, quota, erreur) : rien n'est facturé par nous."""

    code = "ai_provider_failure"


class InvalidOutputError(AIError):
    """Sortie non conforme au schéma attendu : elle n'est ni utilisée ni mise en cache."""

    code = "ai_invalid_output"


class IncompleteOutputError(AIError):
    """Réponse tronquée par la limite de tokens."""

    code = "ai_incomplete_output"
