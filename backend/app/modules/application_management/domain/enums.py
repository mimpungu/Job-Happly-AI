from enum import StrEnum


class ApplicationStatus(StrEnum):
    """Statuts d'une candidature (spécification §12)."""

    NEW_OFFER = "new_offer"
    TO_ANALYZE = "to_analyze"
    TO_APPLY = "to_apply"
    DOCUMENTS_TO_PREPARE = "documents_to_prepare"
    READY_TO_SEND = "ready_to_send"
    SENT = "sent"
    PENDING = "pending"
    INTERVIEW = "interview"
    SECOND_INTERVIEW = "second_interview"
    OFFER_RECEIVED = "offer_received"
    REJECTED = "rejected"
    ABANDONED = "abandoned"


class EventKind(StrEnum):
    STATUS_CHANGE = "status_change"
    NOTE = "note"
    INTERVIEW = "interview"
    FOLLOW_UP = "follow_up"
    OTHER = "other"
