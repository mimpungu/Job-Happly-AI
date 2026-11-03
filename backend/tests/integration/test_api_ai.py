"""API des réglages IA : aucune IA appelée, seulement la configuration et le suivi."""

from decimal import Decimal

import httpx
import pytest

from app.modules.ai_management.application.providers import get_providers
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
    }
    assert avant["paid_calls_possible"] is False
    assert sans_consentement["paid_calls_possible"] is False
    assert apres["paid_calls_possible"] is True


async def test_consommation_vide_au_depart(client: httpx.AsyncClient) -> None:
    corps = (await client.get("/api/v1/ai/usage")).json()

    assert corps["spent_today"] == "0" and corps["percent_today"] is None
    assert corps["recent"] == [] and corps["by_provider_month"] == {}
