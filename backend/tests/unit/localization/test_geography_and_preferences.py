import zoneinfo

import pytest

from app.modules.localization.domain.preferences import (
    InvalidPreferencesError,
    Preferences,
    validate,
)
from app.modules.localization.infrastructure.cldr import BabelGeographyReference

REF = BabelGeographyReference()
FUSEAUX = frozenset(zoneinfo.available_timezones())


class TestReferentiel:
    def test_un_pays_porte_son_nom_ses_langues_officielles_et_sa_devise(self) -> None:
        suisse = REF.country("ch", "fr")

        assert suisse is not None
        assert suisse.code == "CH" and suisse.name == "Suisse"
        assert {"de", "fr", "it"} <= set(suisse.official_languages)
        assert suisse.currencies == ("CHF",)

    def test_le_nom_suit_la_langue_demandee(self) -> None:
        assert REF.country("DE", "fr").name == "Allemagne"  # type: ignore[union-attr]
        assert REF.country("DE", "en").name == "Germany"  # type: ignore[union-attr]

    def test_une_langue_inconnue_retombe_sur_l_anglais(self) -> None:
        assert REF.country("DE", "xx-inconnue").name == "Germany"  # type: ignore[union-attr]

    @pytest.mark.parametrize("code", ["ZZ", "XA", "EU", "UN", "QO", "AA", "FRA", "1", ""])
    def test_les_regroupements_et_codes_reserves_ne_sont_pas_des_pays(self, code: str) -> None:
        assert REF.country(code, "en") is None

    def test_les_langues_d_usage_sont_renseignees_meme_sans_langue_legale(self) -> None:
        # Les États-Unis n'ont pas de langue officielle légale : on ne les déclare pas muets.
        assert REF.country("US", "en").official_languages == ("en",)  # type: ignore[union-attr]

    def test_pays_tries_par_nom_et_sans_doublon(self) -> None:
        pays = REF.countries("fr")
        noms = [c.name.casefold() for c in pays]

        assert noms == sorted(noms)
        assert len({c.code for c in pays}) == len(pays) > 200

    def test_devises_iso_4217(self) -> None:
        assert REF.has_currency("eur") and REF.has_currency("CHF")
        assert not REF.has_currency("EURO") and not REF.has_currency("")
        assert any(d.code == "JPY" for d in REF.currencies("en"))


class TestPreferences:
    def test_normalise_pays_devise_et_retire_les_doublons(self) -> None:
        resultat = validate(
            Preferences(
                ui_language="en",
                country_code="fr",
                currency="chf",
                timezone="Europe/Paris",
                target_countries=("ca", "CA", "de"),
                work_permit_countries=("fr",),
                willing_to_relocate=True,
                needs_sponsorship=False,
            ),
            REF,
            FUSEAUX,
        )

        assert resultat.country_code == "FR" and resultat.currency == "CHF"
        assert resultat.target_countries == ("CA", "DE")
        assert resultat.work_permit_countries == ("FR",)
        assert resultat.needs_sponsorship is False  # « non » n'est pas « non renseigné »

    def test_valeurs_non_renseignees_conservees(self) -> None:
        assert validate(Preferences(), REF, FUSEAUX) == Preferences()

    @pytest.mark.parametrize(
        ("prefs", "message"),
        [
            (Preferences(ui_language="de"), "Langue d'interface"),
            (Preferences(country_code="ZZ"), "Pays inconnu"),
            (Preferences(currency="XXX1"), "Devise inconnue"),
            (Preferences(timezone="Mars/Olympus"), "Fuseau horaire inconnu"),
            (Preferences(target_countries=("FR", "EU")), "Pays inconnu"),
        ],
    )
    def test_refuse_les_valeurs_hors_referentiel(self, prefs: Preferences, message: str) -> None:
        with pytest.raises(InvalidPreferencesError, match=message):
            validate(prefs, REF, FUSEAUX)
