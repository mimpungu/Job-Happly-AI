from enum import StrEnum


class SourceKind(StrEnum):
    OFFICIAL_API = "official_api"
    PUBLIC_ATS = "public_ats"
    PUBLIC_PAGE = "public_page"
    MANUAL = "manual"


class OfferStatus(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    ARCHIVED = "archived"


class OfferState(StrEnum):
    SAVED = "saved"
    IGNORED = "ignored"


class SearchRunStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
