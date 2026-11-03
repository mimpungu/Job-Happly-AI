import os

import pytest


@pytest.fixture(autouse=True)
def _environnement_de_test_isole(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empêche un fichier .env local ou l'environnement de la machine de fausser les tests."""
    for nom in list(os.environ):
        if nom.startswith("HAPPLY_"):
            monkeypatch.delenv(nom)
    monkeypatch.setenv("HAPPLY_ENVIRONMENT", "test")
