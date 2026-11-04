"""Sondes de santé concrètes : base, stockage, LaTeX, IA, sources, tâches planifiées.

Les messages sont courts et sans détail technique : une exception de pilote peut contenir l'URL de
connexion, donc jamais `str(erreur)` brut dans une réponse de santé.
"""

from __future__ import annotations

import os
import shutil
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.observability.redaction import redact
from app.modules.ai_management.application.providers import build_providers
from app.modules.job_discovery.infrastructure.models import JobSourceModel
from app.modules.notifications.infrastructure.models import ScheduledTaskModel
from app.modules.platform.domain.health import ComponentHealth, Status
from app.modules.platform.infrastructure.models import JobModel, JobStatus

_TASK_OVERDUE = timedelta(minutes=15)
_JOB_STALE = timedelta(minutes=30)
_STANDARD_PATHS = ("/usr/bin/pdflatex", "/Library/TeX/texbin/pdflatex", "/usr/local/bin/pdflatex")


async def check_database(session: AsyncSession) -> ComponentHealth:
    debut = time.perf_counter()
    try:
        await session.execute(text("SELECT 1"))
        revision = await session.scalar(text("SELECT version_num FROM alembic_version LIMIT 1"))
    except Exception:
        return ComponentHealth("database", Status.DOWN, "Base de données injoignable.")
    latence = round((time.perf_counter() - debut) * 1000, 1)
    return ComponentHealth(
        "database", Status.OK, data={"latency_ms": latence, "migration_revision": revision}
    )


def check_storage(settings: Settings) -> ComponentHealth:
    dossier = Path(settings.storage_dir) / "documents"
    try:
        dossier.mkdir(parents=True, exist_ok=True)
        ecriture = os.access(dossier, os.W_OK)
        libre_mo = shutil.disk_usage(dossier).free // (1024 * 1024)
    except OSError:
        return ComponentHealth("storage", Status.DOWN, "Stockage des documents inaccessible.")
    if not ecriture:
        return ComponentHealth("storage", Status.DOWN, "Stockage des documents en lecture seule.")
    if libre_mo < 200:
        return ComponentHealth(
            "storage", Status.DEGRADED, "Espace disque faible.", {"free_mb": libre_mo}
        )
    return ComponentHealth("storage", Status.OK, data={"free_mb": libre_mo})


def check_latex(settings: Settings) -> ComponentHealth:
    candidats = [settings.pdflatex_path, shutil.which("pdflatex"), *_STANDARD_PATHS]
    if any(c and os.path.isfile(c) and os.access(c, os.X_OK) for c in candidats):
        return ComponentHealth("latex", Status.OK)
    return ComponentHealth(
        "latex",
        Status.DEGRADED,
        "pdfLaTeX introuvable : la génération et la compilation de PDF sont indisponibles.",
    )


def check_ai(settings: Settings) -> ComponentHealth:
    fournisseurs = build_providers(settings)
    if not fournisseurs:
        return ComponentHealth(
            "ai",
            Status.NOT_CONFIGURED,
            "Aucun fournisseur IA configuré : l'application fonctionne sans IA.",
        )
    return ComponentHealth(
        "ai",
        Status.OK,
        data={"providers": [{"name": f.name, "kind": f.kind.value} for f in fournisseurs]},
    )


async def check_sources(session: AsyncSession) -> ComponentHealth:
    lignes = (await session.scalars(select(JobSourceModel).where(JobSourceModel.enabled))).all()
    if not lignes:
        return ComponentHealth("sources", Status.NOT_CONFIGURED, "Aucune source activée.")
    en_erreur = [s for s in lignes if s.last_error]
    detail = [
        {
            "key": s.key,
            "last_success_at": s.last_success_at.isoformat() if s.last_success_at else None,
            "last_error": redact(s.last_error)[:200] if s.last_error else None,
        }
        for s in lignes
    ]
    if en_erreur:
        # Une source indisponible n'arrête jamais les autres (spec §10) : dégradé, pas en panne.
        return ComponentHealth(
            "sources",
            Status.DEGRADED,
            f"{len(en_erreur)} source(s) en erreur sur {len(lignes)}.",
            {"enabled": len(lignes), "sources": detail},
        )
    return ComponentHealth("sources", Status.OK, data={"enabled": len(lignes), "sources": detail})


async def check_tasks(session: AsyncSession, *, now: datetime | None = None) -> ComponentHealth:
    """Monitoring des tâches planifiées et de la file de tâches de fond (TASK-018-28)."""
    maintenant = now or datetime.now(UTC)
    actives = await session.scalar(
        select(func.count()).select_from(ScheduledTaskModel).where(ScheduledTaskModel.enabled)
    )
    en_retard = await session.scalar(
        select(func.count())
        .select_from(ScheduledTaskModel)
        .where(
            ScheduledTaskModel.enabled,
            ScheduledTaskModel.next_run_at < maintenant - _TASK_OVERDUE,
        )
    )
    par_statut = dict(
        (
            await session.execute(select(JobModel.status, func.count()).group_by(JobModel.status))
        ).all()
    )
    bloquees = await session.scalar(
        select(func.count())
        .select_from(JobModel)
        .where(
            JobModel.status == JobStatus.RUNNING.value,
            JobModel.locked_at < maintenant - _JOB_STALE,
        )
    )
    mortes = par_statut.get(JobStatus.DEAD.value, 0)
    data = {
        "scheduled_enabled": actives or 0,
        "scheduled_overdue": en_retard or 0,
        "jobs": {statut: par_statut.get(statut, 0) for statut in (s.value for s in JobStatus)},
        "jobs_stale_running": bloquees or 0,
    }
    problemes = []
    if en_retard:
        problemes.append(f"{en_retard} tâche(s) planifiée(s) en retard")
    if bloquees:
        problemes.append(f"{bloquees} tâche(s) de fond bloquée(s)")
    if mortes:
        problemes.append(f"{mortes} tâche(s) de fond abandonnée(s) après échecs répétés")
    if problemes:
        return ComponentHealth("tasks", Status.DEGRADED, " ; ".join(problemes), data)
    return ComponentHealth("tasks", Status.OK, data=data)
