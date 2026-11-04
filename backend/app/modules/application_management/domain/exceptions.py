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


class OfferNotFoundError(ApplicationTrackingError):
    """L'offre n'existe pas ou n'appartient pas à l'utilisateur."""


class DocumentVersionNotFoundError(ApplicationTrackingError):
    """La version de document n'existe pas ou n'appartient pas à l'utilisateur."""


class DocumentKindMismatchError(ApplicationTrackingError):
    """La version fournie n'est pas du bon type (un CV n'est pas une lettre)."""


class DocumentLockedError(ApplicationTrackingError):
    """Le document envoyé ne peut plus être remplacé : il atteste de ce qui a été envoyé."""


class NothingToAttachError(ApplicationTrackingError):
    """Aucune version de document n'a été fournie."""


class AlreadySubmittedError(ApplicationTrackingError):
    """L'envoi de cette candidature a déjà été confirmé."""


class InvalidDateError(ApplicationTrackingError):
    """Date refusée (sans fuseau horaire, dans le futur ou hors contexte)."""
