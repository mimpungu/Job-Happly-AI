"""Contexte de requête partagé par les logs : l'identifiant de corrélation (TASK-018-24)."""

from __future__ import annotations

from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("happly_request_id", default=None)
