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


class RewriteMode(StrEnum):
    """Qui reformule les réalisations du CV (TASK-012-08). Toujours un choix explicite."""

    NONE = "none"
    """Texte du profil tel quel : aucun appel IA (défaut)."""
    LOCAL = "local"
    """Modèle local : aucune donnée ne quitte la machine."""
    AI = "ai"
    """Passerelle IA complète (local d'abord, puis API payante si le réglage l'autorise)."""
