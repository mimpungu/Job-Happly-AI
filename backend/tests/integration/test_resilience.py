"""Résilience : restauration réelle d'une sauvegarde et comportement quand la base tombe (EPIC 018).

Les interruptions de tâches (reprise après verrou expiré) et les pannes de fournisseurs (IA,
sources d'offres) sont couvertes par test_job_queue.py, test_ai_gateway.py,
test_collection.py et tests/unit/job_discovery/test_resilience.py.
"""

import os
import shutil
import subprocess
import uuid
from pathlib import Path

import httpx
import pytest
from alembic import command
from sqlalchemy import create_engine, make_url, text

from app.core.api.dependencies import get_session
from app.core.config import get_settings
from app.core.database.session import to_driver_url
from app.main import create_app
from app.modules.platform.infrastructure.health_checks import check_database
from tests.integration.conftest import configurer_alembic

PG_DUMP = shutil.which("pg_dump")
PG_RESTORE = shutil.which("pg_restore")
OUTILS = PG_DUMP and PG_RESTORE


def _env_pg(url: str) -> dict[str, str]:
    u = make_url(url)
    return {**os.environ, "PGPASSWORD": u.password or ""}


def _args_pg(url: str, base: str) -> list[str]:
    u = make_url(url)
    return ["-h", u.host or "127.0.0.1", "-p", str(u.port or 5432), "-U", u.username or "", base]


@pytest.mark.skipif(not OUTILS, reason="pg_dump / pg_restore indisponibles")
def test_une_sauvegarde_se_restaure_dans_une_base_distincte_avec_ses_donnees(
    database_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TASK-018-30 : sauvegarde → restauration vers une base temporaire → mêmes données."""
    suffixe = uuid.uuid4().hex[:8]
    source, cible = f"happly_bkp_src_{suffixe}_test", f"happly_bkp_dst_{suffixe}_test"
    racine = make_url(database_url)
    admin = create_engine(to_driver_url(database_url), isolation_level="AUTOCOMMIT")
    url_source = racine.set(database=source).render_as_string(hide_password=False)
    url_cible = racine.set(database=cible).render_as_string(hide_password=False)
    try:
        with admin.connect() as c:
            c.execute(text(f'CREATE DATABASE "{source}"'))
            c.execute(text(f'CREATE DATABASE "{cible}"'))
    except Exception:
        admin.dispose()
        pytest.skip("droit CREATE DATABASE indisponible")
    ancien = os.environ.get("HAPPLY_DATABASE_URL")
    try:
        command.upgrade(configurer_alembic(url_source), "head")
        moteur = create_engine(to_driver_url(url_source))
        with moteur.begin() as c:
            utilisateur = c.execute(
                text("INSERT INTO users (display_name) VALUES ('Sauvegardé') RETURNING id")
            ).scalar_one()
            c.execute(
                text(
                    "INSERT INTO job_offers (owner_id, title, description, application_url, "
                    "content_hash) VALUES (:o, 'Offre sauvegardée', 'd', 'https://x.test', :h)"
                ),
                {"o": utilisateur, "h": "h" * 64},
            )
        moteur.dispose()

        dump = tmp_path / "happly.dump"
        with dump.open("wb") as f:
            subprocess.run(  # noqa: S603 - outils PostgreSQL, arguments maîtrisés par le test
                [str(PG_DUMP), "-Fc", *_args_pg(url_source, source)],
                stdout=f,
                env=_env_pg(url_source),
                check=True,
            )
        assert dump.stat().st_size > 0

        subprocess.run(  # noqa: S603
            [
                str(PG_RESTORE),
                "--no-owner",
                "-d",
                cible,
                *_args_pg(url_cible, cible)[:-1],
                str(dump),
            ],
            env=_env_pg(url_cible),
            check=True,
        )

        moteur_cible = create_engine(to_driver_url(url_cible))
        with moteur_cible.connect() as c:
            offres = c.execute(text("SELECT title FROM job_offers")).scalars().all()
            revision = c.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        moteur_cible.dispose()
        assert offres == ["Offre sauvegardée"]
        assert revision  # le schéma restauré porte sa version de migration

        # Un fichier altéré est détecté : la restauration échoue au lieu d'écrire à moitié.
        altere = tmp_path / "altere.dump"
        altere.write_bytes(dump.read_bytes()[:200] + b"\x00corrompu" * 50)
        echec = subprocess.run(  # noqa: S603
            [str(PG_RESTORE), "--list", str(altere)], capture_output=True, env=os.environ
        )
        assert echec.returncode != 0
    finally:
        if ancien is None:
            os.environ.pop("HAPPLY_DATABASE_URL", None)
        else:
            os.environ["HAPPLY_DATABASE_URL"] = ancien
        get_settings.cache_clear()
        with admin.connect() as c:
            for base in (source, cible):
                c.execute(text(f'DROP DATABASE IF EXISTS "{base}" WITH (FORCE)'))
        admin.dispose()


class _SessionEnPanne:
    """Simule une base injoignable : toute requête échoue avec le DSN dans le message."""

    async def execute(self, *_: object, **__: object) -> None:
        raise ConnectionError("connexion refusée à postgresql://happly:motdepasse@10.0.0.9/db")

    async def scalar(self, *_: object, **__: object) -> None:
        raise ConnectionError("connexion refusée à postgresql://happly:motdepasse@10.0.0.9/db")


async def test_base_injoignable_la_sonde_signale_down_sans_fuiter_le_dsn() -> None:
    sante = await check_database(_SessionEnPanne())  # type: ignore[arg-type]

    assert sante.status.value == "down"
    assert "motdepasse" not in str(sante)


async def test_base_injoignable_pret_renvoie_503_et_vivacite_reste_ok() -> None:
    application = create_app()

    async def _en_panne():  # type: ignore[no-untyped-def]
        yield _SessionEnPanne()

    application.dependency_overrides[get_session] = _en_panne
    transport = httpx.ASGITransport(app=application, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as c:
        vivacite = await c.get("/api/v1/health")
        pret = await c.get("/api/v1/health/ready")

    assert vivacite.status_code == 200  # le processus tourne : pas de redémarrage inutile
    assert pret.status_code == 503
    corps = pret.json()
    assert corps["status"] == "down"
    assert "motdepasse" not in pret.text


async def test_sans_base_configuree_les_routes_metier_repondent_503_normalise() -> None:
    application = create_app()  # pas de lifespan : aucune fabrique de sessions
    transport = httpx.ASGITransport(app=application, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as c:
        reponse = await c.get("/api/v1/applications")

    assert reponse.status_code == 503
    assert "error" in reponse.json()
