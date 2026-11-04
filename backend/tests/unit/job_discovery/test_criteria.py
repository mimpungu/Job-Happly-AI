from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.modules.job_discovery.domain.criteria import SearchCriteria


def test_critere_minimal_valide() -> None:
    criteres = SearchCriteria(title="  Data Analyst ")

    assert criteres.title == "Data Analyst"
    assert criteres.page_size == 50


def test_normalise_pays_langue_devise_et_dedoublonne() -> None:
    criteres = SearchCriteria(
        keywords=("sql", "sql", " python "),
        country_codes=("fr", "FR", "de"),
        language="PT-br",
        salary_min=Decimal("40000"),
        salary_currency="eur",
    )

    assert criteres.country_codes == ("FR", "DE")
    assert criteres.language == "pt-BR"
    assert criteres.salary_currency == "EUR"
    assert criteres.keywords == ("sql", "python")


@pytest.mark.parametrize(
    "champs",
    [
        {},  # rien à chercher
        {"title": "   "},
        {"title": "x", "country_codes": ("FRA",)},
        {"title": "x", "language": "klingon"},
        {"title": "x", "salary_min": Decimal("10")},  # salaire sans devise
        {
            "title": "x",
            "salary_min": Decimal("10"),
            "salary_max": Decimal("5"),
            "salary_currency": "EUR",
        },
        {"title": "x", "radius_km": 20},  # rayon sans ville
        {"title": "x", "page_size": 0},
        {"title": "x", "page_size": 101},
        {"title": "x", "inconnu": 1},
    ],
)
def test_refuse_les_criteres_incoherents(champs: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        SearchCriteria(**champs)


def test_est_immuable_et_serialisable_pour_etre_sauvegarde() -> None:
    criteres = SearchCriteria(title="Data", country_codes=("FR",))

    with pytest.raises(ValidationError):
        criteres.title = "Autre"  # type: ignore[misc]
    assert SearchCriteria.model_validate(criteres.model_dump(mode="json")) == criteres


def test_une_recherche_vide_est_refusee_sauf_pour_enumerer_un_catalogue() -> None:
    with pytest.raises(ValidationError, match="au moins un intitulé"):
        SearchCriteria()

    catalogue = SearchCriteria(whole_catalogue=True)

    assert catalogue.title is None
    assert catalogue.whole_catalogue is True
