from enum import StrEnum


class DocumentKind(StrEnum):
    CV = "cv"
    COVER_LETTER = "cover_letter"


class ATSCheckStatus(StrEnum):
    PASS = "pass"  # noqa: S105
    WARNING = "warning"
    FAIL = "fail"


class LengthTarget(StrEnum):
    ONE_PAGE = "one_page"
    TWO_PAGES = "two_pages"
    AUTO = "auto"


class ResumeTemplateStyle(StrEnum):
    CLASSIC = "classic"
    COMPACT = "compact"
    MODERN = "modern"
