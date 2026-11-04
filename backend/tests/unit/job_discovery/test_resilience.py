import asyncio
import logging
import random
from collections.abc import Awaitable, Callable

import pytest

from app.modules.job_discovery.domain.connector import (
    AccessDeniedError,
    CircuitOpenError,
    InvalidResponseError,
    RateLimitedError,
    SearchPage,
    SourceTimeoutError,
    SourceUnavailableError,
    UnexpectedConnectorError,
)
from app.modules.job_discovery.infrastructure.resilience import (
    CircuitBreaker,
    CircuitState,
    RateLimiter,
    ResilientConnector,
    RetryPolicy,
)

from .fakes import CRITERES, FakeClock, FakeConnector

PAGE = SearchPage(offers=())


def _resilient(
    behaviour: Callable[[], Awaitable[SearchPage]] | None,
    clock: FakeClock,
    *,
    attempts: int = 3,
    timeout: float = 5.0,
    breaker: CircuitBreaker | None = None,
) -> tuple[ResilientConnector, FakeConnector]:
    inner = FakeConnector("src", behaviour)
    connecteur = ResilientConnector(
        inner,
        timeout=timeout,
        retry=RetryPolicy(max_attempts=attempts, base_delay=1.0, max_delay=8.0, jitter=0.0),
        limiter=RateLimiter(1000, burst=1000, clock=clock, sleep=clock.sleep),
        breaker=breaker or CircuitBreaker(3, 60, clock=clock),
        sleep=clock.sleep,
        rng=random.Random(0),
    )
    return connecteur, inner


class TestRetry:
    async def test_reessaie_apres_une_indisponibilite_puis_reussit(self) -> None:
        horloge = FakeClock()
        appels = {"n": 0}

        async def comportement() -> SearchPage:
            appels["n"] += 1
            if appels["n"] < 3:
                raise SourceUnavailableError("500")
            return PAGE

        connecteur, inner = _resilient(comportement, horloge)

        assert await connecteur.search(CRITERES) == PAGE
        assert inner.calls == 3
        assert horloge.now == pytest.approx(1000.0 + 1.0 + 2.0)  # backoff exponentiel

    async def test_abandonne_apres_le_nombre_maximal_de_tentatives(self) -> None:
        async def comportement() -> SearchPage:
            raise SourceUnavailableError("500")

        connecteur, inner = _resilient(comportement, FakeClock(), attempts=3)

        with pytest.raises(SourceUnavailableError):
            await connecteur.search(CRITERES)
        assert inner.calls == 3

    @pytest.mark.parametrize("erreur", [AccessDeniedError("403"), InvalidResponseError("?")])
    async def test_ne_rejoue_pas_une_erreur_definitive(self, erreur: Exception) -> None:
        async def comportement() -> SearchPage:
            raise erreur

        connecteur, inner = _resilient(comportement, FakeClock())

        with pytest.raises(type(erreur)):
            await connecteur.search(CRITERES)
        assert inner.calls == 1

    async def test_respecte_le_retry_after_de_la_source(self) -> None:
        horloge = FakeClock()
        appels = {"n": 0}

        async def comportement() -> SearchPage:
            appels["n"] += 1
            if appels["n"] == 1:
                raise RateLimitedError("quota", retry_after=5.0)
            return PAGE

        connecteur, _ = _resilient(comportement, horloge)
        await connecteur.search(CRITERES)

        assert horloge.now == pytest.approx(1005.0)

    def test_politique_invalide_refusee(self) -> None:
        with pytest.raises(ValueError):
            RetryPolicy(max_attempts=0)
        with pytest.raises(ValueError):
            RetryPolicy(jitter=2)


class TestTimeout:
    async def test_un_appel_trop_long_devient_une_erreur_de_delai(self) -> None:
        async def comportement() -> SearchPage:
            await asyncio.sleep(10)
            return PAGE

        connecteur, _ = _resilient(comportement, FakeClock(), attempts=1, timeout=0.05)

        with pytest.raises(SourceTimeoutError):
            await connecteur.search(CRITERES)


