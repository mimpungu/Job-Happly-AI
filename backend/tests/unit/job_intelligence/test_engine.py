from datetime import timedelta
from decimal import Decimal

import pytest

from app.modules.job_intelligence.domain.matching.engine import compute_match
from app.modules.job_intelligence.domain.matching.models import (
    Criterion,
    CriterionResult,
    MatchKind,
    MatchResult,
    ProfileFacts,
    Reliability,
    Status,
)
from app.modules.job_intelligence.domain.matching.weights import (
    DEFAULT_WEIGHTS,
    validate_weights,
    weights_version,
)

from .factories import MAINTENANT, offre, profil
from .offers import OFFRE_EN, OFFRE_FR, OFFRE_SANS_STRUCTURE


def _par_critere(resultat: MatchResult) -> dict[Criterion, CriterionResult]:
    return {c.criterion: c for c in resultat.criteria}


class TestScoreGlobal:
    def test_profil_et_offre_bien_alignes(self) -> None:
        r = compute_match(profil(), offre(description=OFFRE_FR), MAINTENANT)

        assert r.score is not None and Decimal(70) <= r.score <= Decimal(100)
        assert r.reliability is Reliability.HIGH
        assert r.coverage == Decimal(1)
        c = _par_critere(r)
        assert c[Criterion.JOB_TITLE].score == Decimal(1)
        assert c[Criterion.EXPERIENCE].score == Decimal(1)
        assert c[Criterion.EDUCATION].score == Decimal(1)
        assert c[Criterion.LOCATION].score == Decimal(1)
        assert c[Criterion.MANDATORY].status is Status.EVALUATED

    def test_profil_et_offre_sans_rapport_donnent_un_score_bas(self) -> None:
        mauvais = profil(
            titles=("Cuisinier",),
            skills=("Pâtisserie",),
            degrees=("CAP Cuisine",),
            country_codes=("BE",),
            cities=("Liège",),
            remote_types=("on_site",),
            employment_types=("fixed_term",),
        )

        r = compute_match(mauvais, offre(description=OFFRE_FR), MAINTENANT)

        assert r.score is not None and r.score < Decimal(35)

    def test_le_score_est_toujours_entre_0_et_100(self) -> None:
        profils = [
            profil(),
            profil(titles=(), skills=(), experience_periods=(), degrees=()),
            ProfileFacts(),
            profil(salary_min=Decimal(1_000_000)),
        ]
        offres = [offre(description=d) for d in ("", OFFRE_FR, OFFRE_EN, OFFRE_SANS_STRUCTURE)]
        for p in profils:
            for o in offres:
                r = compute_match(p, o, MAINTENANT)
                if r.score is not None:
                    assert Decimal(0) <= r.score <= Decimal(100)
                assert Decimal(0) <= r.coverage <= Decimal(1)

    def test_le_message_precise_que_ce_n_est_pas_une_prediction(self) -> None:
        r = compute_match(profil(), offre(description=OFFRE_FR), MAINTENANT)

        assert "pas une probabilité" in r.disclaimer


class TestDonneesManquantes:
    def test_un_critere_sans_donnees_n_est_pas_compte_comme_un_echec(self) -> None:
        complet = compute_match(profil(), offre(description=OFFRE_FR), MAINTENANT)
        # Aucune préférence de contrat/télétravail/salaire/lieu : ces critères sortent du calcul.
        sans_preferences = profil(
            cities=(),
            country_codes=(),
            remote_types=(),
            employment_types=(),
            salary_min=None,
            salary_currency=None,
        )

        r = compute_match(sans_preferences, offre(description=OFFRE_FR), MAINTENANT)

        c = _par_critere(r)
        for critere in (Criterion.LOCATION, Criterion.CONTRACT, Criterion.REMOTE, Criterion.SALARY):
            assert c[critere].status is Status.MISSING_DATA
            assert c[critere].score is None
        assert r.score is not None and complet.score is not None
        assert r.score >= complet.score - Decimal(5)  # pas de pénalité pour les données absentes
        assert r.coverage < complet.coverage

    def test_la_couverture_mesure_la_part_du_poids_evaluee(self) -> None:
        # Offre muette sur tout sauf le titre : peu de critères évaluables.
        r = compute_match(
            profil(),
            offre(
                description="",
                location=None,
                country_code=None,
                employment_type=None,
                remote_type=None,
                salary_min=None,
                salary_max=None,
                salary_currency=None,
                published_at=None,
            ),
            MAINTENANT,
        )

        assert r.coverage == Decimal("0.20")  # seul le métier (20 / 100) est évalué
        assert r.reliability is Reliability.LOW
        assert r.score == Decimal("100.00")  # le métier correspond ; la faible fiabilité le dit
        assert "Données manquantes" in r.summary

    def test_le_poids_des_criteres_manquants_est_redistribue(self) -> None:
        o = offre(
            description="",
            location=None,
            country_code=None,
            employment_type=None,
            remote_type=None,
            salary_min=None,
            salary_max=None,
            salary_currency=None,
            published_at=None,
        )
        # Seul le métier est évaluable : le score est celui du métier, quel que soit son poids.
        for poids_metier in (10, 20, 80):
            poids = validate_weights({"job_title": poids_metier})
            r = compute_match(profil(titles=("Data Analyst",)), o, MAINTENANT, poids)
            assert r.score == Decimal("100.00")

    def test_rien_n_est_evaluable(self) -> None:
        r = compute_match(
            ProfileFacts(),
            offre(
                description="",
                location=None,
                country_code=None,
                employment_type=None,
                remote_type=None,
                salary_min=None,
                salary_max=None,
                salary_currency=None,
                published_at=None,
            ),
            MAINTENANT,
        )

        assert r.score is None
        assert r.coverage == Decimal(0)
        assert r.reliability is Reliability.LOW
        assert "non calculable" in r.summary

    def test_offre_non_structuree(self) -> None:
        r = compute_match(
            profil(), offre(title="Comptable", description=OFFRE_SANS_STRUCTURE), MAINTENANT
        )

        c = _par_critere(r)
        assert c[Criterion.SKILLS].status is Status.MISSING_DATA
        assert c[Criterion.EXPERIENCE].status is Status.MISSING_DATA
        assert c[Criterion.EDUCATION].status is Status.MISSING_DATA
        assert c[Criterion.MANDATORY].status is Status.MISSING_DATA


