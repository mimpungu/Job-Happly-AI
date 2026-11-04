"""AIGateway : seul point d'entrée des appels IA (cache, consentement, plafonds, journal).

Ordre appliqué à chaque appel :
1. IA désactivée ou aucun fournisseur utilisable → refus explicite ;
2. routes ordonnées : le local d'abord, l'API payante ensuite (mode hybride) ;
3. cache (empreinte tâche + version du prompt + modèle + contenu) → aucun appel ;
4. pour une API payante seulement : consentement, plafonds définis, coût estimé *avant* l'appel,
   refus si un plafond serait dépassé ;
5. appel avec délai maximal, puis validation stricte de la sortie ;
6. journal de chaque tentative (réussie, refusée, en échec) avec tokens et coût.

Limite assumée : le verrou qui sérialise « contrôle du plafond → appel → journal » est interne
au processus. C'est suffisant pour l'application locale mono-processus (ADR-0008) ; un déploiement
multi-processus devra le remplacer par un verrou en base.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from app.core.database.session import UnitOfWork
from app.modules.ai_management.domain.budget import decide
from app.modules.ai_management.domain.cost import cache_key, cost_of, estimate_worst_case
from app.modules.ai_management.domain.enums import CallOutcome
from app.modules.ai_management.domain.errors import (
    AIDisabledError,
    AINotConfiguredError,
    BudgetExceededError,
    BudgetNotDefinedError,
    ConsentRequiredError,
    IncompleteOutputError,
    InvalidOutputError,
    PersonalDataBlockedError,
    ProviderFailureError,
)
from app.modules.ai_management.domain.framing import injection_markers
from app.modules.ai_management.domain.models import (
    AIMode,
    AIRequest,
    FinishReason,
    ModelPricing,
    PersonalDataPolicy,
    ProviderKind,
)
from app.modules.ai_management.domain.provider import AIProvider
from app.modules.ai_management.domain.routing import Route, plan_routes
from app.modules.ai_management.infrastructure.models import AIUsageModel
from app.modules.ai_management.infrastructure.repositories import (
    AIConfig,
    SqlAICacheRepository,
    SqlAIConfigRepository,
    SqlAIUsageRepository,
)

logger = logging.getLogger("happly.ai")

DEFAULT_CACHE_TTL = timedelta(days=30)
DEFAULT_TIMEOUT = 60.0


@dataclass(frozen=True, slots=True)
class AIResult[T]:
    value: T
    provider: str
    model: str
    cache_hit: bool
    cost: Decimal
    input_tokens: int
    output_tokens: int
    crossed_thresholds: tuple[int, ...] = ()
    """Seuils d'alerte (en %) franchis par cet appel : à signaler à l'utilisateur."""


@dataclass(frozen=True, slots=True)
class CostEstimate:
    """Coût maximal plausible d'une opération, avant tout appel (TASK-010-28)."""

    provider: str
    model: str
    paid: bool
    cost: Decimal
    currency: str
    allowed: bool
    reason: str | None = None
    """Pourquoi l'appel serait refusé (consentement, plafond…), `None` s'il est possible."""


def _debut_du_jour(maintenant: datetime) -> datetime:
    return maintenant.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


def _debut_du_mois(maintenant: datetime) -> datetime:
    return _debut_du_jour(maintenant).replace(day=1)


