"""Règles pures : coût, plafonds, routage, cache."""

from dataclasses import replace
from decimal import Decimal

import pytest

from app.modules.ai_management.domain.budget import decide
from app.modules.ai_management.domain.cost import (
    cache_key,
    cost_of,
    estimate_input_tokens,
    estimate_worst_case,
)
from app.modules.ai_management.domain.models import (
    AIMode,
    AIRequest,
    BackendPreference,
    BudgetLimits,
    ModelPricing,
    ProviderKind,
)
from app.modules.ai_management.domain.routing import plan_routes
from tests.unit.ai_management.fakes import FakeProvider, requete

D = Decimal


def limites(daily: str | None = "1", monthly: str | None = "10") -> BudgetLimits:
    return BudgetLimits(
        daily=D(daily) if daily else None,
        monthly=D(monthly) if monthly else None,
        per_operation_level1=D("0.02"),
        per_operation_level2=D("0.30"),
        currency="EUR",
    )


class TestCout:
    def test_calcule_le_cout_par_million_de_tokens(self) -> None:
        tarif = ModelPricing("m", D("3"), D("15"), "EUR")

        assert cost_of(tarif, 1_000_000, 0) == D(3)
        assert cost_of(tarif, 1000, 500) == D("0.0105")

    def test_l_estimation_prend_la_sortie_au_maximum(self) -> None:
        tarif = ModelPricing("m", D("3"), D("15"), "EUR")
        req = requete()

        pire = estimate_worst_case(req, tarif)

        assert pire == cost_of(tarif, estimate_input_tokens(req), req.max_output_tokens)
        assert pire > cost_of(tarif, estimate_input_tokens(req), 0)

    def test_l_estimation_surestime_plutot_que_sous_estimer(self) -> None:
        req = requete("a" * 3000, schema=False)

        # 3000 caractères ≈ 1000 tokens au pire cas (3 car./token) + 20 % de marge.
        assert estimate_input_tokens(req) >= 1200

    def test_un_tarif_negatif_ou_une_devise_invalide_est_refuse(self) -> None:
        with pytest.raises(ValueError):
            ModelPricing("m", D("-1"), D("1"), "EUR")
        with pytest.raises(ValueError):
            ModelPricing("m", D("1"), D("1"), "euro")


class TestCle:
    def test_change_avec_le_prompt_le_modele_ou_le_contenu(self) -> None:
        base = cache_key(requete(), "petit")

        assert cache_key(requete(), "petit") == base
        assert cache_key(requete(), "grand") != base
        assert cache_key(requete("autre contenu"), "petit") != base
        v2 = AIRequest(
            "offer_summary",
            1,
            "v2",
            "Résume l'offre en JSON.",
            "Texte d'une offre à résumer.",
            300,
            {"type": "object"},
        )
        assert cache_key(v2, "petit") != base


class TestBudget:
    def test_autorise_sous_les_plafonds(self) -> None:
        d = decide(limites(), level=1, estimated=D("0.01"), spent_today=D(0), spent_month=D(0))

        assert d.allowed and d.reason is None

    def test_refuse_sans_plafond_defini(self) -> None:
        d = decide(
            limites(daily=None), level=1, estimated=D("0.01"), spent_today=D(0), spent_month=D(0)
        )

        assert not d.allowed and "plafond" in (d.reason or "").lower()

    def test_refuse_au_dessus_de_la_limite_par_operation(self) -> None:
        assert not decide(
            limites(), level=1, estimated=D("0.03"), spent_today=D(0), spent_month=D(0)
        ).allowed
        assert decide(
            limites(), level=2, estimated=D("0.03"), spent_today=D(0), spent_month=D(0)
        ).allowed

    def test_ne_depasse_jamais_meme_d_un_centime(self) -> None:
        exact = decide(
            limites("1"), level=1, estimated=D("0.01"), spent_today=D("0.99"), spent_month=D(0)
        )
        depasse = decide(
            limites("1"), level=1, estimated=D("0.01"), spent_today=D("0.991"), spent_month=D(0)
        )

        assert exact.allowed  # 0.99 + 0.01 == 1.00 : pile le plafond, pas au-delà
        assert not depasse.allowed

    def test_le_plafond_mensuel_s_applique_aussi(self) -> None:
        d = decide(
            limites("1", "10"),
            level=1,
            estimated=D("0.02"),
            spent_today=D(0),
            spent_month=D("9.99"),
        )

        assert not d.allowed and "mensuel" in (d.reason or "")

    def test_signale_les_seuils_franchis(self) -> None:
        d = decide(
            limites("1"), level=1, estimated=D("0.02"), spent_today=D("0.49"), spent_month=D(0)
        )

        assert d.allowed and d.crossed_thresholds == (50,)


