import pytest

from app.modules.ai_management.application.benchmark import (
    Run,
    estimated_cost,
    grounded_ratio,
    jaccard,
    summarize,
)

OFFRE = (
    "Nous cherchons un développeur Python maîtrisant FastAPI, PostgreSQL et Docker (C++ apprécié)."
)


def test_detecte_les_competences_inventees() -> None:
    assert grounded_ratio(["Python", "FastAPI", "Kubernetes", "Rust"], OFFRE) == 0.5
    assert grounded_ratio(["python", "postgresql", "DOCKER"], OFFRE) == 1.0
    assert grounded_ratio([], OFFRE) is None


def test_accents_casse_et_symboles_ne_trompent_pas_la_comparaison() -> None:
    assert grounded_ratio(["développeur"], OFFRE) == 1.0
    assert grounded_ratio(["C++"], OFFRE) == 1.0
    assert grounded_ratio(["C"], OFFRE) == 0.0  # « C » n'est pas « C++ »


def test_un_mot_n_est_pas_trouve_a_l_interieur_d_un_autre() -> None:
    assert grounded_ratio(["Java"], "Expert JavaScript demandé") == 0.0


def test_recouvrement_de_deux_listes() -> None:
    assert jaccard(["Python", "SQL"], ["python", "sql"]) == 1.0
    assert jaccard(["Python", "SQL"], ["Python", "Docker"]) == pytest.approx(1 / 3)
    assert jaccard([], []) == 1.0
    assert jaccard(["a"], []) == 0.0


def test_resume_un_lot_de_resultats() -> None:
    runs = [
        Run(True, 2.0, 100, 50, ["Python", "SQL"], 1.0),
        Run(True, 4.0, 100, 50, ["Python"], 0.5),
        Run(False, 10.0, 100, 0, error="JSON invalide"),
    ]

    s = summarize(runs)

    assert s.runs == 3 and s.valid_rate == pytest.approx(2 / 3)
    assert s.median_seconds == 4.0 and s.p90_seconds == 10.0
    assert s.mean_grounded == 0.75 and s.mean_skills == 1.5
    assert (s.input_tokens, s.output_tokens) == (300, 100)


def test_cout_hypothetique_au_tarif_paye() -> None:
    s = summarize([Run(True, 1.0, 1_000_000, 500_000, ["a"], 1.0)])

    assert estimated_cost(s, 0.25, 1.50) == pytest.approx(1.0)


def test_refuse_un_resume_vide() -> None:
    with pytest.raises(ValueError):
        summarize([])
