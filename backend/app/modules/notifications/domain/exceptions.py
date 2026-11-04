"""Exceptions métier du module de notifications et de planification."""

from __future__ import annotations


class NotificationError(Exception):
    """Exception de base pour les notifications."""


class NotificationNotFoundError(NotificationError):
    """La notification demandée n'existe pas ou n'appartient pas à l'utilisateur."""


class ScheduledTaskError(Exception):
    """Exception de base pour les tâches planifiées."""


class ScheduledTaskNotFoundError(ScheduledTaskError):
    """La tâche planifiée demandée n'existe pas ou n'appartient pas à l'utilisateur."""


class InvalidTimezoneError(ScheduledTaskError):
    """Le fuseau horaire spécifié n'est pas reconnu."""


class InvalidFrequencyError(ScheduledTaskError):
    """La configuration de fréquence ou d'intervalle est invalide."""


class EmailConsentRequiredError(NotificationError):
    """L'envoi d'e-mail requiert le consentement explicite de l'utilisateur."""


class EmailNotConfiguredError(NotificationError):
    """Le canal e-mail n'est pas configuré ou l'adresse du destinataire est manquante."""