class AIGateway:
    def __init__(
        self,
        uow: UnitOfWork,
        providers: Sequence[AIProvider],
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        timeout: float = DEFAULT_TIMEOUT,
        cache_ttl: timedelta | None = DEFAULT_CACHE_TTL,
    ) -> None:
        self._uow = uow
        self._providers = tuple(providers)
        self._clock = clock
        self._timeout = timeout
        self._cache_ttl = cache_ttl
        self._verrous: defaultdict[uuid.UUID, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def run[T](
        self,
        *,
        owner_id: uuid.UUID,
        request: AIRequest,
        validate: Callable[[Any], T],
        operation_id: uuid.UUID | None = None,
    ) -> AIResult[T]:
        """Exécute une tâche IA et retourne une valeur déjà validée par `validate`.

        `validate` reçoit le JSON décodé (ou le texte brut sans schéma) et doit lever
        `ValueError` si la sortie n'est pas conforme.
        """
        operation = operation_id or uuid.uuid4()
        async with self._uow.begin() as session:
            config = await SqlAIConfigRepository(session).get(owner_id)
        if config.mode is AIMode.DISABLED:
            raise AIDisabledError("L'IA est désactivée dans vos réglages.")
        request = self._appliquer_confidentialite(request, config)
        marqueurs = injection_markers(request.content)
        if marqueurs:
            # Signalement seulement : le contenu reste une donnée encadrée, jamais une consigne.
            logger.warning(
                "Formulation d'injection de prompt repérée dans un contenu externe",
                extra={"task_type": request.task_type, "markers": marqueurs},
            )
        routes = plan_routes(
            self._providers, request, mode=config.mode, preference=config.preference
        )
        if not routes:
            raise AINotConfiguredError(
                "Aucun fournisseur IA utilisable pour cette tâche "
                "(configurez un modèle local ou une API payante)."
            )

        for route in routes[:-1]:
            try:
                return await self._essayer(owner_id, operation, config, route, request, validate)
            except ProviderFailureError:
                continue  # hybride : la route suivante (l'API) prend le relais du local
        return await self._essayer(owner_id, operation, config, routes[-1], request, validate)

    async def estimate(self, *, owner_id: uuid.UUID, request: AIRequest) -> CostEstimate:
        """Coût maximal et faisabilité d'une opération, sans l'exécuter ni rien journaliser."""
        async with self._uow.begin() as session:
            config = await SqlAIConfigRepository(session).get(owner_id)
        if config.mode is AIMode.DISABLED:
            raise AIDisabledError("L'IA est désactivée dans vos réglages.")
        request = self._appliquer_confidentialite(request, config)
        routes = plan_routes(
            self._providers, request, mode=config.mode, preference=config.preference
        )
        if not routes:
            raise AINotConfiguredError(
                "Aucun fournisseur IA utilisable pour cette tâche "
                "(configurez un modèle local ou une API payante)."
            )
        route = routes[0]
        tarif = route.provider.pricing[route.model]
        devise = config.limits.currency
        if route.provider.kind is not ProviderKind.API:
            return CostEstimate(route.provider.name, route.model, False, Decimal(0), devise, True)
        estimation = estimate_worst_case(request, tarif)
        raison = await self._raison_de_refus(owner_id, config, route, request, tarif, estimation)
        return CostEstimate(
            route.provider.name,
            route.model,
            True,
            estimation,
            tarif.currency,
            raison is None,
            raison,
        )

    async def _raison_de_refus(
        self,
        owner_id: uuid.UUID,
        config: AIConfig,
        route: Route,
        request: AIRequest,
        tarif: ModelPricing,
        estimation: Decimal,
    ) -> str | None:
        limites = config.limits
        if config.api_consent_at is None:
            return "Acceptez d'abord l'envoi de données à l'API payante (réglages IA)."
        if not limites.is_defined:
            return "Aucun plafond défini : définissez un plafond journalier et mensuel."
        if tarif.currency != limites.currency:
            return "Le tarif du modèle n'est pas dans la devise de vos plafonds."
        maintenant = self._clock()
        jusque = maintenant + timedelta(seconds=1)
        async with self._uow.begin() as session:
            usage = SqlAIUsageRepository(session)
            aujourdhui = await usage.total_cost(
                owner_id=owner_id, since=_debut_du_jour(maintenant), until=jusque
            )
            ce_mois = await usage.total_cost(
                owner_id=owner_id, since=_debut_du_mois(maintenant), until=jusque
            )
            fournisseur = await usage.total_cost(
                owner_id=owner_id,
                since=_debut_du_jour(maintenant),
                until=jusque,
                provider=route.provider.name,
            )
        decision = decide(
            limites,
            level=request.level,
            estimated=estimation,
            spent_today=aujourdhui,
            spent_month=ce_mois,
            spent_provider_today=fournisseur,
            provider_daily_cap=config.provider_daily_caps.get(route.provider.name),
        )
        return None if decision.allowed else decision.reason

    @staticmethod
    def _appliquer_confidentialite(request: AIRequest, config: AIConfig) -> AIRequest:
        """Politique de confidentialité de l'utilisateur : elle ne peut que restreindre l'appel."""
        if not request.contains_personal_data:
            return request
        if config.personal_data_policy is PersonalDataPolicy.NEVER:
            raise PersonalDataBlockedError(
                "Vos réglages de confidentialité interdisent d'envoyer des données personnelles "
                "à l'IA."
            )
        if config.personal_data_policy is PersonalDataPolicy.LOCAL_ONLY:
            autorises = request.allowed_kinds or frozenset(ProviderKind)
            return replace(request, allowed_kinds=autorises & {ProviderKind.LOCAL})
        return request

    # ------------------------------------------------------------------ une route

    async def _essayer[T](
        self,
        owner_id: uuid.UUID,
        operation: uuid.UUID,
        config: AIConfig,
        route: Route,
        request: AIRequest,
        validate: Callable[[Any], T],
    ) -> AIResult[T]:
        tarif = route.provider.pricing[route.model]
        cle = cache_key(request, route.model)

        async with self._uow.begin() as session:
            en_cache = await SqlAICacheRepository(session).get(owner_id, cle, self._clock())
        if en_cache is not None:
            try:
                valeur = validate(en_cache["value"])
            except (ValueError, KeyError, TypeError):
                valeur = None  # entrée devenue invalide (schéma modifié) : on l'ignore
            if valeur is not None:
                await self._journaliser(
                    owner_id,
                    operation,
                    route,
                    request,
                    tarif,
                    CallOutcome.CACHE_HIT,
                    0,
                    0,
                    Decimal(0),
                    0,
                    cache_hit=True,
                )
                return AIResult(valeur, route.provider.name, route.model, True, Decimal(0), 0, 0)

        payant = route.provider.kind is ProviderKind.API
        # Le contrôle du plafond et l'appel sont sérialisés : deux appels simultanés ne peuvent
        # pas chacun passer le contrôle puis, ensemble, dépasser le plafond.
        verrou = self._verrous[owner_id] if payant else None
        if verrou is not None:
            await verrou.acquire()
        try:
            franchis: tuple[int, ...] = ()
            estimation = Decimal(0)
            if payant:
                estimation, franchis = await self._controler_budget(
                    owner_id, operation, config, route, request, tarif
                )
            return await self._appeler(
                owner_id, operation, route, request, tarif, validate, cle, estimation, franchis
            )
        finally:
            if verrou is not None:
                verrou.release()

    async def _controler_budget(
        self,
        owner_id: uuid.UUID,
        operation: uuid.UUID,
        config: AIConfig,
        route: Route,
        request: AIRequest,
        tarif: ModelPricing,
    ) -> tuple[Decimal, tuple[int, ...]]:
        """Refuse l'appel payant si une condition manque ou si le plafond serait dépassé."""
        limites = config.limits
        estimation = estimate_worst_case(request, tarif)
        if config.api_consent_at is None:
            await self._bloquer(owner_id, operation, route, request, tarif, estimation)
            raise ConsentRequiredError(
                "Acceptez d'abord l'envoi de données à l'API payante (réglages IA)."
            )
        if not limites.is_defined:
            await self._bloquer(owner_id, operation, route, request, tarif, estimation)
            raise BudgetNotDefinedError(
                "Aucun plafond défini : définissez un plafond journalier et mensuel avant "
                "d'utiliser une API payante."
            )
        if tarif.currency != limites.currency:
            await self._bloquer(owner_id, operation, route, request, tarif, estimation)
            raise BudgetExceededError(
                f"Le tarif du modèle est en {tarif.currency} mais vos plafonds sont en "
                f"{limites.currency} : aucune conversion n'est faite, l'appel est refusé."
            )
        maintenant = self._clock()
        async with self._uow.begin() as session:
            usage = SqlAIUsageRepository(session)
            aujourdhui = await usage.total_cost(
                owner_id=owner_id,
                since=_debut_du_jour(maintenant),
                until=maintenant + timedelta(seconds=1),
            )
            ce_mois = await usage.total_cost(
                owner_id=owner_id,
                since=_debut_du_mois(maintenant),
                until=maintenant + timedelta(seconds=1),
            )
            depense_fournisseur = await usage.total_cost(
                owner_id=owner_id,
                since=_debut_du_jour(maintenant),
                until=maintenant + timedelta(seconds=1),
                provider=route.provider.name,
            )
        decision = decide(
            limites,
            level=request.level,
            estimated=estimation,
            spent_today=aujourdhui,
            spent_month=ce_mois,
            spent_provider_today=depense_fournisseur,
            provider_daily_cap=config.provider_daily_caps.get(route.provider.name),
        )
        if not decision.allowed:
            await self._bloquer(owner_id, operation, route, request, tarif, estimation)
            raise BudgetExceededError(decision.reason or "Plafond atteint.")
        return estimation, decision.crossed_thresholds

    async def _appeler[T](
        self,
        owner_id: uuid.UUID,
        operation: uuid.UUID,
        route: Route,
        request: AIRequest,
        tarif: ModelPricing,
        validate: Callable[[Any], T],
        cle: str,
        estimation: Decimal,
        franchis: tuple[int, ...],
    ) -> AIResult[T]:
        debut = time.monotonic()
        try:
            resultat = await asyncio.wait_for(
                route.provider.generate(request, route.model), timeout=self._timeout
            )
        except TimeoutError as erreur:
            await self._journaliser(
                owner_id,
                operation,
                route,
                request,
                tarif,
                CallOutcome.ERROR,
                0,
                0,
                Decimal(0),
                _ms(debut),
                estimated=estimation,
            )
            raise ProviderFailureError("Le fournisseur IA n'a pas répondu à temps.") from erreur
        except ProviderFailureError:
            await self._journaliser(
                owner_id,
                operation,
                route,
                request,
                tarif,
                CallOutcome.ERROR,
                0,
                0,
                Decimal(0),
                _ms(debut),
                estimated=estimation,
            )
            raise

        reel = resultat.actual_cost
        cout = (
            reel
            if reel is not None
            else cost_of(tarif, resultat.input_tokens, resultat.output_tokens)
        )
        duree = _ms(debut)

        if resultat.finish is FinishReason.TRUNCATED:
            await self._journaliser(
                owner_id,
                operation,
                route,
                request,
                tarif,
                CallOutcome.INVALID_OUTPUT,
                resultat.input_tokens,
                resultat.output_tokens,
                cout,
                duree,
                estimated=estimation,
            )
            raise IncompleteOutputError(
                "La réponse a été coupée par la limite de tokens : elle n'est pas utilisée."
            )
        try:
            brut: Any = (
                json.loads(resultat.text) if request.json_schema is not None else resultat.text
            )
            valeur = validate(brut)
        except (ValueError, TypeError) as erreur:
            # Les tokens ont été consommés : le coût est journalisé même si la sortie est rejetée.
            await self._journaliser(
                owner_id,
                operation,
                route,
                request,
                tarif,
                CallOutcome.INVALID_OUTPUT,
                resultat.input_tokens,
                resultat.output_tokens,
                cout,
                duree,
                estimated=estimation,
            )
            raise InvalidOutputError(
                "La sortie de l'IA ne respecte pas le format attendu."
            ) from erreur

        await self._journaliser(
            owner_id,
            operation,
            route,
            request,
            tarif,
            CallOutcome.SUCCESS,
            resultat.input_tokens,
            resultat.output_tokens,
            cout,
            duree,
            estimated=estimation,
        )
        await self._memoriser(owner_id, cle, request, route.model, brut)
        return AIResult(
            valeur,
            route.provider.name,
            route.model,
            False,
            cout,
            resultat.input_tokens,
            resultat.output_tokens,
            franchis,
        )

    # ------------------------------------------------------------------ journal et cache

    async def _bloquer(
        self,
        owner_id: uuid.UUID,
        operation: uuid.UUID,
        route: Route,
        request: AIRequest,
        tarif: ModelPricing,
        estimation: Decimal,
    ) -> None:
        await self._journaliser(
            owner_id,
            operation,
            route,
            request,
            tarif,
            CallOutcome.BLOCKED_BUDGET,
            0,
            0,
            Decimal(0),
            0,
            estimated=estimation,
        )

    async def _journaliser(
        self,
        owner_id: uuid.UUID,
        operation: uuid.UUID,
        route: Route,
        request: AIRequest,
        tarif: ModelPricing,
        resultat: CallOutcome,
        tokens_entree: int,
        tokens_sortie: int,
        cout: Decimal,
        duree_ms: int,
        *,
        cache_hit: bool = False,
        estimated: Decimal = Decimal(0),
    ) -> None:
        async with self._uow.begin() as session:
            await SqlAIUsageRepository(session).add(
                AIUsageModel(
                    owner_id=owner_id,
                    provider=route.provider.name,
                    model=route.model,
                    task_type=request.task_type,
                    level=request.level,
                    input_tokens=tokens_entree,
                    output_tokens=tokens_sortie,
                    estimated_cost=estimated,
                    actual_cost=cout if resultat in _FACTURES else None,
                    currency=tarif.currency,
                    duration_ms=duree_ms,
                    operation_id=operation,
                    outcome=resultat.value,
                    cache_hit=cache_hit,
                    # Horodatage par la passerelle : les fenêtres « jour » et « mois » des
                    # plafonds se calculent avec la même horloge que le journal.
                    created_at=self._clock(),
                )
            )
        logger.info(
            "Appel IA",
            extra={
                "provider": route.provider.name,
                "model": route.model,
                "task": request.task_type,
                "outcome": resultat.value,
                "input_tokens": tokens_entree,
                "output_tokens": tokens_sortie,
            },
        )

    async def _memoriser(
        self, owner_id: uuid.UUID, cle: str, request: AIRequest, model: str, valeur: Any
    ) -> None:
        maintenant = self._clock()
        async with self._uow.begin() as session:
            await SqlAICacheRepository(session).put(
                owner_id,
                key=cle,
                task_type=request.task_type,
                prompt_version=request.prompt_version,
                model=model,
                result={"value": valeur},
                expires_at=maintenant + self._cache_ttl if self._cache_ttl else None,
            )


_FACTURES = frozenset({CallOutcome.SUCCESS, CallOutcome.INVALID_OUTPUT})


def _ms(debut: float) -> int:
    return int((time.monotonic() - debut) * 1000)
