"""Lecture de pages publiques, uniquement lorsque les règles du site l'autorisent (ADR-0006).

Ce module ne contourne rien : `robots.txt` est respecté, un refus (401, 403, CAPTCHA, défi
anti-bot) arrête immédiatement et la source est considérée « non supportée ». Les conditions
d'utilisation d'un site ne sont pas lisibles par une machine : elles doivent être vérifiées par
une personne avant d'activer la lecture (`tos_verified_at` d'une entreprise ciblée).
"""

from __future__ import annotations

from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from app.modules.job_discovery.domain.connector import (
    AccessDeniedError,
    InvalidResponseError,
    SourceUnavailableError,
)
from app.modules.job_discovery.infrastructure.http import (
    Resolver,
    _resolve,
    ensure_public_url,
    fetch,
    raise_for_status,
)

ROBOTS_USER_AGENT = "HapplyAI"
MAX_REDIRECTIONS = 3
_INDICES_DE_DEFI = (
    "captcha",
    "cf-challenge",
    "just a moment...",
    "verify you are human",
    "access denied",
    "unusual traffic",
)


class _Robots:
    def __init__(self, parseur: RobotFileParser | None, *, tout_interdit: bool = False) -> None:
        self._parseur = parseur
        self._tout_interdit = tout_interdit

    def autorise(self, url: str) -> bool:
        if self._tout_interdit:
            return False
        return True if self._parseur is None else self._parseur.can_fetch(ROBOTS_USER_AGENT, url)


class PublicPageFetcher:
    """Récupère le HTML d'une page publique après contrôles SSRF et robots.txt."""

    def __init__(self, client: httpx.AsyncClient, *, resolver: Resolver = _resolve) -> None:
        self._client = client
        self._resolver = resolver
        self._robots: dict[str, _Robots] = {}

    async def fetch_html(self, url: str, *, source_key: str) -> str:
        courante = url
        for _ in range(MAX_REDIRECTIONS + 1):
            await ensure_public_url(courante, resolver=self._resolver)
            if not (await self._regles(courante, source_key)).autorise(courante):
                raise AccessDeniedError("Lecture interdite par robots.txt.", source_key=source_key)
            reponse = await fetch(self._client, courante, source_key=source_key)
            if reponse.status_code in (301, 302, 303, 307, 308):
                courante = self._suivre(courante, reponse, source_key)
                continue
            raise_for_status(reponse, source_key=source_key)
            type_contenu = reponse.headers.get("Content-Type", "").lower()
            if "html" not in type_contenu:
                raise InvalidResponseError("La page n'est pas du HTML.", source_key=source_key)
            texte = reponse.text
            self._refuser_si_defi(texte, source_key)
            return texte
        raise InvalidResponseError("Trop de redirections.", source_key=source_key)

    @staticmethod
    def _suivre(url: str, reponse: httpx.Response, source_key: str) -> str:
        destination = reponse.headers.get("Location")
        if not destination:
            raise InvalidResponseError("Redirection sans destination.", source_key=source_key)
        cible = str(urljoin(url, destination))
        # Une redirection vers un autre hôte est une décision à valider : on s'arrête.
        if urlsplit(cible).hostname != urlsplit(url).hostname:
            raise AccessDeniedError(
                "Redirection vers un autre hôte refusée.", source_key=source_key
            )
        return cible

    @staticmethod
    def _refuser_si_defi(texte: str, source_key: str) -> None:
        extrait = texte[:20000].lower()
        if any(indice in extrait for indice in _INDICES_DE_DEFI):
            raise AccessDeniedError(
                "La page demande une vérification anti-robot : accès non contourné.",
                source_key=source_key,
            )

    async def _regles(self, url: str, source_key: str) -> _Robots:
        morceaux = urlsplit(url)
        origine = f"{morceaux.scheme}://{morceaux.netloc}"
        if origine in self._robots:
            return self._robots[origine]
        reponse = await fetch(self._client, f"{origine}/robots.txt", source_key=source_key)
        code = reponse.status_code
        if code == 404:  # aucun fichier : aucune restriction déclarée
            regles = _Robots(None)
        elif code in (401, 403) or code >= 500:
            # Prudence : un robots.txt inaccessible n'est pas une autorisation.
            regles = _Robots(None, tout_interdit=True)
        elif 200 <= code < 300:
            parseur = RobotFileParser()
            parseur.parse(reponse.text.splitlines())
            regles = _Robots(parseur)
        else:
            raise SourceUnavailableError(
                f"robots.txt illisible (HTTP {code}).", source_key=source_key
            )
        self._robots[origine] = regles
        return regles
