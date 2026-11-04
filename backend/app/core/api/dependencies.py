"""Dépendances FastAPI : session transactionnelle par requête et contexte utilisateur.

Sans authentification (ADR-0008), le « contexte utilisateur » est l'unique utilisateur local.
Les routes ne manipulent que `owner_id` : brancher une vraie authentification ne changera que
`get_owner_id`.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database.session import UnitOfWork
from app.modules.platform.infrastructure.models import UserModel


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Une transaction par requête : validée si la route réussit, annulée sinon."""
    fabrique: async_sessionmaker[AsyncSession] | None = getattr(
        request.app.state, "session_factory", None
    )
    if fabrique is None:
        raise HTTPException(status_code=503, detail="Base de données non configurée.")
    async with fabrique() as session, session.begin():
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_owner_id(session: SessionDep) -> uuid.UUID:
    """Utilisateur local : créé à la première utilisation, jamais dupliqué."""
    existant = await session.scalar(select(UserModel.id).order_by(UserModel.created_at).limit(1))
    if existant is not None:
        return existant
    utilisateur = UserModel(display_name="Utilisateur local")
    session.add(utilisateur)
    await session.flush()
    return utilisateur.id


def get_unit_of_work(request: Request) -> UnitOfWork:
    """Pour les traitements longs qui gèrent leurs propres transactions (collecte d'offres)."""
    fabrique: async_sessionmaker[AsyncSession] | None = getattr(
        request.app.state, "session_factory", None
    )
    if fabrique is None:
        raise HTTPException(status_code=503, detail="Base de données non configurée.")
    return UnitOfWork(fabrique)


UnitOfWorkDep = Annotated[UnitOfWork, Depends(get_unit_of_work)]
