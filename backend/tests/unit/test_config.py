import pytest

from app.core.config import Settings


def test_hote_par_defaut_est_la_boucle_locale() -> None:
    assert Settings().host == "127.0.0.1"


def test_port_invalide_est_rejete(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HAPPLY_PORT", "70000")

    with pytest.raises(ValueError):
        Settings()
