"""Cas d'usage du scoring : pondérations, score d'une offre, recalcul global."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from app.modules.job_discovery.domain.search import ScoreContext
from app.modules.job_intelligence.application.ports import (
    CandidateFactsReader,
    JobOfferReader,
    MatchStore,
    NoValidatedProfileError,
    ProfileSnapshot,
    ScoreRecord,
)
from app.modules.job_intelligence.domain.matching.engine import compute_match
from app.modules.job_intelligence.domain.matching.models import (
    MatchResult,
    OfferFacts,
    ProfileFacts,
    Weights,
)
from app.modules.job_intelligence.domain.matching.serialization import match_to_dict
from app.modules.job_intelligence.domain.matching.weights import (
    DEFAULT_WEIGHTS,
    validate_weights,
    weights_version,
)

BATCH_SIZE = 200


def _maintenant() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class WeightsView:
    weights: Weights
    defaults: Weights
    version: str
    is_default: bool


@dataclass(frozen=True, slots=True)
class MatchOutcome:
    result: MatchResult
    profile_version: int
    computed_at: datetime


@dataclass(frozen=True, slots=True)
class RecomputeReport:
    computed: int
    not_computable: int
    """Offres pour lesquelles aucune donnée ne permettait un score : elles restent sans score."""
    profile_version: int
    weights_version: str


class MatchingService:
    def __init__(
        self,
        profiles: CandidateFactsReader,
        offers: JobOfferReader,
        store: MatchStore,
        *,
        clock: Callable[[], datetime] = _maintenant,
    ) -> None:
        self._profiles = profiles
        self._offers = offers
        self._store = store
        self._clock = clock

    # --- Pondérations --------------------------------------------------------------------

    async def weights(self, *, owner_id: uuid.UUID) -> WeightsView:
        brutes = await self._store.get_weights(owner_id=owner_id)
        # Une valeur stockée devenue invalide (critère retiré, etc.) ne doit pas bloquer l'app :
        # on retombe sur les pondérations par défaut plutôt que d'échouer à chaque score.
        try:
            actuelles = validate_weights(brutes) if brutes else DEFAULT_WEIGHTS
        except ValueError:
            actuelles = DEFAULT_WEIGHTS
        return WeightsView(
            weights=actuelles,
            defaults=DEFAULT_WEIGHTS,
            version=weights_version(actuelles),
            is_default=weights_version(actuelles) == weights_version(DEFAULT_WEIGHTS),
        )

    async def set_weights(self, *, owner_id: uuid.UUID, brutes: dict[str, object]) -> WeightsView:
        """Enregistre des pondérations validées (`InvalidWeightsError` sinon)."""
        validees = validate_weights(brutes)
        await self._store.set_weights(
            owner_id=owner_id,
            weights={c.value: str(p) for c, p in validees.values.items()},
            now=self._clock(),
        )
        return await self.weights(owner_id=owner_id)

    async def reset_weights(self, *, owner_id: uuid.UUID) -> WeightsView:
        await self._store.clear_weights(owner_id=owner_id)
        return await self.weights(owner_id=owner_id)

    # --- Scores ----------------------------------------------------------------------------

    async def _profil(self, owner_id: uuid.UUID) -> ProfileSnapshot:
        profil = await self._profiles.validated_snapshot(owner_id=owner_id)
        if profil is None:
            raise NoValidatedProfileError(
                "Validez votre profil dans « Espace CV » : le score se calcule uniquement sur "
                "des informations que vous avez relues et confirmées."
            )
        return profil

    async def score_context(self, *, owner_id: uuid.UUID) -> ScoreContext | None:
        """Contexte pour lire les scores déjà calculés (`None` sans profil validé)."""
        profil = await self._profiles.validated_snapshot(owner_id=owner_id)
        if profil is None:
            return None
        vue = await self.weights(owner_id=owner_id)
        return ScoreContext(profile_id=profil.profile_id, weights_version=vue.version)

    async def match_offer(self, *, owner_id: uuid.UUID, offer_id: uuid.UUID) -> MatchOutcome:
        """Score détaillé d'une offre, calculé à l'instant puis mémorisé (tri et filtres)."""
        profil = await self._profil(owner_id)
        vue = await self.weights(owner_id=owner_id)
        offre = await self._offers.get(owner_id=owner_id, offer_id=offer_id)
        maintenant = self._clock()
        resultat = compute_match(profil.facts, offre, maintenant, vue.weights)
        if resultat.score is not None:
            await self._store.save_scores(
                owner_id=owner_id,
                profile_id=profil.profile_id,
                records=[self._enregistrement(offer_id, resultat, profil.version, maintenant)],
                now=maintenant,
            )
        return MatchOutcome(resultat, profil.version, maintenant)

    async def recompute(self, *, owner_id: uuid.UUID) -> RecomputeReport:
        """Recalcule le score de toutes les offres actives (profil validé, poids actuels).

        Par lots, calcul hors de la boucle d'événements : la mémoire reste bornée et l'API reste
        réactive. Les scores obsolètes (autre version de profil ou de poids) sont supprimés.
        """
        profil = await self._profil(owner_id)
        vue = await self.weights(owner_id=owner_id)
        maintenant = self._clock()
        calcules = non_calculables = 0
        curseur: uuid.UUID | None = None
        while True:
            lot = await self._offers.active_batch(
                owner_id=owner_id, after=curseur, limit=BATCH_SIZE
            )
            if not lot:
                break
            curseur = lot[-1][0]
            resultats = await asyncio.to_thread(
                self._calculer_lot, lot, profil.facts, maintenant, vue.weights
            )
            records = [
                self._enregistrement(oid, r, profil.version, maintenant)
                for oid, r in resultats
                if r.score is not None
            ]
            non_calculables += len(resultats) - len(records)
            calcules += len(records)
            if records:
                await self._store.save_scores(
                    owner_id=owner_id, profile_id=profil.profile_id, records=records, now=maintenant
                )
        await self._store.prune_scores(
            owner_id=owner_id, profile_id=profil.profile_id, weights_version=vue.version
        )
        return RecomputeReport(calcules, non_calculables, profil.version, vue.version)

    @staticmethod
    def _calculer_lot(
        lot: list[tuple[uuid.UUID, OfferFacts]],
        facts: ProfileFacts,
        maintenant: datetime,
        poids: Weights,
    ) -> list[tuple[uuid.UUID, MatchResult]]:
        return [(oid, compute_match(facts, offre, maintenant, poids)) for oid, offre in lot]

    @staticmethod
    def _enregistrement(
        offer_id: uuid.UUID, resultat: MatchResult, version_profil: int, maintenant: datetime
    ) -> ScoreRecord:
        assert resultat.score is not None  # noqa: S101  (filtré par l'appelant)
        detail = match_to_dict(resultat)
        detail["as_of"] = maintenant.isoformat()
        detail["profile_version"] = version_profil
        return ScoreRecord(
            offer_id=offer_id,
            score=Decimal(resultat.score),
            breakdown=detail,
            weights_version=resultat.weights_version,
        )
