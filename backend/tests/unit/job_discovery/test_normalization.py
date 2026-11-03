from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.core.domain.value_objects import CountryCode, EmploymentType
from app.modules.job_discovery.domain.normalization import (
    annual_amount,
    clean_title,
    parse_amount,
    parse_country,
    parse_currency,
    parse_employment_type,
    parse_location,
    parse_period,
    title_key,
    to_utc,
)


class TestTitres:
    @pytest.mark.parametrize(
        ("brut", "attendu"),
        [
            ("Data Analyst (H/F)", "Data Analyst"),
            ("Data  Analyst   H/F", "Data Analyst"),
            ("Développeur (F/H) ", "Développeur"),
            ("Software Engineer (m/f/d)", "Software Engineer"),
            ("Data Analyst - [H/F]", "Data Analyst"),
            ("Chef de projet", "Chef de projet"),
            ("Analyste H/F confirmé", "Analyste H/F confirmé"),  # marqueur au milieu : conservé
        ],
    )
    def test_nettoie_l_intitule(self, brut: str, attendu: str) -> None:
        assert clean_title(brut) == attendu

    def test_la_cle_ignore_accents_casse_et_marqueur_de_genre(self) -> None:
        assert title_key("Développeur Données (H/F)") == title_key("developpeur donnees")


class TestLieux:
    def test_ville_region_pays(self) -> None:
        lieu = parse_location("Paris, Île-de-France, France")

        assert (lieu.city, lieu.region, lieu.country_code) == (
            "Paris",
            "Île-de-France",
            CountryCode("FR"),
        )
        assert lieu.key == "paris"
        assert lieu.remote_hint is False

    def test_ville_et_code_pays(self) -> None:
        lieu = parse_location("Montréal, CA")

        assert lieu.city == "Montréal"
        assert lieu.country_code == CountryCode("CA")

    def test_ville_seule_sans_pays_devine(self) -> None:
        lieu = parse_location("Lyon")

        assert lieu.city == "Lyon"
        assert lieu.country_code is None  # on ne déduit pas le pays d'un nom de ville

    def test_pays_seul(self) -> None:
        lieu = parse_location("Germany")

        assert lieu.city is None
        assert lieu.country_code == CountryCode("DE")
        assert lieu.key is None

    def test_teletravail_detecte_comme_indice(self) -> None:
        lieu = parse_location("Remote, France")

        assert lieu.remote_hint is True
        assert lieu.city is None
        assert lieu.country_code == CountryCode("FR")

    @pytest.mark.parametrize("texte", [None, "", "   "])
    def test_lieu_absent(self, texte: str | None) -> None:
        lieu = parse_location(texte)

        assert (lieu.city, lieu.region, lieu.country_code, lieu.remote_hint) == (
            None,
            None,
            None,
            False,
        )

    @pytest.mark.parametrize(
        ("texte", "attendu"),
        [("fr", "FR"), ("Royaume-Uni", "GB"), ("États-Unis", "US"), ("Japon", "JP")],
    )
    def test_pays(self, texte: str, attendu: str) -> None:
        assert parse_country(texte) == CountryCode(attendu)

    @pytest.mark.parametrize("texte", ["Atlantide", "", None, "12"])
    def test_pays_inconnu(self, texte: str | None) -> None:
        assert parse_country(texte) is None


class TestContrats:
    @pytest.mark.parametrize(
        ("texte", "attendu"),
        [
            ("CDI", EmploymentType.PERMANENT),
            ("cdd", EmploymentType.FIXED_TERM),
            ("Stage", EmploymentType.INTERNSHIP),
            ("Alternance", EmploymentType.APPRENTICESHIP),
            ("Intérim", EmploymentType.TEMPORARY),
            ("Freelance", EmploymentType.FREELANCE),
            ("Temps partiel", EmploymentType.PART_TIME),
            ("Part-time", EmploymentType.PART_TIME),
        ],
    )
    def test_reconnait_les_libelles_clairs(self, texte: str, attendu: EmploymentType) -> None:
        assert parse_employment_type(texte) is attendu

    @pytest.mark.parametrize(
        "texte", ["Full-time", "Contract", "Temps plein", "n'importe quoi", "", None]
    )
    def test_libelle_ambigu_ou_inconnu_donne_none(self, texte: str | None) -> None:
        assert parse_employment_type(texte) is None


class TestDevisesEtSalaires:
    @pytest.mark.parametrize(
        ("texte", "attendu"),
        [
            ("eur", "EUR"),
            ("€", "EUR"),
            ("Euros", "EUR"),
            ("£", "GBP"),
            ("cad", "CAD"),
            ("SEK", "SEK"),
        ],
    )
    def test_devise(self, texte: str, attendu: str) -> None:
        assert parse_currency(texte) == attendu

    @pytest.mark.parametrize("texte", ["$", "", None, "pesos", "12"])
    def test_symbole_ambigu_ou_inconnu_donne_none(self, texte: str | None) -> None:
        assert parse_currency(texte) is None

    @pytest.mark.parametrize(
        ("texte", "attendu"),
        [
            ("45000", "45000"),
            ("45 000", "45000"),
            ("45\u202f000", "45000"),
            ("45k", "45000"),
            ("45.5k", "45500"),
            ("45.000", "45000"),
            ("45,000", "45000"),
            ("45.000,50", "45000.50"),
            ("45,000.50", "45000.50"),
            ("1234,5", "1234.5"),
            ("0", "0"),
        ],
    )
    def test_montant(self, texte: str, attendu: str) -> None:
        assert parse_amount(texte) == Decimal(attendu)

    @pytest.mark.parametrize("texte", ["", "abc", "-5", "k", "1e5", "12 EUR"])
    def test_montant_invalide(self, texte: str) -> None:
        assert parse_amount(texte) is None

    @pytest.mark.parametrize(
        ("texte", "attendu"),
        [
            ("par an", "year"),
            ("Annuel", "year"),
            ("par mois", "month"),
            ("hourly", "hour"),
            ("jour", None),
        ],
    )
    def test_periode(self, texte: str, attendu: str | None) -> None:
        assert parse_period(texte) == attendu

    def test_montant_annuel(self) -> None:
        assert annual_amount(Decimal("50000"), "year") == Decimal("50000")
        assert annual_amount(Decimal("3000"), "month") == Decimal("36000")
        assert annual_amount(Decimal("20"), "hour") is None
        assert annual_amount(Decimal("20"), None) is None


class TestDates:
    def test_convertit_en_utc(self) -> None:
        date = datetime.fromisoformat("2026-10-30T09:00:00-04:00")

        assert to_utc(date) == datetime(2026, 10, 30, 13, 0, tzinfo=UTC)

    def test_une_date_sans_fuseau_n_est_pas_devinee(self) -> None:
        assert to_utc(datetime(2026, 10, 30, 9, 0)) is None

    def test_utilise_le_fuseau_documente_de_la_source(self) -> None:
        resultat = to_utc(datetime(2026, 7, 1, 12, 0), assume_timezone="Europe/Paris")

        assert resultat == datetime(2026, 7, 1, 10, 0, tzinfo=UTC)  # heure d'été : UTC+2

    def test_fuseau_invalide(self) -> None:
        assert to_utc(datetime(2026, 7, 1, 12, 0), assume_timezone="Mars/Olympus") is None
