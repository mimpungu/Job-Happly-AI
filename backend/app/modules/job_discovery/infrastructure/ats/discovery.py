"""Découverte du job board public d'une entreprise à partir de son nom.

Aucune liste fermée d'entreprises : on déduit des jetons plausibles du nom saisi, puis on vérifie
auprès des API publiques de lecture (Greenhouse, Lever, Ashby, Workable) qu'ils existent
réellement. Rien n'est inventé : un jeton n'est proposé que si la source a répondu avec une
structure valide.

Limite assumée : deux entreprises peuvent partager un jeton. Le résultat est donc proposé à
l'utilisateur (nom du board, nombre d'offres) avant tout suivi ; il n'est jamais activé seul.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass

import httpx

from app.modules.job_discovery.domain.connector import ConnectorError
from app.modules.job_discovery.domain.target_company import AtsKind
from app.modules.job_discovery.infrastructure.ats.ashby import BASE_URL as ASHBY_URL
from app.modules.job_discovery.infrastructure.ats.greenhouse import BASE_URL as GREENHOUSE_URL
from app.modules.job_discovery.infrastructure.ats.lever import BASE_URLS as LEVER_URLS
from app.modules.job_discovery.infrastructure.ats.workable import BASE_URL as WORKABLE_URL
from app.modules.job_discovery.infrastructure.http import get_json

logger = logging.getLogger("happly.discovery")

MAX_NAME_LENGTH = 100
MAX_CANDIDATES = 3

# Formes juridiques sans valeur d'identification : « Acme Inc. » → « acme ».
FORMES_JURIDIQUES = frozenset(
    {"inc", "incorporated", "llc", "ltd", "limited", "gmbh", "sa", "sas", "sarl", "corp", "co"}
)


@dataclass(frozen=True, slots=True)
class DiscoveredBoard:
    ats_kind: AtsKind
    token: str
    region: str | None
    careers_url: str
    board_name: str | None
    offer_count: int


def slug_candidates(name: str) -> list[str]:
    """Jetons plausibles dérivés du nom, du plus probable au moins probable (sans doublon)."""
    sans_accents = "".join(
        c for c in unicodedata.normalize("NFD", name.casefold()) if not unicodedata.combining(c)
    )
    mots = [m for m in re.split(r"[^a-z0-9]+", sans_accents) if m]
    significatifs = [m for m in mots if m not in FORMES_JURIDIQUES] or mots
    if not significatifs:
        return []
    candidats = ["".join(significatifs), "-".join(significatifs)]
    uniques = list(dict.fromkeys(candidats))
    return uniques[:MAX_CANDIDATES]


async def discover_boards(name: str, client: httpx.AsyncClient) -> list[DiscoveredBoard]:
    """Boards publics trouvés pour ce nom ; liste vide si aucun n'existe (ou si les sources
    sont indisponibles : une panne n'est jamais présentée comme « entreprise sans board »)."""
    texte = name.strip()[:MAX_NAME_LENGTH]
    trouves: list[DiscoveredBoard] = []
    for jeton in slug_candidates(texte):
        for sonde in (
            _sonder_greenhouse,
            _sonder_lever_global,
            _sonder_lever_eu,
            _sonder_ashby,
            _sonder_workable,
        ):
            try:
                board = await sonde(jeton, client)
            except ConnectorError as erreur:
                logger.info(
                    "Sonde de découverte en échec",
                    extra={"error_type": type(erreur).__name__, "token": jeton},
                )
                continue
            if board is not None:
                trouves.append(board)
    return trouves


async def _sonder_greenhouse(jeton: str, client: httpx.AsyncClient) -> DiscoveredBoard | None:
    cle = f"greenhouse:{jeton}"
    racine = await get_json(
        client, f"{GREENHOUSE_URL}/{jeton}", source_key=cle, not_found_is_error=False
    )
    if not isinstance(racine, dict):
        return None
    offres = await get_json(
        client, f"{GREENHOUSE_URL}/{jeton}/jobs", source_key=cle, not_found_is_error=False
    )
    liste = offres.get("jobs") if isinstance(offres, dict) else None
    if not isinstance(liste, list):
        return None
    nom = racine.get("name")
    return DiscoveredBoard(
        ats_kind=AtsKind.GREENHOUSE,
        token=jeton,
        region=None,
        careers_url=f"https://boards.greenhouse.io/{jeton}",
        board_name=nom.strip() if isinstance(nom, str) and nom.strip() else None,
        offer_count=len(liste),
    )


async def _sonder_lever(
    jeton: str, client: httpx.AsyncClient, *, region: str, hote: str
) -> DiscoveredBoard | None:
    donnees = await get_json(
        client,
        f"{LEVER_URLS[region]}/{jeton}",
        source_key=f"lever:{jeton}",
        params={"mode": "json"},
        not_found_is_error=False,
    )
    if not isinstance(donnees, list):
        return None
    return DiscoveredBoard(
        ats_kind=AtsKind.LEVER,
        token=jeton,
        region=None if region == "global" else region,
        careers_url=f"https://{hote}/{jeton}",
        board_name=None,
        offer_count=len(donnees),
    )


async def _sonder_lever_global(jeton: str, client: httpx.AsyncClient) -> DiscoveredBoard | None:
    return await _sonder_lever(jeton, client, region="global", hote="jobs.lever.co")


async def _sonder_lever_eu(jeton: str, client: httpx.AsyncClient) -> DiscoveredBoard | None:
    return await _sonder_lever(jeton, client, region="eu", hote="jobs.eu.lever.co")


async def _sonder_ashby(jeton: str, client: httpx.AsyncClient) -> DiscoveredBoard | None:
    donnees = await get_json(
        client,
        f"{ASHBY_URL}/{jeton}",
        source_key=f"ashby:{jeton}",
        params={"includeCompensation": "false"},
        not_found_is_error=False,
    )
    liste = donnees.get("jobs") if isinstance(donnees, dict) else None
    if not isinstance(liste, list):
        return None
    return DiscoveredBoard(
        ats_kind=AtsKind.ASHBY,
        token=jeton,
        region=None,
        careers_url=f"https://jobs.ashbyhq.com/{jeton}",
        board_name=None,
        # Les offres non listées ne sont pas publiées : elles ne comptent pas.
        offer_count=sum(
            1 for j in liste if not (isinstance(j, dict) and j.get("isListed") is False)
        ),
    )


async def _sonder_workable(jeton: str, client: httpx.AsyncClient) -> DiscoveredBoard | None:
    donnees = await get_json(
        client,
        f"{WORKABLE_URL}/{jeton}",
        source_key=f"workable:{jeton}",
        params={"details": "false"},
        not_found_is_error=False,
    )
    liste = donnees.get("jobs") if isinstance(donnees, dict) else None
    if not isinstance(donnees, dict) or not isinstance(liste, list):
        return None
    nom = donnees.get("name")
    return DiscoveredBoard(
        ats_kind=AtsKind.WORKABLE,
        token=jeton,
        region=None,
        careers_url=f"https://apply.workable.com/{jeton}",
        board_name=nom.strip() if isinstance(nom, str) and nom.strip() else None,
        offer_count=len(liste),
    )