class TestRoutage:
    def _req(self) -> AIRequest:
        return requete()

    def test_le_hybride_essaie_le_local_puis_l_api(self) -> None:
        api, local = FakeProvider("api"), FakeProvider("local", ProviderKind.LOCAL)

        routes = plan_routes(
            [api, local], self._req(), mode=AIMode.ECONOMY, preference=BackendPreference.HYBRID
        )

        assert [r.provider.name for r in routes] == ["local", "api"]

    def test_local_seul_et_api_seule(self) -> None:
        api, local = FakeProvider("api"), FakeProvider("local", ProviderKind.LOCAL)

        seul_local = plan_routes(
            [api, local], self._req(), mode=AIMode.BALANCED, preference=BackendPreference.LOCAL_ONLY
        )
        seule_api = plan_routes(
            [api, local], self._req(), mode=AIMode.BALANCED, preference=BackendPreference.API_ONLY
        )

        assert [r.provider.name for r in seul_local] == ["local"]
        assert [r.provider.name for r in seule_api] == ["api"]

    def test_ia_desactivee_ne_donne_aucune_route(self) -> None:
        assert (
            plan_routes(
                [FakeProvider()],
                self._req(),
                mode=AIMode.DISABLED,
                preference=BackendPreference.HYBRID,
            )
            == []
        )

    def test_un_fournisseur_qui_ne_gere_pas_le_niveau_est_ignore(self) -> None:
        local_petit = FakeProvider("local", ProviderKind.LOCAL, niveaux=(1,))
        api = FakeProvider("api")

        routes = plan_routes(
            [local_petit, api],
            requete(niveau=2),
            mode=AIMode.QUALITY,
            preference=BackendPreference.HYBRID,
        )

        assert [r.provider.name for r in routes] == [
            "api"
        ]  # le local ne sait pas faire le niveau 2

    def test_niveau_zero_refuse(self) -> None:
        with pytest.raises(ValueError):
            AIRequest("t", 0, "v1", "i", "c", 10)


class TestDonneesPersonnelles:
    def _req(self, personnel: bool) -> AIRequest:
        return AIRequest("cv", 2, "v1", "i", "c", 100, contains_personal_data=personnel)

    def test_un_palier_qui_reutilise_les_contenus_est_exclu_pour_des_donnees_personnelles(
        self,
    ) -> None:
        gratuit = FakeProvider("gemini-gratuit", entraine=True)
        payant = FakeProvider("gemini-payant")

        avec = plan_routes(
            [gratuit, payant],
            self._req(True),
            mode=AIMode.QUALITY,
            preference=BackendPreference.API_ONLY,
        )
        sans = plan_routes(
            [gratuit, payant],
            self._req(False),
            mode=AIMode.QUALITY,
            preference=BackendPreference.API_ONLY,
        )

        assert [r.provider.name for r in avec] == ["gemini-payant"]
        assert [r.provider.name for r in sans] == ["gemini-gratuit", "gemini-payant"]

    def test_seul_un_palier_gratuit_donne_aucune_route_pour_des_donnees_personnelles(self) -> None:
        routes = plan_routes(
            [FakeProvider(entraine=True)],
            self._req(True),
            mode=AIMode.ECONOMY,
            preference=BackendPreference.API_ONLY,
        )

        assert routes == []


class TestRestrictionParAppel:
    def test_une_requete_limitee_au_local_n_utilise_jamais_l_api(self) -> None:
        api, local = FakeProvider("api"), FakeProvider("local", ProviderKind.LOCAL)
        requete_locale = replace(requete(), allowed_kinds=frozenset({ProviderKind.LOCAL}))

        routes = plan_routes(
            [api, local], requete_locale, mode=AIMode.ECONOMY, preference=BackendPreference.HYBRID
        )

        assert [r.provider.name for r in routes] == ["local"]

    def test_la_restriction_ne_peut_pas_elargir_le_reglage_de_l_utilisateur(self) -> None:
        api, local = FakeProvider("api"), FakeProvider("local", ProviderKind.LOCAL)
        permissive = replace(requete(), allowed_kinds=frozenset(ProviderKind))

        routes = plan_routes(
            [api, local], permissive, mode=AIMode.ECONOMY, preference=BackendPreference.LOCAL_ONLY
        )

        assert [r.provider.name for r in routes] == ["local"]

    def test_local_demande_sans_modele_local_donne_aucune_route(self) -> None:
        requete_locale = replace(requete(), allowed_kinds=frozenset({ProviderKind.LOCAL}))

        assert (
            plan_routes(
                [FakeProvider("api")],
                requete_locale,
                mode=AIMode.ECONOMY,
                preference=BackendPreference.HYBRID,
            )
            == []
        )
