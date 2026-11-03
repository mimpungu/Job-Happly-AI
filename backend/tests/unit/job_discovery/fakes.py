"""Doubles de test, explicitement identifiés comme tels (jamais utilisés en production)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from app.modules.job_discovery.domain.connector import (
    ConnectorCapabilities,
    ConnectorOffer,
    HealthState,
    HealthStatus,
    SearchPage,
)
from app.modules.job_discovery.domain.criteria import SearchCriteria
from app.modules.job_discovery.domain.enums import SourceKind


class FakeClock:
    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.now += seconds


class FakeConnector:
    """Connecteur de TEST : exécute le comportement fourni, compte les appels."""

    kind = SourceKind.OFFICIAL_API

    def __init__(
        self,
        key: str = "fake",
        behaviour: Callable[[], Awaitable[SearchPage]] | None = None,
        capabilities: ConnectorCapabilities | None = None,
    ) -> None:
        self.key = key
        self.name = f"Faux {key}"
        self.calls = 0
        self._behaviour = behaviour
        self._capabilities = capabilities or ConnectorCapabilities(requests_per_second=1000)

    def get_capabilities(self) -> ConnectorCapabilities:
        return self._capabilities

    async def search(self, criteria: SearchCriteria) -> SearchPage:
        self.calls += 1
        if self._behaviour is None:
            return SearchPage(offers=())
        return await self._behaviour()

    async def get_details(self, external_id: str) -> ConnectorOffer | None:
        self.calls += 1
        return None

    async def health_check(self) -> HealthStatus:
        self.calls += 1
        return HealthStatus(HealthState.OK, datetime.now(UTC))


CRITERES = SearchCriteria(title="Data Analyst")
