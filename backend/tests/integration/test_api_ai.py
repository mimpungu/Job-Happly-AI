"""API des réglages IA : aucune IA appelée, seulement la configuration et le suivi."""

from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai_management.application.gateway import AIGateway
from app.modules.ai_management.application.providers import get_providers
from app.modules.ai_management.domain.models import ProviderKind
from app.modules.ai_management.presentation.dependencies import get_gateway
from tests.integration.conftest import SessionPartagee
from tests.unit.ai_management.fakes import FakeProvider


async def test_par_defaut_aucun_appel_payant_n_est_possible(client: httpx.AsyncClient) -> None:
    reponse = await client.get("/api/v1/ai/settings")

    corps = reponse.json()
    assert reponse.status_code == 200
    assert corps["mode"] == "economy" and corps["backend_preference"] == "hybrid"
    assert corps["budget_defined"] is False and corps["api_consent"] is False
    assert corps["providers"] == [] and corps["paid_calls_possible"] is False
    assert Decimal(corps["per_operation_level1"]) == Decimal("0.02")
    assert Decimal(corps["per_operation_level2"]) == Decimal("0.30")


async def test_definit_les_plafonds_le_consentement_et_le_mode(client: httpx.AsyncClient) -> None:
    budget = await client.put(
        "/api/v1/ai/budget",
        json={
            "daily": "1",
            "monthly": "10",
            "currency": "EUR",
            "alert_thresholds": [100, 50, 80, 50],
        },
    )
    consentement = await client.put("/api/v1/ai/consent", json={"accepted": True})
    mode = await client.put(
        "/api/v1/ai/settings", json={"mode": "quality", "backend_preference": "local_only"}
    )

    assert budget.json()["budget_defined"] is True and budget.json()["alert_thresholds"] == [
        50,
        80,
        100,
    ]
    assert consentement.json()["api_consent"] is True
    final = mode.json()
    assert (final["mode"], final["backend_preference"]) == ("quality", "local_only")
    assert Decimal(final["daily_budget"]) == 1 and Decimal(final["monthly_budget"]) == 10
    retire = await client.put("/api/v1/ai/consent", json={"accepted": False})
    assert retire.json()["api_consent"] is False


@pytest.mark.parametrize(
    "corps",
    [
        {"daily": "0", "monthly": "10", "currency": "EUR"},
        {"daily": "-1", "monthly": "10", "currency": "EUR"},
        {"daily": "1", "monthly": "10", "currency": "euro"},
        {"daily": "1.234", "monthly": "10", "currency": "EUR"},
        {"daily": "1", "monthly": "10", "currency": "EUR", "alert_thresholds": [0]},
        {"daily": "1", "monthly": "10", "currency": "EUR", "alert_thresholds": [101]},
        {"daily": "1", "monthly": "10", "currency": "EUR", "inconnu": 1},
    ],
)
async def test_refuse_des_plafonds_invalides(
    client: httpx.AsyncClient, corps: dict[str, object]
) -> None:
    assert (await client.put("/api/v1/ai/budget", json=corps)).status_code == 422


async def test_refuse_un_mode_inconnu_ou_une_limite_nulle(client: httpx.AsyncClient) -> None:
    assert (await client.put("/api/v1/ai/settings", json={"mode": "turbo"})).status_code == 422
    assert (
        await client.put("/api/v1/ai/settings", json={"per_operation_level1": "0"})
    ).status_code == 422


async def test_un_fournisseur_configure_est_liste_sans_rendre_les_appels_possibles(
    client: httpx.AsyncClient,
) -> None:
    application = client._transport.app  # type: ignore[attr-defined]
    application.dependency_overrides[get_providers] = lambda: [FakeProvider("api-test")]

    avant = (await client.get("/api/v1/ai/settings")).json()
    await client.put("/api/v1/ai/budget", json={"daily": "1", "monthly": "10", "currency": "EUR"})
    sans_consentement = (await client.get("/api/v1/ai/settings")).json()
    await client.put("/api/v1/ai/consent", json={"accepted": True})
    apres = (await client.get("/api/v1/ai/settings")).json()

    assert avant["providers"][0] == {
        "name": "api-test",
        "kind": "api",
        "models": ["grand", "petit"],
        "key_hint": None,
        "uses_data_for_training": False,
    }
    assert avant["paid_calls_possible"] is False
    assert sans_consentement["paid_calls_possible"] is False
    assert apres["paid_calls_possible"] is True


