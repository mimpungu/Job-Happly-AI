"""Limitation de débit par fenêtre glissante, en mémoire (TASK-018-06).

Limite assumée (ADR-0008, application locale mono-processus) : le compteur est local au
processus. Un déploiement multi-processus devra le déplacer dans un stockage partagé.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable

_MAX_CLES = 10_000


class SlidingWindowLimiter:
    def __init__(
        self, limit: int, window_seconds: float = 60.0, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._limit = limit
        self._window = window_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._hits: defaultdict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> tuple[bool, int]:
        """(autorisé, secondes avant de pouvoir réessayer)."""
        maintenant = self._clock()
        with self._lock:
            if len(self._hits) > _MAX_CLES:
                self._hits.clear()  # protection mémoire : on oublie plutôt que de grossir
            fenetre = self._hits[key]
            while fenetre and maintenant - fenetre[0] >= self._window:
                fenetre.popleft()
            if len(fenetre) >= self._limit:
                return False, max(1, int(self._window - (maintenant - fenetre[0])) + 1)
            fenetre.append(maintenant)
            return True, 0
