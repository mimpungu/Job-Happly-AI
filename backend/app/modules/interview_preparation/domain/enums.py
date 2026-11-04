from enum import StrEnum


class QuestionCategory(StrEnum):
    HR = "hr"
    BEHAVIORAL = "behavioral"
    TECHNICAL = "technical"


class QuestionSource(StrEnum):
    RULES = "rules"
    """Généré sans IA, à partir de règles et du parcours réel."""
    AI = "ai"


class AssistMode(StrEnum):
    """IA facultative, toujours demandée explicitement (jamais de simulation coûteuse en masse)."""

    NONE = "none"
    LOCAL = "local"
    """Modèle local : aucune donnée ne quitte la machine."""
    AI = "ai"
    """Passerelle IA complète, soumise aux réglages, au consentement et aux plafonds."""


class InterviewStage(StrEnum):
    HR_SCREEN = "hr_screen"
    TECHNICAL = "technical"
    MANAGER = "manager"
    FINAL = "final"
    OTHER = "other"


class InterviewFormat(StrEnum):
    PHONE = "phone"
    VIDEO = "video"
    ONSITE = "onsite"
    OTHER = "other"


class InterviewOutcome(StrEnum):
    PENDING = "pending"
    POSITIVE = "positive"
    NEGATIVE = "negative"
    CANCELLED = "cancelled"


class SimulationStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
