from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import Base, CreatedAtMixin, OwnedMixin, PrimaryKeyMixin


class NotificationModel(PrimaryKeyMixin, CreatedAtMixin, OwnedMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_owner_id_read_at_created_at", "owner_id", "read_at", "created_at"),
    )

    kind: Mapped[str] = mapped_column(String(60))
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
