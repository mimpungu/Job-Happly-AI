"""Résilience des connecteurs : délai maximal, nouvelles tentatives, débit, disjoncteur.

Une source externe est toujours considérée comme non fiable. Aucune erreur n'est avalée :
chaque échec est journalisé (sans contenu d'annonce ni donnée personnelle) puis remonté sous la
forme d'une `ConnectorError`, pour qu'une source en échec n'arrête jamais les autres.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from app.modules.job_discovery.domain.connector import (
    CircuitOpenError,
    ConnectorCapabilities,
    ConnectorError,
    ConnectorOffer,
    HealthState,
    HealthStatus,
    JobSourceConnector,
    RateLimitedError,
    SearchPage,
    SourceTimeoutError,
    SourceUnavailableError,
    UnexpectedConnectorError,
)
from app.modules.job_discovery.domain.criteria import SearchCriteria
from app.modules.job_discovery.domain.enums import SourceKind

logger = logging.getLogger("happly.connectors")

Sleep = Callable[[float], Awaitable[None]]
Clock = Callable[[], float]


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Backoff exponentiel avec gigue ; seules les erreurs `retryable` sont rejouées."""

    max_attempts: int = 3
    base_delay: float = 0.5
    max_delay: float = 8.0
    jitter: float = 0.2

    def __post_init__(self) -> None:
        if self.max_attempts < 1 or self.base_delay < 0 or self.max_delay < self.base_delay:
            raise ValueError("Politique de nouvelles tentatives invalide.")
        if not 0 <= self.jitter <= 1:
            raise ValueError("La gigue doit être comprise entre 0 et 1.")

    def delay_for(self, attempt: int, error: ConnectorError, rng: random.Random) -> float:
        """Délai avant la tentative suivante (`attempt` commence à 1)."""
        if isinstance(error, RateLimitedError) and error.retry_after is not None:
            return min(error.retry_after, self.max_delay)
        base = min(self.base_delay * (2 ** (attempt - 1)), self.max_delay)
        return float(base * (1 + rng.uniform(-self.jitter, self.jitter)))


class RateLimiter:
    """Seau à jetons : `rate` requêtes par seconde, rafale maximale `burst`."""

    def __init__(
        self,
        rate: float,
        burst: int = 1,
        *,
        clock: Clock = time.monotonic,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        if rate <= 0 or burst < 1:
            raise ValueError("Débit et rafale doivent être strictement positifs.")
        self._rate = rate
        self._burst = burst
        self._clock = clock
        self._sleep = sleep
        self._tokens = float(burst)
        self._updated = clock()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            while True:
                now = self._clock()
                self._tokens = min(self._burst, self._tokens + (now - self._updated) * self._rate)
                self._updated = now
                if self._tokens >= 1:
                    self._tokens -= 1
                    return
                await self._sleep((1 - self._tokens) / self._rate)


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Écarte une source qui échoue de façon répétée, puis la re-teste prudemment."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        *,
        clock: Clock = time.monotonic,
    ) -> None:
        if failure_threshold < 1 or recovery_timeout <= 0:
            raise ValueError("Paramètres de disjoncteur invalides.")
        self._threshold = failure_threshold
        self._recovery = recovery_timeout
        self._clock = clock
        self._failures = 0
        self._opened_at: float | None = None
        self._probing = False

    @property
    def state(self) -> CircuitState:
        if self._opened_at is None:
            return CircuitState.CLOSED
        if self._clock() - self._opened_at >= self._recovery:
            return CircuitState.HALF_OPEN
        return CircuitState.OPEN

    def allow(self) -> bool:
        """Autorise un appel. En demi-ouverture, un seul appel d'essai est admis à la fois."""
        match self.state:
            case CircuitState.CLOSED:
                return True
            case CircuitState.OPEN:
                return False
            case CircuitState.HALF_OPEN:
                if self._probing:
                    return False
                self._probing = True
                return True

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None
        self._probing = False

    def release_probe(self) -> None:
        """Libère l'appel d'essai quand son échec n'est pas une panne de disponibilité."""
        self._probing = False

    def record_failure(self) -> None:
        self._probing = False
        self._failures += 1
        if self._opened_at is not None or self._failures >= self._threshold:
            self._opened_at = self._clock()


