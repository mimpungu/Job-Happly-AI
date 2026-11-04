from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database.session import UnitOfWork
from app.modules.demo.application.service import DemoService
from app.modules.demo.infrastructure.repository import SqlDemoRepository
from app.modules.document_generation.infrastructure.document_storage import LocalDocumentStorage


async def ensure_demo_inactive(uow: UnitOfWork, owner_id: uuid.UUID) -> None:
    """Garde pour les routes qui travaillent par unité de travail (collecte, recherche)."""
    async with uow.begin() as session:
        await build_demo_service(session).ensure_inactive(owner_id)


def build_demo_service(session: AsyncSession) -> DemoService:
    base = Path(get_settings().storage_dir) / "documents"
    return DemoService(SqlDemoRepository(session), LocalDocumentStorage(base_directory=base))
