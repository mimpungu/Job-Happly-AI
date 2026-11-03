"""Fixtures d'intégration : PostgreSQL réel dédié aux tests.

Les tests s'exécutent uniquement si HAPPLY_TEST_DATABASE_URL est défini et pointe vers une base
dont le nom finit par `_test` : une base de développement ne doit jamais être effacée.
"""

import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import make_url, pool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.api.dependencies import get_session, get_unit_of_work
from app.core.config import get_settings
from app.core.database.session import UnitOfWork, to_driver_url
from app.main import create_app
from app.modules.platform.infrastructure.models import UserModel

RACINE_BACKEND = Path(__file__).resolve().parents[2]


def _url_de_test() -> str:
    url = os.environ.get("HAPPLY_TEST_DATABASE_URL")
    if not url:
        pytest.skip(
            "HAPPLY_TEST_DATABASE_URL non défini : tests d'intégration PostgreSQL non exécutés "
            "(lancer infrastructure/scripts/test.sh)."
        )
    if not (make_url(url).database or "").endswith("_test"):
        pytest.fail("Par sécurité, la base de test doit avoir un nom finissant par '_test'.")
    return url


@pytest.fixture(scope="session")
def database_url() -> str:
    return _url_de_test()


def configurer_alembic(database_url: str, monkeypatch: pytest.MonkeyPatch | None = None) -> Config:
    os.environ["HAPPLY_DATABASE_URL"] = database_url
    get_settings.cache_clear()
    return Config(str(RACINE_BACKEND / "alembic.ini"))


@pytest.fixture(scope="session")
def schema_migre(database_url: str) -> str:
    """Repart d'une base vide, applique toutes les migrations."""
    config = configurer_alembic(database_url)
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    return database_url


@pytest.fixture
async def session(schema_migre: str) -> AsyncIterator[AsyncSession]:
    """Session isolée : tout est annulé à la fin du test (aucune donnée résiduelle)."""
    engine = create_async_engine(to_driver_url(schema_migre), poolclass=pool.NullPool)
    async with engine.connect() as connexion:
        transaction = await connexion.begin()
        async with AsyncSession(
            bind=connexion, expire_on_commit=False, join_transaction_mode="create_savepoint"
        ) as session:
            yield session
        await transaction.rollback()
    await engine.dispose()


@pytest.fixture
async def user_id(session: AsyncSession) -> uuid.UUID:
    utilisateur = UserModel(display_name="Local")
    session.add(utilisateur)
    await session.flush()
    return utilisateur.id


class SessionPartagee(UnitOfWork):
    """Unité de travail de TEST : réutilise la session du test (annulée à la fin du test)."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(async_sessionmaker())
        self._session = session

    @asynccontextmanager
    async def begin(self) -> AsyncIterator[AsyncSession]:
        async with self._session.begin_nested():
            yield self._session


@pytest.fixture
async def client(session: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    application = create_app()
    application.dependency_overrides[get_unit_of_work] = lambda: SessionPartagee(session)

    async def _session_de_test() -> AsyncIterator[AsyncSession]:
        yield session

    application.dependency_overrides[get_session] = _session_de_test
    transport = httpx.ASGITransport(app=application, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as c:
        yield c
