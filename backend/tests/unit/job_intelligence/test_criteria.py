from datetime import UTC, datetime, timedelta
from decimal import Decimal
from itertools import pairwise

import pytest

from app.modules.job_intelligence.domain.matching.criteria import (
    evaluate_contract,
    evaluate_education,
    evaluate_experience,
    evaluate_freshness,
    evaluate_location,
    evaluate_remote,
    evaluate_salary,
    evaluate_title,
    experience_months,
)
from app.modules.job_intelligence.domain.matching.models import (
    ExperiencePeriod,
    MatchKind,
    Status,
    YearMonth,
)
from app.modules.job_intelligence.domain.matching.offer_requirements import (
    EducationRequirement,
    YearsRequirement,
)

from .factories import MAINTENANT, offre, profil

P = Decimal(10)


class TestMetier:
    @pytest.mark.parametrize(
        ("titre_offre", "score", "kind"),
        [
            ("Data Analyst H/F", Decimal(1), MatchKind.PRESENT),
            ("Senior Data Analyst", Decimal(1), MatchKind.PRESENT),
            ("Analyste de données", Decimal("0.5"), MatchKind.PARTIAL),
            ("Comptable général", Decimal(0), MatchKind.ABSENT),
        ],
    )
    def test_niveaux_de_correspondance(
        self, titre_offre: str, score: Decimal, kind: MatchKind
    ) -> None:
        r = evaluate_title(profil(titles=("Data Analyst",)), offre(title=titre_offre), P)

        assert r.status is Status.EVALUATED
        assert r.score == score
        assert r.items[0].kind is kind

    def test_equivalences_francais_anglais(self) -> None:
        r = evaluate_title(
            profil(titles=("Développeur Python",)), offre(title="Python Developer"), P
        )

        assert r.score == Decimal(1)

    def test_un_seul_mot_en_commun_ne_fait_pas_un_metier(self) -> None:
        r = evaluate_title(
            profil(titles=("Data Analyst Marketing",)), offre(title="Data Engineer Cloud Senior"), P
        )

        assert r.score is not None and r.score < Decimal("0.5")

    def test_garde_le_meilleur_des_intitules_du_profil(self) -> None:
        r = evaluate_title(profil(titles=("Comptable", "Data Analyst")), offre(), P)

        assert r.score == Decimal(1)
        assert "Data Analyst" in (r.items[0].detail or "")

    def test_profil_sans_intitule_donnees_manquantes(self) -> None:
        r = evaluate_title(profil(titles=()), offre(), P)

        assert (r.status, r.score) == (Status.MISSING_DATA, None)