def _compte_pour_disjoncteur(error: ConnectorError) -> bool:
    """Seules les pannes de disponibilité ouvrent le disjoncteur (pas un quota ni un refus)."""
    return isinstance(error, SourceUnavailableError | UnexpectedConnectorError)


class ResilientConnector:
    """Enveloppe un connecteur avec délai, nouvelles tentatives, débit et disjoncteur."""

    def __init__(
        self,
        inner: JobSourceConnector,
        *,
        timeout: float = 15.0,
        retry: RetryPolicy | None = None,
        limiter: RateLimiter | None = None,
        breaker: CircuitBreaker | None = None,
        sleep: Sleep = asyncio.sleep,
        rng: random.Random | None = None,
    ) -> None:
        if timeout <= 0:
            raise ValueError("Le délai maximal doit être positif.")
        self._inner = inner
        self._timeout = timeout
        self._retry = retry or RetryPolicy()
        capacities = inner.get_capabilities()
        self._limiter = limiter or RateLimiter(capacities.requests_per_second)
        self._breaker = breaker or CircuitBreaker()
        self._sleep = sleep
        self._rng = rng or random.Random()  # noqa: S311 - gigue de backoff, pas de cryptographie

    @property
    def key(self) -> str:
        return self._inner.key

    @property
    def name(self) -> str:
        return self._inner.name

    @property
    def kind(self) -> SourceKind:
        return self._inner.kind

    @property
    def breaker(self) -> CircuitBreaker:
        return self._breaker

    def get_capabilities(self) -> ConnectorCapabilities:
        return self._inner.get_capabilities()

    async def search(self, criteria: SearchCriteria) -> SearchPage:
        return await self._execute("search", lambda: self._inner.search(criteria))

    async def get_details(self, external_id: str) -> ConnectorOffer | None:
        return await self._execute("get_details", lambda: self._inner.get_details(external_id))

    async def health_check(self) -> HealthStatus:
        try:
            return await self._execute("health_check", self._inner.health_check)
        except ConnectorError as erreur:
            return HealthStatus(
                state=HealthState.UNAVAILABLE,
                checked_at=datetime.now(UTC),
                detail=type(erreur).__name__,
            )

    async def _execute[T](self, operation: str, appel: Callable[[], Awaitable[T]]) -> T:
        for tentative in range(1, self._retry.max_attempts + 1):
            if not self._breaker.allow():
                raise CircuitOpenError("Source temporairement écartée.", source_key=self.key)
            await self._limiter.acquire()
            try:
                async with asyncio.timeout(self._timeout):
                    resultat = await appel()
            except TimeoutError:
                erreur: ConnectorError = SourceTimeoutError(
                    f"Délai de {self._timeout}s dépassé.", source_key=self.key
                )
            except ConnectorError as echec:
                erreur = echec
                erreur.source_key = erreur.source_key or self.key
            except asyncio.CancelledError:
                raise
            except Exception as imprevue:
                erreur = UnexpectedConnectorError(
                    f"Erreur imprévue : {type(imprevue).__name__}", source_key=self.key
                )
                erreur.__cause__ = imprevue
            else:
                self._breaker.record_success()
                return resultat

            if _compte_pour_disjoncteur(erreur):
                self._breaker.record_failure()
            else:
                self._breaker.release_probe()
            self._journaliser(operation, tentative, erreur)
            if not erreur.retryable or tentative == self._retry.max_attempts:
                raise erreur
            await self._sleep(self._retry.delay_for(tentative, erreur, self._rng))
        raise AssertionError("inatteignable")  # pragma: no cover

    def _journaliser(self, operation: str, tentative: int, erreur: ConnectorError) -> None:
        # Aucun contenu d'annonce, aucune donnée personnelle ni clé : type d'erreur seulement.
        logger.warning(
            "Échec connecteur",
            extra={
                "source": self.key,
                "operation": operation,
                "attempt": tentative,
                "error_type": type(erreur).__name__,
                "retryable": erreur.retryable,
            },
        )