class TestIsolationDesErreurs:
    async def test_une_exception_imprevue_est_enveloppee_et_journalisee(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        async def comportement() -> SearchPage:
            raise KeyError("champ secret-xyz")

        connecteur, _ = _resilient(comportement, FakeClock(), attempts=1)
        with (
            caplog.at_level(logging.WARNING, logger="happly.connectors"),
            pytest.raises(UnexpectedConnectorError) as info,
        ):
            await connecteur.search(CRITERES)

        assert isinstance(info.value.__cause__, KeyError)
        enregistrement = caplog.records[0]
        assert enregistrement.source == "src"  # type: ignore[attr-defined]
        assert enregistrement.error_type == "UnexpectedConnectorError"  # type: ignore[attr-defined]
        assert "secret-xyz" not in caplog.text

    async def test_l_annulation_n_est_jamais_avalee(self) -> None:
        async def comportement() -> SearchPage:
            raise asyncio.CancelledError

        connecteur, _ = _resilient(comportement, FakeClock())

        with pytest.raises(asyncio.CancelledError):
            await connecteur.search(CRITERES)

    async def test_une_source_en_echec_n_empeche_pas_les_autres(self) -> None:
        async def en_panne() -> SearchPage:
            raise SourceUnavailableError("500")

        mauvaise, _ = _resilient(en_panne, FakeClock(), attempts=1)
        bonne, _ = _resilient(None, FakeClock())

        resultats = await asyncio.gather(
            mauvaise.search(CRITERES), bonne.search(CRITERES), return_exceptions=True
        )

        assert isinstance(resultats[0], SourceUnavailableError)
        assert isinstance(resultats[1], SearchPage)

    async def test_le_health_check_ne_leve_pas_et_signale_l_indisponibilite(self) -> None:
        _connecteur, inner = _resilient(None, FakeClock())

        async def casse() -> None:
            raise SourceUnavailableError("down")

        inner.health_check = casse  # type: ignore[method-assign,assignment]
        connecteur_ = ResilientConnector(inner, retry=RetryPolicy(max_attempts=1), timeout=1)

        statut = await connecteur_.health_check()

        assert statut.state.value == "unavailable"
        assert statut.detail == "SourceUnavailableError"


class TestDisjoncteur:
    async def test_s_ouvre_apres_le_seuil_puis_ecarte_la_source_sans_appel(self) -> None:
        horloge = FakeClock()

        async def comportement() -> SearchPage:
            raise SourceUnavailableError("500")

        connecteur, inner = _resilient(comportement, horloge, attempts=1)
        for _ in range(3):
            with pytest.raises(SourceUnavailableError):
                await connecteur.search(CRITERES)

        assert connecteur.breaker.state is CircuitState.OPEN
        with pytest.raises(CircuitOpenError):
            await connecteur.search(CRITERES)
        assert inner.calls == 3  # aucun appel réseau supplémentaire

    async def test_se_referme_apres_un_essai_reussi(self) -> None:
        horloge = FakeClock()
        etat = {"panne": True}

        async def comportement() -> SearchPage:
            if etat["panne"]:
                raise SourceUnavailableError("500")
            return PAGE

        connecteur, _ = _resilient(comportement, horloge, attempts=1)
        for _ in range(3):
            with pytest.raises(SourceUnavailableError):
                await connecteur.search(CRITERES)
        horloge.now += 61
        etat["panne"] = False

        assert connecteur.breaker.state is CircuitState.HALF_OPEN
        assert await connecteur.search(CRITERES) == PAGE
        assert connecteur.breaker.state.value == "closed"

    async def test_un_essai_echoue_rouvre_le_disjoncteur(self) -> None:
        horloge = FakeClock()

        async def comportement() -> SearchPage:
            raise SourceUnavailableError("500")

        connecteur, _ = _resilient(comportement, horloge, attempts=1)
        for _ in range(3):
            with pytest.raises(SourceUnavailableError):
                await connecteur.search(CRITERES)
        horloge.now += 61
        with pytest.raises(SourceUnavailableError):
            await connecteur.search(CRITERES)

        assert connecteur.breaker.state is CircuitState.OPEN

    async def test_un_quota_ou_un_refus_n_ouvre_pas_le_disjoncteur(self) -> None:
        async def comportement() -> SearchPage:
            raise AccessDeniedError("403")

        connecteur, _ = _resilient(comportement, FakeClock(), attempts=1)
        for _ in range(10):
            with pytest.raises(AccessDeniedError):
                await connecteur.search(CRITERES)

        assert connecteur.breaker.state is CircuitState.CLOSED

    async def test_un_seul_essai_a_la_fois_en_demi_ouverture(self) -> None:
        horloge = FakeClock()
        disjoncteur = CircuitBreaker(1, 10, clock=horloge)
        disjoncteur.record_failure()
        horloge.now += 11

        assert disjoncteur.allow() is True
        assert disjoncteur.allow() is False

    def test_parametres_invalides_refuses(self) -> None:
        with pytest.raises(ValueError):
            CircuitBreaker(0, 10)
        with pytest.raises(ValueError):
            CircuitBreaker(1, 0)


class TestRateLimiter:
    async def test_espace_les_appels_au_debit_configure(self) -> None:
        horloge = FakeClock()
        limiteur = RateLimiter(2, burst=1, clock=horloge, sleep=horloge.sleep)  # 2 req/s

        for _ in range(3):
            await limiteur.acquire()

        assert horloge.now == pytest.approx(1000.0 + 2 * 0.5)

    async def test_autorise_une_rafale_initiale(self) -> None:
        horloge = FakeClock()
        limiteur = RateLimiter(1, burst=3, clock=horloge, sleep=horloge.sleep)

        for _ in range(3):
            await limiteur.acquire()

        assert horloge.now == 1000.0

    def test_parametres_invalides_refuses(self) -> None:
        with pytest.raises(ValueError):
            RateLimiter(0)
        with pytest.raises(ValueError):
            RateLimiter(1, burst=0)