class TestExperience:
    def test_union_sans_double_compte_des_chevauchements(self) -> None:
        periodes = (
            ExperiencePeriod(YearMonth(2020, 1), YearMonth(2020, 12)),
            ExperiencePeriod(YearMonth(2020, 6), YearMonth(2021, 5)),
        )

        bas, haut, ignorees = experience_months(periodes, MAINTENANT)

        # Janvier 2020 -> mai 2021 : 17 mois (et non 12 + 12 = 24 : le chevauchement compte une fois).
        assert (bas, haut, ignorees) == (17, 17, 0)

    def test_dates_partielles_donnent_une_fourchette_pas_une_valeur_inventee(self) -> None:
        bas, haut, _ = experience_months(
            (ExperiencePeriod(YearMonth(2018), YearMonth(2020)),), MAINTENANT
        )

        assert bas < haut
        # Au plus court : déc. 2018 -> janv. 2020 (14 mois). Au plus long : janv. 2018 -> déc. 2020 (36).
        assert (bas, haut) == (14, 36)

    def test_poste_actuel_court_jusqu_a_maintenant(self) -> None:
        debut_ce_mois = ExperiencePeriod(YearMonth(2026, 11), None, is_current=True)
        depuis_un_an = ExperiencePeriod(YearMonth(2025, 11), None, is_current=True)

        assert experience_months((debut_ce_mois,), MAINTENANT)[:2] == (1, 1)
        # Novembre 2025 -> novembre 2026, mois de début et de fin compris : 13 mois.
        assert experience_months((depuis_un_an,), MAINTENANT)[:2] == (13, 13)

    def test_periodes_inexploitables_ignorees_et_comptees(self) -> None:
        periodes = (
            ExperiencePeriod(None, YearMonth(2020, 1)),
            ExperiencePeriod(YearMonth(2020, 1), None, is_current=False),
            ExperiencePeriod(YearMonth(2024, 1), YearMonth(2024, 12)),
        )

        bas, haut, ignorees = experience_months(periodes, MAINTENANT)

        assert (bas, haut, ignorees) == (12, 12, 2)

    def test_exigence_satisfaite(self) -> None:
        r = evaluate_experience(profil(), YearsRequirement(3, True, "3 ans"), MAINTENANT, P)

        assert (r.status, r.score) == (Status.EVALUATED, Decimal(1))
        assert r.uncertain is False

    def test_exigence_non_satisfaite_score_proportionnel(self) -> None:
        periodes = (ExperiencePeriod(YearMonth(2024, 11), YearMonth(2025, 10)),)

        r = evaluate_experience(
            profil(experience_periods=periodes), YearsRequirement(4, False, "x"), MAINTENANT, P
        )

        assert r.score == Decimal("0.25")
        assert r.items[0].kind is MatchKind.PARTIAL

    def test_dates_partielles_a_la_limite_donnent_un_resultat_incertain(self) -> None:
        # « 2020 – 2022 » en années seules : de 13 à 36 mois ; 2 ans (24) demandés -> indécidable.
        periodes = (ExperiencePeriod(YearMonth(2020), YearMonth(2022)),)

        r = evaluate_experience(
            profil(experience_periods=periodes), YearsRequirement(2, False, "x"), MAINTENANT, P
        )

        assert r.uncertain is True
        assert r.score == Decimal("0.9")
        assert "précisez les mois" in r.explanation

    def test_debutant_accepte_toujours_satisfait_meme_sans_experience(self) -> None:
        r = evaluate_experience(
            profil(experience_periods=()), YearsRequirement(0, False, "x"), MAINTENANT, P
        )

        assert r.score == Decimal(1)

    def test_offre_muette_donnees_manquantes(self) -> None:
        assert evaluate_experience(profil(), None, MAINTENANT, P).status is Status.MISSING_DATA

    def test_profil_sans_experience_donnees_manquantes_pas_zero(self) -> None:
        r = evaluate_experience(
            profil(experience_periods=()), YearsRequirement(3, True, "x"), MAINTENANT, P
        )

        assert (r.status, r.score) == (Status.MISSING_DATA, None)


class TestFormation:
    def test_niveau_atteint(self) -> None:
        r = evaluate_education(
            profil(degrees=("Master Informatique",)), EducationRequirement(3, False, "x"), P
        )

        assert r.score == Decimal(1)

    def test_niveau_insuffisant_proportionnel(self) -> None:
        r = evaluate_education(
            profil(degrees=("Licence Maths",)), EducationRequirement(5, False, "x"), P
        )

        assert r.score == Decimal("0.6")

    def test_prend_le_diplome_le_plus_eleve(self) -> None:
        r = evaluate_education(
            profil(degrees=("BTS Info", "Master Data")), EducationRequirement(5, False, "x"), P
        )

        assert r.score == Decimal(1)

    def test_diplome_de_niveau_non_reconnu_donnees_manquantes(self) -> None:
        r = evaluate_education(
            profil(degrees=("Diplôme de l'ESSEC",)), EducationRequirement(5, False, "x"), P
        )

        assert r.status is Status.MISSING_DATA
        assert "reconnaissable" in r.explanation

    def test_sans_formation_ou_offre_muette(self) -> None:
        assert (
            evaluate_education(profil(degrees=()), EducationRequirement(3, False, "x"), P).status
            is Status.MISSING_DATA
        )
        assert evaluate_education(profil(), None, P).status is Status.MISSING_DATA


class TestLocalisation:
    def test_ville_souhaitee(self) -> None:
        r = evaluate_location(profil(), offre(location="Lyon 3e, France"), P)

        assert r.score == Decimal(1)

    def test_bon_pays_mauvaise_ville(self) -> None:
        r = evaluate_location(profil(), offre(location="Lille, France"), P)

        assert r.score == Decimal("0.4")

    def test_mauvais_pays(self) -> None:
        r = evaluate_location(profil(), offre(location="Bruxelles", country_code="BE"), P)

        assert r.score == Decimal(0)

    def test_pays_seul_sans_ville_souhaitee(self) -> None:
        r = evaluate_location(profil(cities=()), offre(location="Lille", country_code="FR"), P)

        assert r.score == Decimal(1)

    def test_teletravail_complet_neutralise_le_lieu(self) -> None:
        r = evaluate_location(
            profil(), offre(location="Tokyo", country_code="JP", remote_type="remote"), P
        )

        assert r.score == Decimal(1)

    def test_donnees_manquantes(self) -> None:
        assert (
            evaluate_location(profil(cities=(), country_codes=()), offre(), P).status
            is Status.MISSING_DATA
        )
        assert (
            evaluate_location(profil(), offre(location=None, country_code=None), P).status
            is Status.MISSING_DATA
        )


