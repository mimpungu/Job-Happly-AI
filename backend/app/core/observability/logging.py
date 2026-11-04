"""Logs structurés JSON avec identifiant de corrélation (TASK-018-23, 018-24).

Une ligne = un objet JSON : horodatage UTC, niveau, logger, message (masqué), `request_id` et les
champs `extra` fournis par l'appelant (masqués s'ils sont textuels). Jamais de corps de requête,
de CV ni de secret.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from app.core.observability.context import request_id_var
from app.core.observability.redaction import redact

_STANDARD = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime", "taskName"}
_HANDLER_FLAG = "_happly_json_handler"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        charge: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": redact(record.getMessage()),
        }
        request_id = request_id_var.get()
        if request_id:
            charge["request_id"] = request_id
        for cle, valeur in record.__dict__.items():
            if cle in _STANDARD or cle.startswith("_"):
                continue
            charge[cle] = redact(valeur) if isinstance(valeur, str) else valeur
        if record.exc_info and record.exc_info[0] is not None:
            # Type et message masqué ; la pile complète reste réservée au débogage local.
            charge["exception"] = (
                f"{record.exc_info[0].__name__}: {redact(str(record.exc_info[1]))}"
            )
        return json.dumps(charge, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Idempotent : un seul gestionnaire JSON sur le logger racine."""
    racine = logging.getLogger()
    racine.setLevel(level)
    for gestionnaire in racine.handlers:
        if getattr(gestionnaire, _HANDLER_FLAG, False):
            return
    gestionnaire = logging.StreamHandler(sys.stdout)
    gestionnaire.setFormatter(JsonFormatter())
    setattr(gestionnaire, _HANDLER_FLAG, True)
    racine.addHandler(gestionnaire)
