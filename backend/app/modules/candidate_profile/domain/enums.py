from enum import StrEnum


class DataOrigin(StrEnum):
    """Origine d'une information du profil (traçabilité, spec §9.1)."""

    IMPORTED = "imported"
    MANUAL = "manual"


class ProfileStatus(StrEnum):
    DRAFT = "draft"
    VALIDATED = "validated"
    ARCHIVED = "archived"


class LanguageProficiency(StrEnum):
    A1 = "a1"
    A2 = "a2"
    B1 = "b1"
    B2 = "b2"
    C1 = "c1"
    C2 = "c2"
    NATIVE = "native"
