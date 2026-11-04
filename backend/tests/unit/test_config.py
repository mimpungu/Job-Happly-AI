import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_hote_par_defaut_est_la_boucle_locale() -> None:
    assert Settings().host == "127.0.0.1"


def test_port_invalide_est_rejete(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HAPPLY_PORT", "70000")

    with pytest.raises(ValidationError):
        Settings()


def test_cors_generique_est_rejete(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HAPPLY_CORS_ALLOWED_ORIGINS", '["*"]')

    with pytest.raises(ValidationError):
        Settings()


def test_production_exige_une_url_de_base(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HAPPLY_ENVIRONMENT", "production")

    with pytest.raises(ValidationError):
        Settings()


def test_production_refuse_le_mot_de_passe_d_exemple(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HAPPLY_ENVIRONMENT", "production")
    monkeypatch.setenv("HAPPLY_DATABASE_URL", "postgresql://happly:change-me@127.0.0.1/happly")

    with pytest.raises(ValidationError):
        Settings()


def test_le_secret_n_apparait_pas_dans_la_representation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HAPPLY_DATABASE_URL", "postgresql://happly:secret-xyz@127.0.0.1/happly")

    assert "secret-xyz" not in repr(Settings())
