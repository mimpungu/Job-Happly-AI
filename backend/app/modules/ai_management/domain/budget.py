"""Décision de budget avant chaque appel (fonction pure, testée exhaustivement)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.modules.ai_management.domain.models import BudgetLimits


@dataclass(frozen=True, slots=True)
class BudgetDecision:
    allowed: bool
    reason: str | None = None
    """Explication affichable quand l'appel est refusé."""
    crossed_thresholds: tuple[int, ...] = ()
    """Seuils d'alerte (en %) franchis par la dépense *après* cet appel."""


def _pourcentage(depense: Decimal, plafond: Decimal) -> Decimal:
    return depense / plafond * 100


def _seuils(limits: BudgetLimits, avant: Decimal, apres: Decimal, plafond: Decimal) -> set[int]:
    return {
        s
        for s in limits.alert_thresholds
        if _pourcentage(avant, plafond) < s <= _pourcentage(apres, plafond)
    }


def decide(
    limits: BudgetLimits,
    *,
    level: int,
    estimated: Decimal,
    spent_today: Decimal,
    spent_month: Decimal,
    spent_provider_today: Decimal | None = None,
    provider_daily_cap: Decimal | None = None,
    spent_task_today: Decimal | None = None,
    task_daily_cap: Decimal | None = None,
) -> BudgetDecision:
    """Refuse si le coût estimé ferait dépasser un plafond. Ne dépasse jamais, même d'un centime."""
    if limits.daily is None or limits.monthly is None:
        return BudgetDecision(
            False, "Aucun plafond défini : définissez-en un avant d'utiliser l'IA."
        )
    devise = limits.currency
    par_operation = limits.per_operation(level)
    if estimated > par_operation:
        return BudgetDecision(
            False,
            f"Coût estimé {estimated:.4f} {devise} supérieur à la limite par opération "
            f"({par_operation} {devise}).",
        )
    if spent_today + estimated > limits.daily:
        return BudgetDecision(
            False,
            f"Le plafond journalier de {limits.daily} {devise} serait dépassé "
            f"(déjà dépensé : {spent_today:.4f} {devise}).",
        )
    if spent_month + estimated > limits.monthly:
        return BudgetDecision(
            False,
            f"Le plafond mensuel de {limits.monthly} {devise} serait dépassé "
            f"(déjà dépensé : {spent_month:.4f} {devise}).",
        )
    if (
        provider_daily_cap is not None
        and spent_provider_today is not None
        and spent_provider_today + estimated > provider_daily_cap
    ):
        return BudgetDecision(
            False,
            f"Le plafond de ce fournisseur ({provider_daily_cap} {devise}/jour) serait dépassé.",
        )
    if (
        task_daily_cap is not None
        and spent_task_today is not None
        and spent_task_today + estimated > task_daily_cap
    ):
        return BudgetDecision(
            False,
            f"Le plafond de cette tâche ({task_daily_cap} {devise}/jour) serait dépassé.",
        )
    franchis = _seuils(limits, spent_today, spent_today + estimated, limits.daily) | _seuils(
        limits, spent_month, spent_month + estimated, limits.monthly
    )
    return BudgetDecision(True, None, tuple(sorted(franchis)))


@dataclass(frozen=True, slots=True)
class BudgetAlert:
    period: str
    """`daily` ou `monthly`."""
    threshold: int
    """Plus haut seuil configuré atteint (en %)."""
    percent: Decimal
    spent: Decimal
    limit: Decimal


def active_alerts(
    limits: BudgetLimits, *, spent_today: Decimal, spent_month: Decimal
) -> tuple[BudgetAlert, ...]:
    """Alertes en cours : pour chaque période, le plus haut seuil déjà atteint.

    Dérivées de la dépense réelle plutôt que stockées : elles ne peuvent ni se perdre ni rester
    affichées après un changement de plafond ou de période.
    """
    alertes: list[BudgetAlert] = []
    for periode, depense, plafond in (
        ("daily", spent_today, limits.daily),
        ("monthly", spent_month, limits.monthly),
    ):
        if plafond is None or plafond <= 0:
            continue
        pourcentage = _pourcentage(depense, plafond)
        atteints = [s for s in limits.alert_thresholds if pourcentage >= s]
        if atteints:
            alertes.append(
                BudgetAlert(
                    periode, max(atteints), pourcentage.quantize(Decimal("0.1")), depense, plafond
                )
            )
    return tuple(alertes)
