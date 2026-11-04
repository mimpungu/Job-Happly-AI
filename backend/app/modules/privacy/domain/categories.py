"""Catégories de données personnelles, dépendances et politique de conservation (RGPD, EPIC 018).

Chaque table qui porte un `owner_id` DOIT figurer dans exactement une catégorie : un test le
vérifie, donc une nouvelle table force une décision explicite d'export, de conservation et de
suppression (principe de minimisation et droit à l'effacement).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class DataCategory(StrEnum):
    PROFILE = "profile"
    DOCUMENTS = "documents"
    APPLICATIONS = "applications"
    INTERVIEWS = "interviews"
    OFFERS = "offers"
    AI_ACTIVITY = "ai_activity"
    NOTIFICATIONS = "notifications"
    SETTINGS = "settings"


CATEGORY_LABELS: dict[DataCategory, str] = {
    DataCategory.PROFILE: "Profil maître (identité, expériences, formations, compétences)",
    DataCategory.DOCUMENTS: "CV et lettres générés (versions et fichiers PDF)",
    DataCategory.APPLICATIONS: "Candidatures, historique, contacts et leurs entretiens",
    DataCategory.INTERVIEWS: "Préparations, simulations et fiches d'entretien",
    DataCategory.OFFERS: "Offres, sources, recherches, entreprises, analyses et scores",
    DataCategory.AI_ACTIVITY: "Journal des appels IA et cache des réponses",
    DataCategory.NOTIFICATIONS: "Notifications et tâches planifiées",
    DataCategory.SETTINGS: "Réglages (IA, budgets, pondération, notifications)",
}

CATEGORY_TABLES: dict[DataCategory, tuple[str, ...]] = {
    DataCategory.PROFILE: (
        "candidates",
        "candidate_profiles",
        "experiences",
        "educations",
        "certifications",
        "skills",
        "profile_languages",
        "profile_changes",
    ),
    DataCategory.DOCUMENTS: ("generated_documents", "document_versions"),
    DataCategory.APPLICATIONS: (
        "applications",
        "application_events",
        "application_contacts",
        "application_documents",
    ),
    DataCategory.INTERVIEWS: ("interview_preparations", "interview_simulations", "interviews"),
    DataCategory.OFFERS: (
        "job_sources",
        "job_offers",
        "job_offer_sources",
        "job_offer_revisions",
        "job_offer_states",
        "saved_searches",
        "search_runs",
        "target_companies",
        "job_analyses",
        "job_match_scores",
    ),
    DataCategory.AI_ACTIVITY: ("ai_usages", "ai_cache_entries"),
    DataCategory.NOTIFICATIONS: ("notifications", "scheduled_tasks"),
    DataCategory.SETTINGS: (
        "ai_settings",
        "ai_budgets",
        "matching_settings",
        "notification_preferences",
    ),
}

# Tables techniques : jamais exportées par catégorie (compte local, file de tâches de fond).
SYSTEM_TABLES = frozenset({"users", "jobs"})

# Catégories à supprimer avant d'autres (clé étrangère protégée) : supprimer les offres suivies
# par une candidature est refusé avec un message clair plutôt qu'une erreur de base.
BLOCKED_BY: dict[DataCategory, DataCategory] = {DataCategory.OFFERS: DataCategory.APPLICATIONS}

CONFIRMATION_WORD = "SUPPRIMER"


@dataclass(frozen=True)
class RetentionRule:
    table: str
    category: DataCategory
    days: int | None
    """`None` : conservé jusqu'à suppression par l'utilisateur."""
    description: str
    automatic: bool = False
    """Vrai si la règle est appliquée par la purge de conservation."""


RETENTION_RULES: tuple[RetentionRule, ...] = (
    RetentionRule(
        "ai_cache_entries", DataCategory.AI_ACTIVITY, 30, "Réponses IA mises en cache", True
    ),
    RetentionRule(
        "ai_usages", DataCategory.AI_ACTIVITY, 365, "Journal des appels IA (comptabilité)", True
    ),
    RetentionRule("notifications", DataCategory.NOTIFICATIONS, 90, "Notifications lues", True),
    RetentionRule("search_runs", DataCategory.OFFERS, 180, "Historique des recherches", True),
    RetentionRule("jobs", DataCategory.NOTIFICATIONS, 30, "Tâches de fond terminées", True),
    RetentionRule(
        "candidate_profiles", DataCategory.PROFILE, None, "Profil maître et ses versions"
    ),
    RetentionRule("document_versions", DataCategory.DOCUMENTS, None, "CV et lettres générés"),
    RetentionRule("applications", DataCategory.APPLICATIONS, None, "Candidatures et historique"),
    RetentionRule(
        "interviews", DataCategory.INTERVIEWS, None, "Entretiens, préparations et simulations"
    ),
    RetentionRule("job_offers", DataCategory.OFFERS, None, "Offres collectées"),
)
