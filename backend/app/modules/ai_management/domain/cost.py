"""Estimation et calcul des coûts (fonctions pures)."""

from __future__ import annotations

import hashlib
import json
import math
from decimal import Decimal

from app.modules.ai_management.domain.models import AIRequest, ModelPricing

_MILLION = Decimal(1_000_000)
# Estimation prudente en français : ~3 caractères par token (la réalité est plutôt 3,5 à 4),
# majorée de 20 % pour ne pas sous-estimer un appel avant de l'avoir fait.
_CARACTERES_PAR_TOKEN = 3
_MARGE_ENTREE = Decimal("1.2")


def estimate_input_tokens(request: AIRequest) -> int:
    caracteres = len(request.instructions) + len(request.content)
    if request.json_schema is not None:
        caracteres += len(json.dumps(request.json_schema))
    return math.ceil(math.ceil(caracteres / _CARACTERES_PAR_TOKEN) * _MARGE_ENTREE)


def cost_of(pricing: ModelPricing, input_tokens: int, output_tokens: int) -> Decimal:
    return (
        Decimal(input_tokens) * pricing.input_per_million
        + Decimal(output_tokens) * pricing.output_per_million
    ) / _MILLION


def estimate_worst_case(request: AIRequest, pricing: ModelPricing) -> Decimal:
    """Coût maximal plausible : entrée estimée + sortie à la limite de tokens autorisée."""
    return cost_of(pricing, estimate_input_tokens(request), request.max_output_tokens)


def cache_key(request: AIRequest, model: str) -> str:
    """Empreinte de (tâche, version du prompt, modèle, instructions, contenu, schéma)."""
    canonique = json.dumps(
        [
            request.task_type,
            request.prompt_version,
            model,
            request.instructions,
            request.content,
            request.json_schema,
        ],
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(canonique.encode("utf-8")).hexdigest()