class TestPonderations:
    def test_un_poids_a_zero_retire_le_critere_du_resultat_et_du_calcul(self) -> None:
        poids = validate_weights({"freshness": 0})

        r = compute_match(profil(), offre(description=OFFRE_FR), MAINTENANT, poids)

        assert Criterion.FRESHNESS not in _par_critere(r)

    def test_augmenter_un_poids_rapproche_le_score_de_ce_critere(self) -> None:
        o = offre(
            description=OFFRE_FR, salary_min=Decimal(20000), salary_max=Decimal(25000)
        )  # sous le souhait
        p = profil()

        normal = compute_match(p, o, MAINTENANT)
        salaire_dominant = compute_match(p, o, MAINTENANT, validate_weights({"salary": 100}))

        assert normal.score is not None and salaire_dominant.score is not None
        assert salaire_dominant.score < normal.score  # le salaire (mauvais) pèse davantage

    def test_la_version_des_poids_accompagne_le_resultat(self) -> None:
        poids = validate_weights({"skills": 50})

        r = compute_match(profil(), offre(description=OFFRE_FR), MAINTENANT, poids)

        assert r.weights_version == weights_version(poids) != weights_version(DEFAULT_WEIGHTS)


class TestReproductibilite:
    def test_memes_entrees_meme_resultat(self) -> None:
        a = compute_match(profil(), offre(description=OFFRE_FR), MAINTENANT)
        b = compute_match(profil(), offre(description=OFFRE_FR), MAINTENANT)

        assert a == b

    def test_seule_l_anciennete_depend_de_la_date_de_reference(self) -> None:
        a = compute_match(profil(), offre(description=OFFRE_FR), MAINTENANT)
        b = compute_match(profil(), offre(description=OFFRE_FR), MAINTENANT + timedelta(days=60))
        ca, cb = _par_critere(a), _par_critere(b)

        assert ca[Criterion.FRESHNESS].score != cb[Criterion.FRESHNESS].score
        for critere in Criterion:
            if critere not in (Criterion.FRESHNESS, Criterion.EXPERIENCE):
                assert ca[critere].score == cb[critere].score  # l'expérience en cours grandit aussi


class TestExplications:
    def test_correspondances_et_ecarts_sont_regroupes_avec_leur_critere(self) -> None:
        r = compute_match(profil(), offre(description=OFFRE_FR), MAINTENANT)

        presents = {(i.criterion, i.label) for i in r.matches if i.kind is MatchKind.PRESENT}
        absents = {(i.criterion, i.label) for i in r.gaps if i.kind is MatchKind.ABSENT}
        non_verifiables = {i.label for i in r.gaps if i.kind is MatchKind.UNVERIFIABLE}

        assert (Criterion.SKILLS, "SQL") in presents
        assert (Criterion.SKILLS, "Power BI") in absents
        assert "Esprit d'équipe et autonomie" in non_verifiables
        assert all(i.criterion is not None for i in (*r.matches, *r.gaps))

    def test_chaque_critere_evalue_est_explique(self) -> None:
        r = compute_match(profil(), offre(description=OFFRE_FR), MAINTENANT)

        for c in r.criteria:
            assert c.explanation.strip(), f"critère {c.criterion} sans explication"

    def test_le_resume_cite_forces_faiblesses_et_manques(self) -> None:
        mauvais_contrat = profil(employment_types=("fixed_term",), salary_min=None)

        r = compute_match(mauvais_contrat, offre(description=OFFRE_FR), MAINTENANT)

        assert "Points forts" in r.summary
        assert "Points d'attention : contrat" in r.summary
        assert "Données manquantes (non comptées) : salaire" in r.summary

    @pytest.mark.parametrize(
        "description", ["", OFFRE_FR, OFFRE_EN, OFFRE_SANS_STRUCTURE, "\n\n   \n"]
    )
    def test_aucun_plantage_sur_des_textes_varies(self, description: str) -> None:
        compute_match(profil(), offre(description=description), MAINTENANT)

    def test_resultat_incertain_signale_pour_dates_partielles(self) -> None:
        from app.modules.job_intelligence.domain.matching.models import ExperiencePeriod, YearMonth

        p = profil(experience_periods=(ExperiencePeriod(YearMonth(2020), YearMonth(2022)),))
        r = compute_match(
            p, offre(description="Profil recherché\n- 2 ans d'expérience\n"), MAINTENANT
        )

        assert _par_critere(r)[Criterion.EXPERIENCE].uncertain is True
