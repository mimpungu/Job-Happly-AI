"""Faux fournisseurs de TEST : aucun appel réseau, aucun vrai modèle."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from decimal import Decimal

from app.modules.ai_management.domain.errors import ProviderFailureError
from app.modules.ai_management.domain.models import (
    AIRequest,
    FinishReason,
    ModelPricing,
    ProviderKind,
    ProviderResult,
)


class FakeProvider:
    """Retourne des réponses préparées et compte ses appels."""

    def __init__(
        self,
        name: str = "fake-api",
        kind: ProviderKind = ProviderKind.API,
        *,
        currency: str = "EUR",
        input_price: str = "3",
        output_price: str = "15",
        reponses: list[str] | None = None,
        tokens: tuple[int, int] = (400, 100),
        finish: FinishReason = FinishReason.COMPLETE,
        panne: bool = False,
        delai: float = 0.0,
        niveaux: tuple[int, ...] = (1, 2),
        entraine: bool = False,
    ) -> None:
        self._name = name
        self._kind = kind
        prix = (
            (Decimal(0), Decimal(0))
            if kind is ProviderKind.LOCAL
            else (
                Decimal(input_price),
                Decimal(output_price),
            )
        )
        self._pricing = {
            "petit": ModelPricing("petit", prix[0], prix[1], currency),
            "grand": ModelPricing("grand", prix[0], prix[1], currency),
        }
        self.reponses = reponses if reponses is not None else [json.dumps({"ok": True})]
        self.tokens = tokens
        self.finish = finish
        self.panne = panne
        self.delai = delai
        self.niveaux = niveaux
        self.appels = 0
        self._entraine = entraine

    @property
    def uses_data_for_training(self) -> bool:
        return self._entraine

    @property
    def name(self) -> str:
        return self._name

    @property
    def kind(self) -> ProviderKind:
        return self._kind

    @property
    def pricing(self) -> Mapping[str, ModelPricing]:
        return self._pricing

    def supports(self, request: AIRequest) -> bool:
        return request.level in self.niveaux

    def model_for(self, level: int, mode: str) -> str | None:
        return "petit" if level == 1 else "grand"

    async def generate(self, request: AIRequest, model: str) -> ProviderResult:
        self.appels += 1
        if self.delai:
            await asyncio.sleep(self.delai)
        if self.panne:
            raise ProviderFailureError("panne simulée")
        texte = self.reponses[min(self.appels - 1, len(self.reponses) - 1)]
        return ProviderResult(texte, self.tokens[0], self.tokens[1], self.finish)


def requete(
    contenu: str = "Texte d'une offre à résumer.", *, niveau: int = 1, schema: bool = True
) -> AIRequest:
    return AIRequest(
        task_type="offer_summary",
        level=niveau,
        prompt_version="v1",
        instructions="Résume l'offre en JSON.",
        content=contenu,
        max_output_tokens=300,
        json_schema={"type": "object"} if schema else None,
    )
