"""AIGateway sur PostgreSQL réel : plafonds, consentement, cache, hybride, concurrence.

Aucun vrai fournisseur : des faux comptent leurs appels, ce qui prouve qu'un refus ne coûte rien.
"""

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai_management.application.gateway import AIGateway, AIResult
from app.modules.ai_management.domain.cost import estimate_worst_case
from app.modules.ai_management.domain.enums import CallOutcome
from app.modules.ai_management.domain.errors import (
    AIDisabledError,
    AINotConfiguredError,
    BudgetExceededError,
    BudgetNotDefinedError,
    ConsentRequiredError,
    IncompleteOutputError,
    InvalidOutputError,
    ProviderFailureError,
)
from app.modules.ai_management.domain.models import (
    AIMode,
    BackendPreference,
    FinishReason,
    ProviderKind,
)
from app.modules.ai_management.infrastructure.models import AICacheEntryModel, AIUsageModel
from app.modules.ai_management.infrastructure.repositories import SqlAIConfigRepository
from tests.integration.conftest import SessionPartagee
from tests.unit.ai_management.fakes import FakeProvider, requete

MAINTENANT = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)


class Resume(BaseModel):
    ok: bool


def valider(brut: object) -> Resume:
    try:
        return Resume.model_validate(brut)
    except ValidationError as erreur:
        raise ValueError(str(erreur)) from erreur


