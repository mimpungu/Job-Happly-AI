"""Cas d'usage : retrouver le site carrières public de l'entreprise tapée dans la recherche.

Quand l'utilisateur renseigne une entreprise, la recherche doit aller lire **ses** offres :
- si l'entreprise est déjà suivie, on la lit ;
- sinon on cherche son site carrières public (Greenhouse, Lever, Ashby, Workable) à partir du
  nom, et on ne la suit automatiquement que si le nom du site correspond bien à celui saisi ;
- en cas de doute (nom proche, plusieurs sites), on propose les candidats sans rien activer ;
- si rien n'est trouvé, on le dit : l'entreprise utilise peut-être un outil non pris en charge.

Aucun site n'est inventé : chaque candidat a répondu à l'API publique de l'ATS avec une structure
valide (voir `infrastructure/ats/discovery.py`).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

import httpx

from app.core.database.session import UnitOfWork
from app.modules.job_discovery.domain.text import normalize_text
from app.modules.job_discovery.infrastructure.ats.discovery import (
    FORMES_JURIDIQUES,
    DiscoveredBoard,
    discover_boards,
)
from app.modules.job_discovery.infrastructure.target_company_repository import (
    SqlTargetCompanyRepository,
    TargetCompanyError,
)

ClientFactory = Callable[[], AbstractAsyncContextManager[httpx.AsyncClient]]


class CompanyStatus(StrEnum):
    TRACKED = "tracked"
    """Déjà suivie : ses offres sont lues."""
    FOLLOWED = "followed"
    """Site carrières trouvé et correspondant au nom : suivie automatiquement."""
    CANDIDATES = "candidates"
    """Des sites existent mais le nom ne correspond pas assez : à confirmer par l'utilisateur."""
    NOT_FOUND = "not_found"
    DISABLED = "disabled"
    """Suivie mais désactivée par l'utilisateur : jamais réactivée sans son accord."""


@dataclass(frozen=True, slots=True)
class CompanyResolution:
    status: CompanyStatus
    query: str
    company_ids: frozenset[uuid.UUID] = frozenset()
    """Entreprises à lire pour cette recherche (vide si aucune)."""
    followed_name: str | None = None
    boards: tuple[DiscoveredBoard, ...] = field(default_factory=tuple)


def comparable_name(nom: str) -> str:
    """Nom sans casse, accents, ponctuation ni forme juridique : « Acme, Inc. » → « acme »."""
    mots = [m for m in normalize_text(nom).split() if m not in FORMES_JURIDIQUES]
    return " ".join(mots) or normalize_text(nom)


def _correspond(recherche: str, nom: str) -> bool:
    """Les deux noms désignent la même entreprise : égaux une fois normalisés, ou l'un est un
    groupe de mots entier de l'autre (« Stripe » ↔ « Stripe Payments »)."""
    a, b = comparable_name(recherche), comparable_name(nom)
    if not a or not b:
        return False
    return a == b or f" {a} " in f" {b} " or f" {b} " in f" {a} "


class CompanyResolver:
    def __init__(
        self,
        uow: UnitOfWork,
        client_factory: ClientFactory,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._uow = uow
        self._client_factory = client_factory
        self._clock = clock

    async def resolve(self, *, owner_id: uuid.UUID, company: str) -> CompanyResolution:
        async with self._uow.begin() as session:
            suivies = await SqlTargetCompanyRepository(session).list(owner_id)
        correspondantes = [e for e in suivies if _correspond(company, e.name)]
        actives = frozenset(e.id for e in correspondantes if e.enabled)
        if actives:
            return CompanyResolution(CompanyStatus.TRACKED, company, company_ids=actives)
        if correspondantes:
            return CompanyResolution(CompanyStatus.DISABLED, company)

        async with self._client_factory() as client:
            trouves = await discover_boards(company, client)
        if not trouves:
            return CompanyResolution(CompanyStatus.NOT_FOUND, company)
        sures = [
            b
            for b in trouves
            if b.offer_count > 0 and b.board_name and _correspond(company, b.board_name)
        ]
        if not sures:
            return CompanyResolution(CompanyStatus.CANDIDATES, company, boards=tuple(trouves))
        choisi = max(sures, key=lambda b: b.offer_count)
        identifiant = await self._suivre(owner_id, choisi)
        return CompanyResolution(
            CompanyStatus.FOLLOWED,
            company,
            company_ids=frozenset({identifiant}),
            followed_name=choisi.board_name,
            boards=tuple(trouves),
        )

    async def _suivre(self, owner_id: uuid.UUID, board: DiscoveredBoard) -> uuid.UUID:
        async with self._uow.begin() as session:
            depot = SqlTargetCompanyRepository(session)
            try:
                entreprise = await depot.add(
                    owner_id,
                    name=board.board_name or board.token,
                    careers_url=board.careers_url,
                    now=self._clock(),
                )
            except TargetCompanyError:
                # Déjà suivie sous un autre nom : on la retrouve par son site.
                entreprise = next(
                    e
                    for e in await depot.list(owner_id)
                    if e.careers_url == board.careers_url or e.ats_token == board.token
                )
            await depot.set_enabled(entreprise, True)
            return entreprise.id
