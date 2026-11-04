import pytest

from app.modules.candidate_profile.domain.extraction.dates import PartialDate, find_date_range


@pytest.mark.parametrize(
    ("ligne", "debut", "fin", "en_cours"),
    [
        ("2020 – 2023", (2020, None), (2023, None), False),
        ("janvier 2020 - mars 2023", (2020, 1), (2023, 3), False),
        ("01/2020 - 03/2023", (2020, 1), (2023, 3), False),
        ("Jan 2020 - Present", (2020, 1), None, True),
        ("2021 – Aujourd'hui", (2021, None), None, True),
        ("Depuis septembre 2021", (2021, 9), None, True),
        ("Févr. 2018 à Déc. 2019", (2018, 2), (2019, 12), False),
        ("août 2019 - 2020", (2019, 8), (2020, None), False),
        ("2019", (2019, None), None, False),
    ],
)
def test_formats_de_dates(
    ligne: str,
    debut: tuple[int, int | None],
    fin: tuple[int, int | None] | None,
    en_cours: bool,
) -> None:
    plage = find_date_range(ligne)

    assert plage is not None
    assert plage.start == PartialDate(*debut)
    assert plage.end == (PartialDate(*fin) if fin else None)
    assert plage.is_current is en_cours


def test_une_date_partielle_n_est_jamais_completee() -> None:
    plage = find_date_range("2020 – 2023")

    assert plage is not None
    assert plage.start is not None
    assert plage.start.month is None
    assert plage.start.as_date() is None  # pas de « 1er janvier » inventé
    assert PartialDate(2020, 5).as_date() is not None


@pytest.mark.parametrize(
    "ligne",
    [
        "2023 - 2020",
        "Tel 06 12 34 56 78",
        "version 2.0.2020",
        "Python 3.12",
        "",
        "Bac+5",
        "1234 - 5678",
    ],
)
def test_ne_reconnait_pas_ce_qui_n_est_pas_une_periode(ligne: str) -> None:
    assert find_date_range(ligne) is None


def test_position_du_texte_reconnu() -> None:
    ligne = "Data Analyst – Acme – 2020 – 2023"
    plage = find_date_range(ligne)

    assert plage is not None
    assert ligne[plage.span[0] : plage.span[1]] == "2020 – 2023"


def test_annee_improbable_refusee() -> None:
    with pytest.raises(ValueError, match="improbable"):
        PartialDate(1800)


@pytest.mark.parametrize("prefixe", ["De ", "du "])
def test_le_mot_qui_introduit_la_periode_fait_partie_du_texte_reconnu(prefixe: str) -> None:
    # « De mai 2025 à août 2025 Inetum » : sans cela, « De » resterait collé à l'entreprise.
    ligne = f"{prefixe}mai 2025 à août 2025 Inetum Pessac"
    plage = find_date_range(ligne)

    assert plage is not None
    assert ligne[plage.span[1] :].strip() == "Inetum Pessac"
    assert ligne[: plage.span[0]] == ""


@pytest.mark.parametrize(
    ("ligne", "debut", "fin"),
    [
        ("From 2020 to 2023", (2020, None), (2023, None)),
        ("From Jan 2020 to Mar 2023", (2020, 1), (2023, 3)),
    ],
)
def test_une_periode_anglaise_from_to_n_est_pas_prise_pour_un_poste_en_cours(
    ligne: str, debut: tuple[int, int | None], fin: tuple[int, int | None]
) -> None:
    plage = find_date_range(ligne)

    assert plage is not None
    assert plage.is_current is False
    assert (plage.start, plage.end) == (PartialDate(*debut), PartialDate(*fin))
    assert ligne[plage.span[0] : plage.span[1]] == ligne  # « From » fait partie de la période


def test_since_reste_une_periode_en_cours() -> None:
    plage = find_date_range("Since 2020")

    assert plage is not None
    assert plage.is_current is True
