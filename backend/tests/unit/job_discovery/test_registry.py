import pytest

from app.modules.job_discovery.application.registry import (
    ConnectorRegistry,
    DuplicateSourceError,
    UnknownSourceError,
)
from app.modules.job_discovery.domain.connector import (
    ConnectorCapabilities,
    HealthState,
    HealthStatus,
    JobSourceConnector,
)
from app.modules.job_discovery.domain.criteria import SearchCriteria

from .fakes import FakeConnector


def test_un_connecteur_de_test_respecte_le_contrat() -> None:
    assert isinstance(FakeConnector(), JobSourceConnector)


def test_aucune_source_n_est_active_par_defaut() -> None:
    registre = ConnectorRegistry()
    registre.register(FakeConnector("a"))

    assert registre.enabled() == ()
    assert registre.is_enabled("a") is False


def test_active_et_desactive_une_source() -> None:
    registre = ConnectorRegistry()
    registre.register(FakeConnector("a"))
    registre.register(FakeConnector("b"))

    registre.enable("a")
    assert [c.key for c in registre.enabled()] == ["a"]
    registre.disable("a")
    assert registre.enabled() == ()


def test_refuse_une_cle_en_double_et_une_source_inconnue() -> None:
    registre = ConnectorRegistry()
    registre.register(FakeConnector("a"))

    with pytest.raises(DuplicateSourceError):
        registre.register(FakeConnector("a"))
    with pytest.raises(UnknownSourceError):
        registre.enable("absente")
    with pytest.raises(UnknownSourceError):
        registre.get("absente")


def test_ne_retient_que_les_sources_actives_couvrant_les_pays_demandes() -> None:
    registre = ConnectorRegistry()
    registre.register(
        FakeConnector("fr", capabilities=ConnectorCapabilities(countries=frozenset({"FR"}))),
        enabled=True,
    )
    registre.register(
        FakeConnector("ca", capabilities=ConnectorCapabilities(countries=frozenset({"CA"}))),
        enabled=True,
    )
    registre.register(FakeConnector("monde"), enabled=True)  # sans restriction
    registre.register(
        FakeConnector(
            "fr-inactive", capabilities=ConnectorCapabilities(countries=frozenset({"FR"}))
        )
    )

    en_france = registre.compatible_with(SearchCriteria(title="x", country_codes=("FR",)))
    sans_pays = registre.compatible_with(SearchCriteria(title="x"))

    assert sorted(c.key for c in en_france) == ["fr", "monde"]
    assert sorted(c.key for c in sans_pays) == ["ca", "fr", "monde"]


def test_conserve_l_etat_de_sante() -> None:
    from datetime import UTC, datetime

    registre = ConnectorRegistry()
    registre.register(FakeConnector("a"))
    assert registre.health("a") is None  # jamais vérifié ≠ en bonne santé

    statut = HealthStatus(HealthState.DEGRADED, datetime.now(UTC), "lent")
    registre.record_health("a", statut)

    assert registre.health("a") == statut