class UowSerie(SessionPartagee):
    """Une seule session est partagée par le test : on sérialise ses transactions."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self._verrou = asyncio.Lock()

    @asynccontextmanager
    async def begin(self) -> AsyncIterator[AsyncSession]:
        async with self._verrou, super().begin() as session:
            yield session


def _gateway(session: AsyncSession, *fournisseurs: FakeProvider) -> AIGateway:
    return AIGateway(UowSerie(session), fournisseurs, clock=lambda: MAINTENANT)


async def _config(
    session: AsyncSession,
    owner: uuid.UUID,
    *,
    budget: tuple[str, str] | None = ("1", "10"),
    consentement: bool = True,
    mode: AIMode = AIMode.ECONOMY,
    preference: BackendPreference = BackendPreference.API_ONLY,
) -> None:
    depot = SqlAIConfigRepository(session)
    await depot.update_settings(owner, mode=mode, preference=preference)
    if budget:
        await depot.set_budget(
            owner,
            daily=Decimal(budget[0]),
            monthly=Decimal(budget[1]),
            currency="EUR",
            alert_thresholds=(50, 80, 100),
        )
    if consentement:
        await depot.set_consent(owner, MAINTENANT)


async def _journal(session: AsyncSession) -> list[str]:
    lignes = await session.execute(select(AIUsageModel.outcome).order_by(AIUsageModel.created_at))
    return list(lignes.scalars())


async def test_appel_nominal_est_valide_journalise_et_mis_en_cache(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    await _config(session, user_id)
    api = FakeProvider()

    resultat = await _gateway(session, api).run(
        owner_id=user_id, request=requete(), validate=valider
    )

    assert resultat.value == Resume(ok=True) and not resultat.cache_hit
    assert resultat.cost > 0 and (resultat.input_tokens, resultat.output_tokens) == (400, 100)
    ligne = (await session.execute(select(AIUsageModel))).scalar_one()
    assert ligne.outcome == "success" and ligne.provider == "fake-api"
    assert ligne.actual_cost == resultat.cost.quantize(Decimal("0.000001"))
    assert await session.scalar(select(func.count()).select_from(AICacheEntryModel)) == 1


async def test_le_cache_evite_un_second_appel_payant(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    await _config(session, user_id)
    api = FakeProvider()
    gateway = _gateway(session, api)

    await gateway.run(owner_id=user_id, request=requete(), validate=valider)
    seconde = await gateway.run(owner_id=user_id, request=requete(), validate=valider)

    assert api.appels == 1
    assert seconde.cache_hit and seconde.cost == 0
    assert await _journal(session) == ["success", "cache_hit"]


async def test_un_contenu_ou_un_prompt_different_n_utilise_pas_le_cache(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    await _config(session, user_id)
    api = FakeProvider()
    gateway = _gateway(session, api)

    await gateway.run(owner_id=user_id, request=requete("offre A"), validate=valider)
    await gateway.run(owner_id=user_id, request=requete("offre B"), validate=valider)

    assert api.appels == 2


async def test_sans_plafond_aucun_appel_payant(session: AsyncSession, user_id: uuid.UUID) -> None:
    await _config(session, user_id, budget=None)
    api = FakeProvider()

    with pytest.raises(BudgetNotDefinedError):
        await _gateway(session, api).run(owner_id=user_id, request=requete(), validate=valider)

    assert api.appels == 0
    assert await _journal(session) == ["blocked_budget"]


async def test_sans_consentement_aucun_envoi_a_l_api(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    await _config(session, user_id, consentement=False)
    api = FakeProvider()

    with pytest.raises(ConsentRequiredError):
        await _gateway(session, api).run(owner_id=user_id, request=requete(), validate=valider)

    assert api.appels == 0


async def test_le_plafond_n_est_jamais_depasse_sur_une_serie_d_appels(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    await _config(session, user_id, budget=("0.05", "10"))
    api = FakeProvider()
    gateway = _gateway(session, api)
    estimation = estimate_worst_case(requete("x"), api.pricing["petit"])

    reussis = 0
    for i in range(20):
        try:
            await gateway.run(owner_id=user_id, request=requete(f"offre {i}"), validate=valider)
            reussis += 1
        except BudgetExceededError:
            break

    depense = await session.scalar(
        select(func.coalesce(func.sum(AIUsageModel.actual_cost), 0)).where(
            AIUsageModel.outcome == CallOutcome.SUCCESS.value
        )
    )
    assert 0 < reussis < 20
    assert depense is not None and Decimal(depense) <= Decimal("0.05")
    assert api.appels == reussis  # l'appel refusé n'a jamais atteint le fournisseur
    assert estimation > 0


async def test_une_estimation_au_dessus_de_la_limite_par_operation_est_refusee(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    await _config(session, user_id)
    api = FakeProvider()
    gros = requete("é" * 30_000)  # ~12 000 tokens d'entrée : bien au-delà de 0,02 €

    with pytest.raises(BudgetExceededError, match="par opération"):
        await _gateway(session, api).run(owner_id=user_id, request=gros, validate=valider)

    assert api.appels == 0


async def test_deux_appels_simultanes_ne_depassent_pas_ensemble_le_plafond(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    # Plafond minimal (0,01 €) : coût réel 0,0027 € par appel, estimation ~0,0046 €. Sans
    # sérialisation, les 6 appels passeraient le contrôle ensemble (0,0162 € dépensés).
    await _config(session, user_id, budget=("0.01", "10"))
    api = FakeProvider(delai=0.02)
    gateway = _gateway(session, api)

    resultats = await asyncio.gather(
        *(
            gateway.run(owner_id=user_id, request=requete(f"offre {i}"), validate=valider)
            for i in range(6)
        ),
        return_exceptions=True,
    )

    reussis = [r for r in resultats if isinstance(r, AIResult)]
    refus = [r for r in resultats if isinstance(r, BudgetExceededError)]
    assert refus and len(reussis) + len(refus) == 6
    assert api.appels == len(reussis)  # un refus n'atteint jamais le fournisseur
    assert sum(r.cost for r in reussis) <= Decimal("0.01")


async def test_sortie_invalide_est_rejetee_facturee_et_non_mise_en_cache(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    await _config(session, user_id)
    api = FakeProvider(reponses=[json.dumps({"pas_ok": 1})])

    with pytest.raises(InvalidOutputError):
        await _gateway(session, api).run(owner_id=user_id, request=requete(), validate=valider)

    ligne = (await session.execute(select(AIUsageModel))).scalar_one()
    assert ligne.outcome == "invalid_output" and ligne.actual_cost and ligne.actual_cost > 0
    assert await session.scalar(select(func.count()).select_from(AICacheEntryModel)) == 0


async def test_json_illisible_et_reponse_tronquee(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    await _config(session, user_id)

    with pytest.raises(InvalidOutputError):
        await _gateway(session, FakeProvider(reponses=["pas du json"])).run(
            owner_id=user_id, request=requete("a"), validate=valider
        )
    with pytest.raises(IncompleteOutputError):
        await _gateway(session, FakeProvider(finish=FinishReason.TRUNCATED)).run(
            owner_id=user_id, request=requete("b"), validate=valider
        )

    assert await session.scalar(select(func.count()).select_from(AICacheEntryModel)) == 0


async def test_panne_du_fournisseur_est_journalisee_sans_cout(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    await _config(session, user_id)

    with pytest.raises(ProviderFailureError):
        await _gateway(session, FakeProvider(panne=True)).run(
            owner_id=user_id, request=requete(), validate=valider
        )

    ligne = (await session.execute(select(AIUsageModel))).scalar_one()
    assert ligne.outcome == "error" and ligne.actual_cost is None


async def test_delai_depasse_est_une_erreur_explicite(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    await _config(session, user_id)
    gateway = AIGateway(
        UowSerie(session), [FakeProvider(delai=1.0)], clock=lambda: MAINTENANT, timeout=0.05
    )

    with pytest.raises(ProviderFailureError, match="à temps"):
        await gateway.run(owner_id=user_id, request=requete(), validate=valider)


async def test_ia_desactivee_ou_sans_fournisseur(session: AsyncSession, user_id: uuid.UUID) -> None:
    await _config(session, user_id, mode=AIMode.DISABLED)
    api = FakeProvider()
    with pytest.raises(AIDisabledError):
        await _gateway(session, api).run(owner_id=user_id, request=requete(), validate=valider)

    await _config(session, user_id, mode=AIMode.ECONOMY)
    with pytest.raises(AINotConfiguredError):
        await _gateway(session).run(owner_id=user_id, request=requete(), validate=valider)
    assert api.appels == 0


async def test_le_local_est_gratuit_sans_plafond_ni_consentement(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    await _config(
        session, user_id, budget=None, consentement=False, preference=BackendPreference.LOCAL_ONLY
    )
    local = FakeProvider("local", ProviderKind.LOCAL)

    resultat = await _gateway(session, local).run(
        owner_id=user_id, request=requete(), validate=valider
    )

    assert resultat.cost == 0 and local.appels == 1


async def test_hybride_prefere_le_local_et_n_appelle_pas_l_api(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    await _config(session, user_id, preference=BackendPreference.HYBRID)
    local, api = FakeProvider("local", ProviderKind.LOCAL), FakeProvider("api")

    resultat = await _gateway(session, api, local).run(
        owner_id=user_id, request=requete(), validate=valider
    )

    assert resultat.provider == "local" and local.appels == 1 and api.appels == 0


async def test_hybride_bascule_sur_l_api_si_le_local_tombe_et_respecte_le_plafond(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    await _config(session, user_id, preference=BackendPreference.HYBRID)
    local, api = FakeProvider("local", ProviderKind.LOCAL, panne=True), FakeProvider("api")

    resultat = await _gateway(session, api, local).run(
        owner_id=user_id, request=requete(), validate=valider
    )

    assert resultat.provider == "api" and resultat.cost > 0
    assert await _journal(session) == ["error", "success"]


async def test_hybride_sans_plafond_ne_bascule_pas_sur_l_api(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    await _config(session, user_id, budget=None, preference=BackendPreference.HYBRID)
    local, api = FakeProvider("local", ProviderKind.LOCAL, panne=True), FakeProvider("api")

    with pytest.raises(BudgetNotDefinedError):
        await _gateway(session, api, local).run(
            owner_id=user_id, request=requete(), validate=valider
        )

    assert api.appels == 0


async def test_les_seuils_d_alerte_franchis_sont_remontes(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    # Modèle cher + niveau 2 : l'estimation (~0,06 €) pèse ~60 % d'un plafond journalier de 0,10 €.
    await _config(session, user_id, budget=("0.10", "10"))
    cher = FakeProvider(input_price="40", output_price="200")

    resultat = await _gateway(session, cher).run(
        owner_id=user_id, request=requete(niveau=2), validate=valider
    )

    assert resultat.crossed_thresholds == (50,)


async def test_devise_differente_refusee_sans_conversion(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    await _config(session, user_id)
    api = FakeProvider(currency="USD")

    with pytest.raises(BudgetExceededError, match="aucune conversion"):
        await _gateway(session, api).run(owner_id=user_id, request=requete(), validate=valider)

    assert api.appels == 0


async def test_une_entree_de_cache_expiree_est_ignoree_puis_remplacee(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    await _config(session, user_id)
    api = FakeProvider()
    temps = [MAINTENANT]
    gateway = AIGateway(
        UowSerie(session), [api], clock=lambda: temps[0], cache_ttl=timedelta(days=1)
    )

    await gateway.run(owner_id=user_id, request=requete(), validate=valider)
    temps[0] = MAINTENANT + timedelta(hours=23)
    await gateway.run(owner_id=user_id, request=requete(), validate=valider)
    assert api.appels == 1  # encore valide

    temps[0] = MAINTENANT + timedelta(days=2)
    await gateway.run(owner_id=user_id, request=requete(), validate=valider)

    assert api.appels == 2  # expirée : nouvel appel, et une seule entrée (remplacée)
    assert await session.scalar(select(func.count()).select_from(AICacheEntryModel)) == 1
