"""Environnement Alembic : l'URL vient de HAPPLY_DATABASE_URL, les modèles du registre."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.core.config import get_settings
from app.core.database.registry import metadata
from app.core.database.session import to_driver_url

config = context.config
if config.config_file_name is not None:
    # Ne désactive pas les loggers de l'application (comportement par défaut d'Alembic).
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = metadata


def _url() -> str:
    database_url = get_settings().database_url
    if database_url is None:
        raise RuntimeError("HAPPLY_DATABASE_URL doit être défini pour exécuter les migrations.")
    return to_driver_url(database_url)


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
