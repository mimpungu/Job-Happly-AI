"""Contrat commun des sources d'offres (ADR-0006) : modèles, erreurs et interface."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from app.modules.job_discovery.domain.criteria import SearchCriteria
from app.modules.job_discovery.domain.enums import SourceKind
from app.modules.job_discovery.domain.offers import NormalizedOffer

# ---------------------------------------------------------------- erreurs


class ConnectorError(Exception):
    """Erreur d'une source. `retryable` indique si une nouvelle tentative a un sens."""

    retryable: bool = False

    def __init__(self, message: str, *, source_key: str | None = None) -> None:
        super().__init__(message)
        self.source_key = source_key


class NotConfiguredError(ConnectorError):
    """Configuration ou clé d'accès manquante : la source est signalée « non configurée »."""


class AuthenticationFailedError(ConnectorError):
    """Identifiants refusés par la source."""


class AccessDeniedError(ConnectorError):
    """Accès refusé (403, CAPTCHA, connexion exigée, robots.txt, CGU).

    Jamais contourné : la source est marquée « non supportée » (ADR-0006).
    """


class UnsupportedCriteriaError(ConnectorError):
    """La source ne sait pas traiter ces critères."""


class InvalidResponseError(ConnectorError):
    """Réponse illisible ou hors contrat (structure modifiée côté source)."""


class SourceUnavailableError(ConnectorError):
    """Source momentanément indisponible (réseau, 5xx)."""

    retryable = True


class SourceTimeoutError(SourceUnavailableError):
    """Délai d'attente dépassé."""


class RateLimitedError(ConnectorError):
    """Quota atteint ; `retry_after` (secondes) si la source l'indique."""

    retryable = True

    def __init__(
        self, message: str, *, retry_after: float | None = None, source_key: str | None = None
    ) -> None:
        super().__init__(message, source_key=source_key)
        self.retry_after = retry_after


class CircuitOpenError(SourceUnavailableError):
    """Disjoncteur ouvert : la source est écartée temporairement, sans appel réseau."""

    retryable = False


class UnexpectedConnectorError(ConnectorError):
    """Erreur imprévue d'un connecteur, enveloppée pour ne jamais bloquer les autres sources."""


# ---------------------------------------------------------------- modèles


class HealthState(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    NOT_CONFIGURED = "not_configured"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class HealthStatus:
    state: HealthState
    checked_at: datetime
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class ConnectorCapabilities:
    """Ce qu'une source sait faire : sert à choisir les sources compatibles avec une recherche."""

    countries: frozenset[str] = frozenset()
    """Pays couverts (ISO alpha-2). Vide = non restreint."""
    supports_keywords: bool = True
    supports_location: bool = False
    supports_radius: bool = False
    supports_salary_filter: bool = False
    supports_remote_filter: bool = False
    supports_published_since: bool = False
    requires_credentials: bool = False
    max_page_size: int = 50
    requests_per_second: float = 1.0
    """Limite de débit respectant les conditions de la source."""

    def covers(self, criteria: SearchCriteria) -> bool:
        """Faux si la recherche cible uniquement des pays hors de la couverture de la source."""
        if not self.countries or not criteria.country_codes:
            return True
        return bool(self.countries & set(criteria.country_codes))


@dataclass(frozen=True, slots=True)
class ConnectorOffer:
    """Offre renvoyée par une source : normalisée, avec sa donnée brute pour l'audit."""

    external_id: str
    offer: NormalizedOffer
    raw_payload: dict[str, Any]
    source_url: str | None = None


@dataclass(frozen=True, slots=True)
class SearchPage:
    offers: tuple[ConnectorOffer, ...]
    next_cursor: str | None = None
    total: int | None = None
    """Total annoncé par la source, `None` s'il est inconnu (jamais 0 par défaut)."""
    retrieved_at: datetime | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------- interface


@runtime_checkable
class JobSourceConnector(Protocol):
    """Contrat de toute source d'offres. Une source ne connaît ni la base ni les autres sources."""

    # Lecture seule : un connecteur enveloppé (résilience) expose ces valeurs sans les stocker.
    @property
    def key(self) -> str: ...

    @property
    def name(self) -> str: ...

    @property
    def kind(self) -> SourceKind: ...

    def get_capabilities(self) -> ConnectorCapabilities: ...

    async def search(self, criteria: SearchCriteria) -> SearchPage: ...

    async def get_details(self, external_id: str) -> ConnectorOffer | None:
        """Détails d'une offre ; `None` si elle n'existe plus."""
        ...

    async def health_check(self) -> HealthStatus: ...
