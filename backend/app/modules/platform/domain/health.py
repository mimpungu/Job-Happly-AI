"""Modèle de santé de l'application (TASK-018-25, 018-27) : fonctions pures, sans framework."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Status(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    DOWN = "down"
    NOT_CONFIGURED = "not_configured"
    """Composant facultatif absent (IA, source) : ce n'est pas une panne."""


# Composants sans lesquels l'application ne rend pas son service principal.
ESSENTIAL = frozenset({"database", "storage"})


@dataclass(frozen=True)
class ComponentHealth:
    name: str
    status: Status
    detail: str | None = None
    data: dict[str, Any] = field(default_factory=dict)


def overall_status(components: list[ComponentHealth]) -> Status:
    """`down` si un composant essentiel est en panne ; `degraded` pour toute autre anomalie.

    Un composant « non configuré » (IA, clé d'API) ne dégrade jamais l'ensemble : l'application
    fonctionne entièrement sans.
    """
    if any(c.status is Status.DOWN and c.name in ESSENTIAL for c in components):
        return Status.DOWN
    if any(c.status in (Status.DOWN, Status.DEGRADED) for c in components):
        return Status.DEGRADED
    return Status.OK
