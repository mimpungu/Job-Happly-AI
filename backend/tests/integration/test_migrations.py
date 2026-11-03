import os

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from app.core.database.registry import metadata
from app.core.database.session import to_driver_url

from .conftest import configurer_alembic


def test_les_migrations_creent_toutes_les_tables_du_modele(schema_migre: str) -> None:
    engine = create_engine(to_driver_url(schema_migre))
    try:
        tables = set(inspect(engine).get_table_names()) - {"alembic_version"}
    finally:
        engine.dispose()

    assert tables == set(metadata.tables)


def test_le_schema_migre_correspond_exactement_aux_modeles(schema_migre: str) -> None:
    engine = create_engine(to_driver_url(schema_migre))
    try:
        with engine.connect() as connexion:
            contexte = MigrationContext.configure(
                connexion, opts={"compare_type": True, "compare_server_default": True}
            )
            differences = compare_metadata(contexte, metadata)
    finally:
        engine.dispose()

    assert differences == []


def test_les_migrations_sont_reversibles_et_rejouables(database_url: str) -> None:
    config = configurer_alembic(database_url)

    command.downgrade(config, "base")
    engine = create_engine(to_driver_url(database_url))
    try:
        assert set(inspect(engine).get_table_names()) <= {"alembic_version"}
    finally:
        engine.dispose()
    command.upgrade(config, "head")
    command.upgrade(config, "head")  # idempotent : rien à appliquer la seconde fois

    assert os.environ["HAPPLY_DATABASE_URL"] == database_url


def test_un_seul_point_d_entree_de_migration() -> None:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    from .conftest import RACINE_BACKEND

    script = ScriptDirectory.from_config(Config(str(RACINE_BACKEND / "alembic.ini")))

    assert len(script.get_heads()) == 1


@pytest.mark.parametrize("table", ["job_offers", "applications", "ai_usages"])
def test_les_tables_metier_ont_un_proprietaire(schema_migre: str, table: str) -> None:
    engine = create_engine(to_driver_url(schema_migre))
    try:
        colonnes = {c["name"]: c for c in inspect(engine).get_columns(table)}
    finally:
        engine.dispose()

    assert "owner_id" in colonnes
    assert colonnes["owner_id"]["nullable"] is False
