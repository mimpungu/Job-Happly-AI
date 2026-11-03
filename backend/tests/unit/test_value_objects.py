from datetime import date
from decimal import Decimal

import pytest

from app.core.domain.value_objects import (
    CountryCode,
    DateRange,
    DomainValueError,
    LanguageCode,
    Money,
)


class TestCountryCode:
    def test_normalise_en_majuscules(self) -> None:
        assert CountryCode(" fr ").value == "FR"

    @pytest.mark.parametrize("valeur", ["", "F", "FRA", "F1", "  "])
    def test_rejette_les_codes_invalides(self, valeur: str) -> None:
        with pytest.raises(DomainValueError):
            CountryCode(valeur)

    def test_accepte_n_importe_quel_pays_valide(self) -> None:
        assert CountryCode("jp").value == "JP"


class TestLanguageCode:
    @pytest.mark.parametrize(
        ("saisie", "attendu"), [("FR", "fr"), ("pt-br", "pt-BR"), ("EN-us", "en-US")]
    )
    def test_normalise(self, saisie: str, attendu: str) -> None:
        assert LanguageCode(saisie).value == attendu

    @pytest.mark.parametrize("valeur", ["", "f", "french", "fr_FR", "fr-"])
    def test_rejette_les_codes_invalides(self, valeur: str) -> None:
        with pytest.raises(DomainValueError):
            LanguageCode(valeur)


class TestMoney:
    def test_normalise_la_devise(self) -> None:
        assert Money(Decimal("10.50"), "eur").currency == "EUR"

    def test_refuse_un_flottant(self) -> None:
        with pytest.raises(DomainValueError):
            Money(10.5, "EUR")  # type: ignore[arg-type]

    @pytest.mark.parametrize("montant", [Decimal("-1"), Decimal("NaN"), Decimal("Infinity")])
    def test_refuse_les_montants_invalides(self, montant: Decimal) -> None:
        with pytest.raises(DomainValueError):
            Money(montant, "EUR")

    def test_additionne_dans_la_meme_devise(self) -> None:
        assert Money(Decimal("1"), "EUR") + Money(Decimal("2"), "EUR") == Money(Decimal("3"), "EUR")

    def test_refuse_d_additionner_des_devises_differentes(self) -> None:
        with pytest.raises(DomainValueError):
            Money(Decimal("1"), "EUR") + Money(Decimal("1"), "USD")

    def test_zero_est_une_valeur_valide_distincte_de_l_absence(self) -> None:
        assert Money(Decimal("0"), "EUR").amount == 0


class TestDateRange:
    def test_periode_en_cours(self) -> None:
        periode = DateRange(date(2024, 1, 1))

        assert periode.is_ongoing
        assert periode.contains(date(2030, 1, 1))

    def test_refuse_une_fin_avant_le_debut(self) -> None:
        with pytest.raises(DomainValueError):
            DateRange(date(2024, 5, 1), date(2024, 4, 30))

    def test_bornes_incluses(self) -> None:
        periode = DateRange(date(2024, 1, 1), date(2024, 1, 31))

        assert periode.contains(date(2024, 1, 1))
        assert periode.contains(date(2024, 1, 31))
        assert not periode.contains(date(2024, 2, 1))
