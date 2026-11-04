"""Exceptions métier pour le suivi des candidatures (EPIC 014)."""


class ApplicationTrackingError(Exception):
    """Exception de base pour le module de suivi des candidatures."""


class ApplicationNotFoundError(ApplicationTrackingError):
    """Candidature introuvable pour l'identifiant et le propriétaire donnés."""


class DuplicateApplicationError(ApplicationTrackingError):
    """Une candidature existe déjà pour cette offre et ce propriétaire."""


class InvalidStatusTransitionError(ApplicationTrackingError):
    """Transition de statut non autorisée selon les règles métier."""


class IncompleteDossierError(ApplicationTrackingError):
    """Le dossier de candidature est incomplet (documents manquants ou non compilés)."""


class ExternalOfferLinkMissingError(ApplicationTrackingError):
    """L'offre associée ne possède aucune URL de candidature externe."""

