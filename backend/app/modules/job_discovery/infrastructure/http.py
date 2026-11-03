"""Accès HTTP sortant contrôlé : en-têtes honnêtes, taille bornée, erreurs typées, SSRF."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.modules.job_discovery.domain.connector import (
    AccessDeniedError,
    InvalidResponseError,
    NotConfiguredError,
    RateLimitedError,
    SourceTimeoutError,
    SourceUnavailableError,
)

# User-Agent honnête : il dit qui est le client, sans coordonnées personnelles.
USER_AGENT = "HapplyAI/0.1 (assistant personnel de recherche d'emploi; lecture de pages publiques)"
MAX_RESPONSE_BYTES = 5 * 1024 * 1024

Resolver = Callable[[str], Awaitable[list[str]]]


def create_http_client(
    *, timeout: float = 15.0, transport: httpx.AsyncBaseTransport | None = None
) -> httpx.AsyncClient:
    """Client sans redirection automatique (une redirection est une décision à valider)."""
    return httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=False,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json, text/html;q=0.8"},
        transport=transport,
    )


def _retry_after(response: httpx.Response) -> float | None:
    brut = response.headers.get("Retry-After")
    try:
        return max(0.0, float(brut)) if brut is not None else None
    except ValueError:
        return None


def raise_for_status(
    response: httpx.Response, *, source_key: str, not_found_is_error: bool = True
) -> None:
    """Traduit un statut HTTP en erreur de connecteur. Aucun contournement d'un refus."""
    code = response.status_code
    if code < 400:
        if 300 <= code < 400:
            raise InvalidResponseError(
                f"Redirection non suivie (HTTP {code}).", source_key=source_key
            )
        return
    if code == 404 and not_found_is_error:
        raise NotConfiguredError("Ressource introuvable (HTTP 404).", source_key=source_key)
    if code in (401, 403):
        raise AccessDeniedError(f"Accès refusé (HTTP {code}).", source_key=source_key)
    if code == 429:
        raise RateLimitedError(
            "Quota atteint (HTTP 429).", retry_after=_retry_after(response), source_key=source_key
        )
    if code >= 500:
        raise SourceUnavailableError(f"Source indisponible (HTTP {code}).", source_key=source_key)
    raise InvalidResponseError(f"Réponse inattendue (HTTP {code}).", source_key=source_key)


async def fetch(
    client: httpx.AsyncClient,
    url: str,
    *,
    source_key: str,
    params: dict[str, str] | None = None,
    max_bytes: int = MAX_RESPONSE_BYTES,
) -> httpx.Response:
    """GET avec taille de réponse bornée et traduction des erreurs réseau."""
    try:
        async with client.stream("GET", url, params=params) as flux:
            contenu = bytearray()
            async for morceau in flux.aiter_bytes():
                contenu.extend(morceau)
                if len(contenu) > max_bytes:
                    raise InvalidResponseError("Réponse trop volumineuse.", source_key=source_key)
            return httpx.Response(
                status_code=flux.status_code,
                headers=flux.headers,
                content=bytes(contenu),
                request=flux.request,
            )
    except httpx.TimeoutException as erreur:
        raise SourceTimeoutError("Délai réseau dépassé.", source_key=source_key) from erreur
    except httpx.TransportError as erreur:
        raise SourceUnavailableError("Erreur réseau.", source_key=source_key) from erreur


async def get_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    source_key: str,
    params: dict[str, str] | None = None,
    not_found_is_error: bool = True,
) -> Any | None:
    """GET JSON ; retourne `None` sur un 404 si `not_found_is_error` est faux."""
    reponse = await fetch(client, url, source_key=source_key, params=params)
    if reponse.status_code == 404 and not not_found_is_error:
        return None
    raise_for_status(reponse, source_key=source_key)
    try:
        return reponse.json()
    except ValueError as erreur:
        raise InvalidResponseError("JSON invalide.", source_key=source_key) from erreur


# ------------------------------------------------------------------ SSRF


class UnsafeUrlError(AccessDeniedError):
    """URL refusée par la protection SSRF (schéma, identifiants, adresse non publique)."""


async def _resolve(host: str) -> list[str]:
    infos = await asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM)
    return [str(info[4][0]) for info in infos]


def _is_public(adresse: str) -> bool:
    try:
        ip = ipaddress.ip_address(adresse.split("%")[0])
    except ValueError:
        return False
    return ip.is_global and not ip.is_multicast


async def ensure_public_url(url: str, *, resolver: Resolver = _resolve) -> str:
    """Refuse toute URL pouvant viser le réseau interne (SSRF).

    Contrôles : HTTPS uniquement, pas d'identifiants dans l'URL, hôte présent, et **toutes** les
    adresses résolues sont publiques. Limite connue : entre la résolution et la connexion, le DNS
    peut changer (rebinding) ; les redirections ne sont jamais suivies automatiquement.
    """
    morceaux = urlsplit(url)
    if morceaux.scheme != "https":
        raise UnsafeUrlError("Seul HTTPS est autorisé.")
    if morceaux.username or morceaux.password:
        raise UnsafeUrlError("Identifiants dans l'URL interdits.")
    hote = morceaux.hostname
    if not hote:
        raise UnsafeUrlError("Hôte absent.")
    try:
        adresses = [str(ipaddress.ip_address(hote))]
    except ValueError:
        try:
            adresses = await resolver(hote)
        except OSError as erreur:
            raise UnsafeUrlError("Hôte non résolu.") from erreur
    if not adresses or not all(_is_public(a) for a in adresses):
        raise UnsafeUrlError("L'hôte ne résout pas vers une adresse publique.")
    return url
