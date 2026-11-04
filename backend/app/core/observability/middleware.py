"""Middleware transversal : corrélation, en-têtes de sécurité, limites, mesures et journal d'accès.

ASGI « pur » (pas de BaseHTTPMiddleware) pour ne rien bufferiser ni casser les flux. Rien du corps
ni de la query string n'est journalisé : elles peuvent contenir des données personnelles.
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

from app.core.observability.context import request_id_var
from app.core.observability.metrics import MetricsRegistry
from app.core.observability.rate_limit import SlidingWindowLimiter

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]

logger = logging.getLogger("happly.http")

_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")

# Réponses d'API : jamais mises en cache, jamais interprétées comme page ni encadrées.
SECURITY_HEADERS: tuple[tuple[bytes, bytes], ...] = (
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
    (b"cross-origin-resource-policy", b"same-site"),
    (b"cache-control", b"no-store"),
)
# Les PDF sont affichés par le navigateur : leur CSP stricte est assouplie pour `frame-ancestors`
# seulement ; ils restent sans cache partagé et sans sniffing.
_PDF_TYPE = b"application/pdf"

# Chemins coûteux (IA, génération, import, collecte) : plafond de débit plus bas.
EXPENSIVE_PREFIXES: tuple[str, ...] = (
    "/api/v1/ai",
    "/api/v1/resumes/generate",
    "/api/v1/cover-letters/generate",
    "/api/v1/profile/import",
    "/api/v1/interview-preparation/applications",
    "/api/v1/interview-preparation/simulations",
    "/api/v1/offers/search",
    "/api/v1/companies",
)


def _json_response(status: int, code: str, message: str, extra: list[tuple[bytes, bytes]]) -> Any:
    corps = json.dumps({"error": {"code": code, "message": message}}).encode()

    async def repondre(send: Send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [(b"content-type", b"application/json"), *extra],
            }
        )
        await send({"type": "http.response.body", "body": corps})

    return repondre


class ObservabilityMiddleware:
    def __init__(
        self,
        app: Callable[[Scope, Receive, Send], Awaitable[None]],
        *,
        metrics: MetricsRegistry,
        limiter: SlidingWindowLimiter,
        expensive_limiter: SlidingWindowLimiter,
        max_body_bytes: int,
    ) -> None:
        self._app = app
        self._metrics = metrics
        self._limiter = limiter
        self._expensive = expensive_limiter
        self._max_body = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        entrant = dict(scope.get("headers", [])).get(b"x-request-id", b"").decode("latin-1")
        request_id = entrant if _REQUEST_ID.fullmatch(entrant) else uuid.uuid4().hex
        jeton = request_id_var.set(request_id)
        debut = time.perf_counter()
        statut = 500
        id_header = [(b"x-request-id", request_id.encode())]

        async def envoyer(message: Message) -> None:
            nonlocal statut
            if message["type"] == "http.response.start":
                statut = message["status"]
                existants = {nom.lower() for nom, _ in message.get("headers", [])}
                est_pdf = dict(message.get("headers", [])).get(b"content-type") == _PDF_TYPE
                ajouts = [
                    (n, v)
                    for n, v in SECURITY_HEADERS
                    if n not in existants and not (est_pdf and n == b"content-security-policy")
                ]
                message["headers"] = [*message.get("headers", []), *ajouts, *id_header]
            await send(message)

        try:
            refus = self._controler(scope)
            if refus is not None:
                statut_refus, code, texte, en_tetes = refus
                statut = statut_refus
                await _json_response(statut_refus, code, texte, [*en_tetes, *id_header])(
                    envoyer_sans_corps_securite(send)
                )
                return
            await self._app(scope, receive, envoyer)
        finally:
            duree = (time.perf_counter() - debut) * 1000
            route = getattr(scope.get("route"), "path", None) or "unmatched"
            methode = scope.get("method", "GET")
            self._metrics.record(route, methode, statut, duree)
            logger.info(
                "request",
                extra={
                    "method": methode,
                    "route": route,
                    "status": statut,
                    "duration_ms": round(duree, 1),
                },
            )
            request_id_var.reset(jeton)

    def _controler(self, scope: Scope) -> tuple[int, str, str, list[tuple[bytes, bytes]]] | None:
        """Taille annoncée, puis débit : renvoie la réponse de refus ou `None`."""
        chemin: str = scope.get("path", "")
        longueur = dict(scope.get("headers", [])).get(b"content-length", b"")
        if longueur.isdigit() and int(longueur) > self._max_body:
            return 413, "payload_too_large", "La requête dépasse la taille maximale autorisée.", []
        client = scope.get("client")
        cle = client[0] if client else "inconnu"
        classes = [self._limiter]
        if chemin.startswith(EXPENSIVE_PREFIXES) and scope.get("method") != "GET":
            classes.append(self._expensive)
        for limiteur in classes:
            autorise, attente = limiteur.check(f"{cle}")
            if not autorise:
                self._metrics.rate_limited += 1
                return (
                    429,
                    "rate_limited",
                    "Trop de requêtes : réessayez dans quelques instants.",
                    [(b"retry-after", str(attente).encode())],
                )
        return None


def envoyer_sans_corps_securite(send: Send) -> Send:
    """Ajoute les en-têtes de sécurité aux réponses de refus produites par le middleware."""

    async def envoyer(message: Message) -> None:
        if message["type"] == "http.response.start":
            message["headers"] = [*message.get("headers", []), *SECURITY_HEADERS]
        await send(message)

    return envoyer
