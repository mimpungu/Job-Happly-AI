"""Erreurs métier de la préparation aux entretiens (EPIC 016). Messages affichables tels quels."""


class InterviewPreparationError(Exception):
    pass


class PreparationNotFoundError(InterviewPreparationError):
    pass


class PreparationRequiredError(InterviewPreparationError):
    """Une simulation s'appuie sur une préparation existante."""


class SimulationNotFoundError(InterviewPreparationError):
    pass


class SimulationClosedError(InterviewPreparationError):
    """Une simulation terminée n'est plus modifiable : elle sert d'historique."""


class UnknownQuestionError(InterviewPreparationError):
    pass


class InterviewNotFoundError(InterviewPreparationError):
    pass


class NoValidatedProfileError(InterviewPreparationError):
    pass


class InvalidInterviewDateError(InterviewPreparationError):
    pass


class CoachUnavailableError(InterviewPreparationError):
    """L'IA demandée n'a pas pu répondre (désactivée, plafond, consentement, panne)."""
