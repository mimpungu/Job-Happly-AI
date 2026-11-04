"""Lecture de pages publiques, uniquement lorsque les règles du site l'autorisent (ADR-0006).

Ce module ne contourne rien : `robots.txt` est respecté, un refus (401, 403, CAPTCHA, défi
anti-bot) arrête immédiatement et la source est considérée « non supportée ». Les conditions
d'utilisation d'un site ne sont pas lisibles par une machine : elles doivent être vérifiées par
une personne avant d'activer la lecture (`tos_verified_at` d'une entreprise ciblée).
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
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
# Débit (TASK-006-25) : au plus une requête par seconde et par hôte, davantage si le site le
# demande (`Crawl-delay`). Un délai exigé trop long vaut refus : source « non supportée ».
MIN_INTERVAL_SECONDS = 1.0
MAX_CRAWL_DELAY_SECONDS = 30.0
# Cache : une page déjà lue n'est pas redemandée avant ce délai, ce qui évite de solliciter
# le site pour rien lors de recherches répétées.
CACHE_TTL_SECONDS = 900.0
CACHE_MAX_ENTRIES = 256

Clock = Callable[[], float]
Sleep = Callable[[float], Awaitable[None]]
_INDICES_DE_DEFI = (
    "captcha",
    "cf-challenge",
    "just a moment...",
    "verify you are human",
    "access denied",
    "unusual traffic",
)


def _origine(url: str) -> str:
    morceaux = urlsplit(url)
    return f"{morceaux.scheme}://{morceaux.netloc}"


class _Robots:
    def __init__(self, parseur: RobotFileParser | None, *, tout_interdit: bool = False) -> None:
        self._parseur = parseur
        self._tout_interdit = tout_interdit

    def autorise(self, url: str) -> bool:
        if self._tout_interdit:
            return False
        return True if self._parseur is None else self._parseur.can_fetch(ROBOTS_USER_AGENT, url)


class PageCache:
    """Cache mémoire borné des pages lues, avec expiration. Seules les pages réussies y entrent :
    un refus, un défi anti-robot ou une erreur ne sont jamais mémorisés comme des réponses."""

    def __init__(
        self,
        *,
        ttl: float = CACHE_TTL_SECONDS,
        max_entries: int = CACHE_MAX_ENTRIES,
        clock: Clock = time.monotonic,
    ) -> None:
        self._ttl = ttl
        self._max = max_entries
        self._clock = clock
        self._entrees: dict[str, tuple[float, str]] = {}

    def get(self, url: str) -> str | None:
        trouvee = self._entrees.get(url)
        if trouvee is None:
            return None
        if self._clock() >= trouvee[0]:
            del self._entrees[url]
            return None
        return trouvee[1]

    def put(self, url: str, html: str) -> None:
        if len(self._entrees) >= self._max and url not in self._entrees:
            # Éviction de la plus ancienne (ordre d'insertion du dictionnaire).
            self._entrees.pop(next(iter(self._entrees)))
        self._entrees[url] = (self._clock() + self._ttl, html)


class PublicPageFetcher:
    """Récupère le HTML d'une page publique après contrôles SSRF et robots.txt, à débit limité."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        resolver: Resolver = _resolve,
        cache: PageCache | None = None,
        clock: Clock = time.monotonic,
        sleep: Sleep = asyncio.sleep,
        min_interval: float = MIN_INTERVAL_SECONDS,
    ) -> None:
        self._client = client
        self._resolver = resolver
        self._robots: dict[str, _Robots] = {}
        self._cache = cache if cache is not None else PageCache(clock=clock)
        self._clock = clock
        self._sleep = sleep
        self._min_interval = min_interval
        self._delais: dict[str, float] = {}
        self._derniere: dict[str, float] = {}
        self._verrous: dict[str, asyncio.Lock] = {}

    async def _patienter(self, url: str) -> None:
        """Espace les requêtes vers un même hôte : une seule à la fois, au débit autorisé."""
        origine = _origine(url)
        verrou = self._verrous.setdefault(origine, asyncio.Lock())
        async with verrou:
            attente = self._delais.get(origine, self._min_interval) - (
                self._clock() - self._derniere.get(origine, float("-inf"))
            )
            if attente > 0:
                await self._sleep(attente)
            self._derniere[origine] = self._clock()

    async def fetch_html(self, url: str, *, source_key: str) -> str:
        en_cache = self._cache.get(url)
        if en_cache is not None:
            return en_cache
        courante = url
        for _ in range(MAX_REDIRECTIONS + 1):
            await ensure_public_url(courante, resolver=self._resolver)
            if not (await self._regles(courante, source_key)).autorise(courante):
                raise AccessDeniedError("Lecture interdite par robots.txt.", source_key=source_key)
            await self._patienter(courante)
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
            self._cache.put(url, texte)
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
        origine = _origine(url)
        if origine in self._robots:
            return self._robots[origine]
        await self._patienter(f"{origine}/robots.txt")
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
            exige = parseur.crawl_delay(ROBOTS_USER_AGENT)
            if exige is not None:
                if float(exige) > MAX_CRAWL_DELAY_SECONDS:
                    raise AccessDeniedError(
                        "Le site exige un délai entre requêtes trop long : source non supportée.",
                        source_key=source_key,
                    )
                self._delais[origine] = max(self._min_interval, float(exige))
        else:
            raise SourceUnavailableError(
                f"robots.txt illisible (HTTP {code}).", source_key=source_key
            )
        self._robots[origine] = regles
        return regles
