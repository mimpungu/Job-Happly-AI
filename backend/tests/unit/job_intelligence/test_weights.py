from decimal import Decimal

import pytest

from app.modules.job_intelligence.domain.matching.models import Criterion, Weights
from app.modules.job_intelligence.domain.matching.weights import (
    ALGORITHM_VERSION,
    DEFAULT_WEIGHTS,
    InvalidWeightsError,
    validate_weights,
    weights_version,
)


def test_les_poids_par_defaut_couvrent_tous_les_criteres_et_totalisent_100() -> None:
    assert set(DEFAULT_WEIGHTS.values) == set(Criterion)
    assert DEFAULT_WEIGHTS.total() == Decimal(100)


def test_un_critere_non_precise_garde_son_poids_par_defaut() -> None:
    poids = validate_weights({"skills": 40})

    assert poids.get(Criterion.SKILLS) == Decimal(40)
    assert poids.get(Criterion.JOB_TITLE) == DEFAULT_WEIGHTS.get(Criterion.JOB_TITLE)


def test_un_poids_a_zero_desactive_le_critere() -> None:
    assert validate_weights({"salary": 0}).get(Criterion.SALARY) == Decimal(0)


@pytest.mark.parametrize(
    ("brutes", "message"),
    [
        ({"inconnu": 5}, "inconnu"),
        ({"skills": -1}, "entre 0 et 100"),
        ({"skills": 101}, "entre 0 et 100"),
        ({"skills": "beaucoup"}, "invalide"),
        ({"skills": True}, "invalide"),
        ({"skills": None}, "invalide"),
        ({"skills": float("nan")}, "entre 0 et 100"),
        ({"skills": float("inf")}, "entre 0 et 100"),
    ],
)
def test_poids_invalides_refuses(brutes: dict[str, object], message: str) -> None:
    with pytest.raises(InvalidWeightsError, match=message):
        validate_weights(brutes)


def test_au_moins_un_critere_doit_rester_actif() -> None:
    with pytest.raises(InvalidWeightsError, match="Au moins un critère"):
        validate_weights({c.value: 0 for c in Criterion})


def test_version_stable_independante_de_l_ordre_et_de_la_forme() -> None:
    a = Weights({c: DEFAULT_WEIGHTS.get(c) for c in reversed(list(Criterion))})
    b = validate_weights({"skills": "25.0"})

    assert weights_version(a) == weights_version(DEFAULT_WEIGHTS) == weights_version(b)
    assert weights_version(DEFAULT_WEIGHTS).startswith(f"{ALGORITHM_VERSION}-")


def test_la_version_change_des_que_un_poids_change() -> None:
    assert weights_version(validate_weights({"skills": 26})) != weights_version(DEFAULT_WEIGHTS)
