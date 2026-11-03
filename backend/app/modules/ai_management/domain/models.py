"""Modèles du domaine IA : requête, réponse, tarifs. Aucun fournisseur précis (ADR-0005)."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any


class AIMode(StrEnum):
    """Mode d'usage choisi par l'utilisateur (TASK-010-22, 010-23)."""

    DISABLED = "disabled"
    ECONOMY = "economy"
    BALANCED = "balanced"
    QUALITY = "quality"


class BackendPreference(StrEnum):
    """Où exécuter l'IA : en local, via une API payante, ou les deux (hybride)."""

    LOCAL_ONLY = "local_only"
    API_ONLY = "api_only"
    HYBRID = "hybrid"
    """Local d'abord quand il sait faire la tâche ; l'API payante prend le relais, sous plafond."""


class ProviderKind(StrEnum):
    API = "api"  # payant, les données quittent la machine
    LOCAL = "local"  # gratuit, les données restent sur la machine


class FinishReason(StrEnum):
    COMPLETE = "complete"
    TRUNCATED = "truncated"  # sortie coupée par la limite de tokens


@dataclass(frozen=True, slots=True)
class ModelPricing:
    """Tarif d'un modèle, par million de tokens, dans une devise donnée."""

    model: str
    input_per_million: Decimal
    output_per_million: Decimal
    currency: str

    def __post_init__(self) -> None:
        if self.input_per_million < 0 or self.output_per_million < 0:
            raise ValueError("Un tarif ne peut pas être négatif.")
        if len(self.currency) != 3 or not self.currency.isupper():
            raise ValueError("Devise invalide.")


@dataclass(frozen=True, slots=True)
class AIRequest:
    """Une demande à un modèle. `content` est une donnée, jamais une instruction."""

    task_type: str
    level: int
    """1 = modèle économique (extraction, classification, résumé) ; 2 = modèle performant."""
    prompt_version: str
    instructions: str
    content: str
    max_output_tokens: int
    json_schema: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.level not in (1, 2):
            raise ValueError("Le niveau d'un appel IA est 1 ou 2 (le niveau 0 n'appelle pas d'IA).")
        if self.max_output_tokens < 1:
            raise ValueError("max_output_tokens doit être positif.")
        if not self.task_type or not self.prompt_version:
            raise ValueError("task_type et prompt_version sont obligatoires.")


@dataclass(frozen=True, slots=True)
class ProviderResult:
    text: str
    input_tokens: int
    output_tokens: int
    finish: FinishReason = FinishReason.COMPLETE
    actual_cost: Decimal | None = None
    """Coût réel si le fournisseur le communique ; sinon il est calculé depuis les tarifs."""


@dataclass(frozen=True, slots=True)
class BudgetLimits:
    """Plafonds de l'utilisateur. `None` = non défini (donc aucun appel payant)."""

    daily: Decimal | None
    monthly: Decimal | None
    per_operation_level1: Decimal
    per_operation_level2: Decimal
    currency: str
    alert_thresholds: tuple[int, ...] = field(default=(50, 80, 100))

    @property
    def is_defined(self) -> bool:
        return self.daily is not None and self.monthly is not None

    def per_operation(self, level: int) -> Decimal:
        return self.per_operation_level1 if level == 1 else self.per_operation_level2