async def test_consommation_vide_au_depart(client: httpx.AsyncClient) -> None:
    corps = (await client.get("/api/v1/ai/usage")).json()

    assert corps["spent_today"] == "0" and corps["percent_today"] is None
    assert corps["recent"] == [] and corps["by_provider_month"] == {}


REPONSE_IA = '{"summary": "s", "skills": ["Python"]}'


def _brancher(
    client: httpx.AsyncClient, session: AsyncSession, *fournisseurs: FakeProvider
) -> None:
    application = client._transport.app  # type: ignore[attr-defined]
    application.dependency_overrides[get_providers] = lambda: list(fournisseurs)
    application.dependency_overrides[get_gateway] = lambda: AIGateway(
        SessionPartagee(session), list(fournisseurs)
    )


async def test_le_test_de_bout_en_bout_exige_plafond_et_consentement(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    _brancher(client, session, FakeProvider("api-test", reponses=[REPONSE_IA]))
    await client.put("/api/v1/ai/settings", json={"backend_preference": "api_only"})

    sans_accord = await client.post("/api/v1/ai/test", json={})
    await client.put("/api/v1/ai/consent", json={"accepted": True})
    sans_plafond = await client.post("/api/v1/ai/test", json={})
    await client.put("/api/v1/ai/budget", json={"daily": "1", "monthly": "10", "currency": "EUR"})
    ok = await client.post("/api/v1/ai/test", json={})

    assert sans_accord.status_code == 409
    assert sans_accord.json()["error"]["code"] == "ai_consent_required"
    assert sans_plafond.json()["error"]["code"] == "ai_budget_not_defined"
    assert ok.status_code == 200
    corps = ok.json()
    assert corps["provider"] == "api-test" and corps["skills"] == ["Python"]
    assert corps["cache_hit"] is False and Decimal(corps["cost"]) > 0
    deuxieme = (await client.post("/api/v1/ai/test", json={})).json()
    assert deuxieme["cache_hit"] is True and Decimal(deuxieme["cost"]) == 0
    usage = (await client.get("/api/v1/ai/usage")).json()
    assert [r["outcome"] for r in usage["recent"]][:2] == ["cache_hit", "success"]


async def test_le_test_en_local_ne_demande_ni_plafond_ni_consentement(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    local = FakeProvider("ollama-test", ProviderKind.LOCAL, reponses=[REPONSE_IA])
    _brancher(client, session, local)
    await client.put("/api/v1/ai/settings", json={"backend_preference": "local_only"})

    reponse = await client.post("/api/v1/ai/test", json={})

    assert reponse.status_code == 200 and reponse.json()["provider"] == "ollama-test"
    assert Decimal(reponse.json()["cost"]) == 0


async def test_sans_fournisseur_le_test_explique_quoi_configurer(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    _brancher(client, session)

    reponse = await client.post("/api/v1/ai/test", json={})

    assert reponse.status_code == 409 and reponse.json()["error"]["code"] == "ai_not_configured"


async def test_une_sortie_invalide_du_fournisseur_est_une_erreur_502_claire(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    local = FakeProvider("ollama-test", ProviderKind.LOCAL, reponses=['{"pas": "bon"}'])
    _brancher(client, session, local)
    await client.put("/api/v1/ai/settings", json={"backend_preference": "local_only"})

    reponse = await client.post("/api/v1/ai/test", json={})

    assert reponse.status_code == 502 and reponse.json()["error"]["code"] == "ai_invalid_output"


async def test_la_cle_d_api_n_est_jamais_exposee_seul_un_indice_masque_l_est(
    client: httpx.AsyncClient,
) -> None:
    from pydantic import SecretStr

    from app.modules.ai_management.infrastructure.gemini import GeminiProvider

    cle = "AIzaSyA1234567890abcdefghij"
    application = client._transport.app  # type: ignore[attr-defined]
    application.dependency_overrides[get_providers] = lambda: [
        GeminiProvider(
            api_key=SecretStr(cle),
            tier="paid",
            model_level1="gemini-3.1-flash-lite",
            model_level2="gemini-3-flash-preview",
        )
    ]

    reponse = await client.get("/api/v1/ai/settings")

    assert reponse.json()["providers"][0]["key_hint"] == "…ghij"
    assert cle not in reponse.text and "AIzaSy" not in reponse.text


async def test_plafond_par_fournisseur_alertes_et_estimation_via_l_api(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    _brancher(client, session, FakeProvider("api-test", reponses=[REPONSE_IA]))
    await client.put("/api/v1/ai/settings", json={"backend_preference": "api_only"})
    await client.put("/api/v1/ai/consent", json={"accepted": True})
    await client.put("/api/v1/ai/budget", json={"daily": "1", "monthly": "10", "currency": "EUR"})

    inconnu = await client.put("/api/v1/ai/provider-caps/inconnu", json={"daily": "0.5"})
    pose = await client.put("/api/v1/ai/provider-caps/api-test", json={"daily": "0.5"})
    retire = await client.put("/api/v1/ai/provider-caps/api-test", json={"daily": None})
    estimation = await client.post("/api/v1/ai/estimate", json={"characters": 1000})
    usage = (await client.get("/api/v1/ai/usage")).json()

    assert inconnu.status_code == 409
    assert pose.json()["provider_daily_caps"] == {"api-test": "0.50"}
    assert retire.json()["provider_daily_caps"] == {}
    corps = estimation.json()
    assert corps["paid"] is True and Decimal(corps["cost"]) > 0 and corps["allowed"] is True
    assert usage["alerts"] == []  # rien dépensé : aucune alerte


async def test_plafond_par_tache_et_estimation_d_une_tache_via_l_api(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    _brancher(client, session, FakeProvider("api-test", reponses=[REPONSE_IA]))
    await client.put("/api/v1/ai/settings", json={"backend_preference": "api_only"})
    await client.put("/api/v1/ai/consent", json={"accepted": True})
    await client.put("/api/v1/ai/budget", json={"daily": "1", "monthly": "10", "currency": "EUR"})

    inconnue = await client.put("/api/v1/ai/task-caps/inconnue", json={"daily": "0.5"})
    pose = await client.put("/api/v1/ai/task-caps/offer_summary", json={"daily": "0.01"})
    estimation = (
        await client.post("/api/v1/ai/estimate", json={"task_type": "offer_summary"})
    ).json()
    sans_taille = await client.post("/api/v1/ai/estimate", json={})
    retire = await client.put("/api/v1/ai/task-caps/offer_summary", json={"daily": None})

    assert inconnue.status_code == 409
    corps = pose.json()
    assert corps["task_daily_caps"] == {"offer_summary": "0.01"}
    assert {t["task_type"] for t in corps["tasks"]} >= {"offer_summary", "cv_rewrite"}
    # Le profil de la tâche (6 100 caractères, 600 tokens de sortie) dépasse 0,01 € : refus.
    assert estimation["paid"] is True and estimation["allowed"] is False
    assert "cette tâche" in estimation["reason"]
    assert sans_taille.status_code == 422
    assert retire.json()["task_daily_caps"] == {}


async def test_la_depense_du_mois_est_donnee_jour_par_jour_sans_trou(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    _brancher(client, session, FakeProvider("api-test", reponses=[REPONSE_IA]))
    await client.put("/api/v1/ai/settings", json={"backend_preference": "api_only"})
    await client.put("/api/v1/ai/consent", json={"accepted": True})
    await client.put("/api/v1/ai/budget", json={"daily": "1", "monthly": "10", "currency": "EUR"})
    await client.post("/api/v1/ai/test", json={})

    corps = (await client.get("/api/v1/ai/usage")).json()

    jours = corps["daily_spend"]
    aujourdhui = datetime.now(UTC).date()
    # Un point par jour, du 1er du mois à aujourd'hui ; les jours sans appel valent 0.
    assert jours[0]["date"] == aujourdhui.replace(day=1).isoformat()
    assert jours[-1]["date"] == aujourdhui.isoformat()
    assert len(jours) == aujourdhui.day
    assert Decimal(jours[-1]["cost"]) == Decimal(corps["spent_today"]) > 0
    assert sum(Decimal(j["cost"]) for j in jours) == Decimal(corps["spent_month"])