class TestContratEtTeletravail:
    def test_contrat(self) -> None:
        assert evaluate_contract(profil(), offre(), P).score == Decimal(1)
        assert evaluate_contract(profil(), offre(employment_type="fixed_term"), P).score == Decimal(
            0
        )

    def test_contrat_donnees_manquantes(self) -> None:
        assert (
            evaluate_contract(profil(employment_types=()), offre(), P).status is Status.MISSING_DATA
        )
        assert (
            evaluate_contract(profil(), offre(employment_type=None), P).status
            is Status.MISSING_DATA
        )

    @pytest.mark.parametrize(
        ("souhaite", "offre_remote", "score"),
        [
            (("hybrid", "remote"), "hybrid", Decimal(1)),
            (("remote",), "hybrid", Decimal("0.5")),
            (("on_site",), "hybrid", Decimal("0.5")),
            (("remote",), "on_site", Decimal(0)),
            (("on_site",), "remote", Decimal(0)),
        ],
    )
    def test_teletravail(
        self, souhaite: tuple[str, ...], offre_remote: str, score: Decimal
    ) -> None:
        assert (
            evaluate_remote(profil(remote_types=souhaite), offre(remote_type=offre_remote), P).score
            == score
        )

    def test_teletravail_donnees_manquantes(self) -> None:
        assert evaluate_remote(profil(remote_types=()), offre(), P).status is Status.MISSING_DATA
        assert evaluate_remote(profil(), offre(remote_type=None), P).status is Status.MISSING_DATA


class TestSalaire:
    def test_atteint(self) -> None:
        assert evaluate_salary(profil(), offre(), P).score == Decimal(1)

    def test_en_dessous_proportionnel(self) -> None:
        r = evaluate_salary(
            profil(salary_min=Decimal(60000)), offre(salary_min=None, salary_max=Decimal(45000)), P
        )

        assert r.score == Decimal("0.75")

    def test_seule_la_borne_basse_est_connue_resultat_incertain(self) -> None:
        r = evaluate_salary(
            profil(salary_min=Decimal(60000)), offre(salary_min=Decimal(40000), salary_max=None), P
        )

        assert r.uncertain is True
        assert "bas de la fourchette" in r.explanation

    def test_devises_differentes_aucune_conversion(self) -> None:
        r = evaluate_salary(profil(), offre(salary_currency="USD"), P)

        assert (r.status, r.score) == (Status.MISSING_DATA, None)
        assert "aucune conversion" in r.explanation

    def test_donnees_manquantes(self) -> None:
        assert evaluate_salary(profil(salary_min=None), offre(), P).status is Status.MISSING_DATA
        assert (
            evaluate_salary(
                profil(), offre(salary_min=None, salary_max=None, salary_currency=None), P
            ).status
            is Status.MISSING_DATA
        )


class TestAnciennete:
    @pytest.mark.parametrize(
        ("jours", "attendu"),
        [(0, Decimal(1)), (7, Decimal(1)), (400, Decimal(0)), (120, Decimal("0.1"))],
    )
    def test_paliers(self, jours: int, attendu: Decimal) -> None:
        r = evaluate_freshness(
            offre(published_at=MAINTENANT - timedelta(days=jours)), MAINTENANT, P
        )

        assert r.score == attendu

    def test_decroissante_et_continue(self) -> None:
        scores = [
            evaluate_freshness(
                offre(published_at=MAINTENANT - timedelta(days=j)), MAINTENANT, P
            ).score
            for j in (7, 15, 30, 60, 90, 91)
        ]

        assert all(a is not None and b is not None and a >= b for a, b in pairwise(scores))

    def test_date_dans_le_futur_traitee_comme_recente(self) -> None:
        r = evaluate_freshness(offre(published_at=datetime(2030, 1, 1, tzinfo=UTC)), MAINTENANT, P)

        assert r.score == Decimal(1)

    def test_date_inconnue_donnees_manquantes(self) -> None:
        assert (
            evaluate_freshness(offre(published_at=None), MAINTENANT, P).status
            is Status.MISSING_DATA
        )
