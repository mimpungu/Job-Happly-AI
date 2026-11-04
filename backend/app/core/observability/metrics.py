"""Mesures de performance en mémoire (TASK-018-26) : suffisantes pour l'app locale mono-processus.

Par route (modèle d'URL, jamais l'URL brute) : volume, erreurs, durées moyenne, p50 et p95 sur
les dernières mesures. Les mesures sont perdues au redémarrage : c'est assumé et documenté.
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from dataclasses import dataclass, field

_WINDOW = 500
_MAX_ROUTES = 300  # borne mémoire : un chemin imprévu ne peut pas faire grossir la table sans fin


@dataclass
class _RouteStats:
    count: int = 0
    errors: int = 0
    total_ms: float = 0.0
    samples: deque[float] = field(default_factory=lambda: deque(maxlen=_WINDOW))


def _percentile(valeurs: list[float], p: float) -> float:
    ordonnees = sorted(valeurs)
    rang = max(0, math.ceil(p / 100 * len(ordonnees)) - 1)
    return ordonnees[rang]


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._routes: dict[str, _RouteStats] = {}
        self._started = time.monotonic()
        self.rate_limited = 0

    def record(self, route: str, method: str, status: int, duration_ms: float) -> None:
        cle = f"{method} {route}"
        with self._lock:
            stats = self._routes.get(cle)
            if stats is None:
                if len(self._routes) >= _MAX_ROUTES:
                    cle = "OTHER"
                stats = self._routes.setdefault(cle, _RouteStats())
            stats.count += 1
            stats.total_ms += duration_ms
            stats.samples.append(duration_ms)
            if status >= 500:
                stats.errors += 1

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            routes = {
                cle: {
                    "count": s.count,
                    "errors": s.errors,
                    "avg_ms": round(s.total_ms / s.count, 1),
                    "p50_ms": round(_percentile(list(s.samples), 50), 1),
                    "p95_ms": round(_percentile(list(s.samples), 95), 1),
                }
                for cle, s in self._routes.items()
                if s.count
            }
            total = sum(s.count for s in self._routes.values())
            erreurs = sum(s.errors for s in self._routes.values())
            return {
                "uptime_seconds": round(time.monotonic() - self._started),
                "requests": total,
                "server_errors": erreurs,
                "rate_limited": self.rate_limited,
                "routes": routes,
            }
