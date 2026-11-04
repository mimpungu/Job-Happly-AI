"""Moteur, sessions et unité de travail (transactions explicites)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from pydantic import SecretStr
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def to_driver_url(database_url: SecretStr | str) -> str:
    """Convertit `postgresql://…` en URL SQLAlchemy utilisant le pilote psycopg 3."""
    brut = database_url.get_secret_value() if isinstance(database_url, SecretStr) else database_url
    url = make_url(brut)
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
    return url.render_as_string(hide_password=False)


def create_engine(database_url: SecretStr | str) -> AsyncEngine:
    return create_async_engine(to_driver_url(database_url), pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


class UnitOfWork:
    """Délimite une transaction : validation si le bloc réussit, annulation sinon.

    Les use cases ouvrent une unité de travail ; les repositories reçoivent la session et
    ne valident jamais eux-mêmes.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    @asynccontextmanager
    async def begin(self) -> AsyncIterator[AsyncSession]:
        async with self._session_factory() as session, session.begin():
            yield session
