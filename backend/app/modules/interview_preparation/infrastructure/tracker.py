"""Écriture dans le suivi des candidatures via son service (un seul historique par candidature)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.application_management.infrastructure.composition import (
    build_application_tracking_service,
)


class ApplicationTracker:
    def __init__(self, session: AsyncSession) -> None:
        self._service = build_application_tracking_service(session)

    async def record_interview(
        self,
        *,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        description: str,
        when: datetime | None,
    ) -> None:
        await self._service.add_interview_event(
            owner_id=owner_id,
            application_id=application_id,
            description=description,
            interview_time=when,
        )

    async def schedule_follow_up(
        self,
        *,
        owner_id: uuid.UUID,
        application_id: uuid.UUID,
        follow_up_at: datetime,
        notes: str | None,
    ) -> None:
        await self._service.schedule_follow_up(
            owner_id=owner_id,
            application_id=application_id,
            follow_up_at=follow_up_at,
            notes=notes,
        )
