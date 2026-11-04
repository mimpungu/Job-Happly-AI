"""Registre des sources : enregistrement, activation et état de santé."""

from __future__ import annotations

from app.modules.job_discovery.domain.connector import HealthStatus, JobSourceConnector
from app.modules.job_discovery.domain.criteria import SearchCriteria


class UnknownSourceError(KeyError):
    """Aucune source enregistrée sous cette clé."""


class DuplicateSourceError(ValueError):
    """Une source est déjà enregistrée sous cette clé."""


class ConnectorRegistry:
    """Garde les connecteurs et leur état. Aucune source n'est active sans décision explicite."""

    def __init__(self) -> None:
        self._connectors: dict[str, JobSourceConnector] = {}
        self._enabled: set[str] = set()
        self._health: dict[str, HealthStatus] = {}

    def register(self, connector: JobSourceConnector, *, enabled: bool = False) -> None:
        if connector.key in self._connectors:
            raise DuplicateSourceError(f"Source déjà enregistrée : {connector.key!r}")
        self._connectors[connector.key] = connector
        if enabled:
            self._enabled.add(connector.key)

    def get(self, key: str) -> JobSourceConnector:
        try:
            return self._connectors[key]
        except KeyError:
            raise UnknownSourceError(key) from None

    def all(self) -> tuple[JobSourceConnector, ...]:
        return tuple(self._connectors.values())

    def enable(self, key: str) -> None:
        self.get(key)
        self._enabled.add(key)

    def disable(self, key: str) -> None:
        self.get(key)
        self._enabled.discard(key)

    def is_enabled(self, key: str) -> bool:
        self.get(key)
        return key in self._enabled

    def enabled(self) -> tuple[JobSourceConnector, ...]:
        return tuple(c for c in self._connectors.values() if c.key in self._enabled)

    def compatible_with(self, criteria: SearchCriteria) -> tuple[JobSourceConnector, ...]:
        """Sources actives dont la couverture correspond à la recherche."""
        return tuple(c for c in self.enabled() if c.get_capabilities().covers(criteria))

    def record_health(self, key: str, status: HealthStatus) -> None:
        self.get(key)
        self._health[key] = status

    def health(self, key: str) -> HealthStatus | None:
        self.get(key)
        return self._health.get(key)
