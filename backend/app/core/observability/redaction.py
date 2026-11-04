"""Masquage des secrets et données personnelles dans les logs (TASK-018-23).

Dernier filet : le code ne doit déjà jamais journaliser de secret ni de CV. Ce masquage couvre
l'erreur humaine (message d'exception d'une bibliothèque qui contient une URL avec clé, etc.).
"""

from __future__ import annotations

import re

MASK = "***"

_MOTIFS: tuple[tuple[re.Pattern[str], str], ...] = (
    # Identifiants dans une URL : https://user:motdepasse@hote
    (re.compile(r"(?<=://)[^/\s:@]+:[^/\s@]+@"), f"{MASK}@"),
    # Paramètres sensibles : ?key=…, &api_key=…, token=…, password=…
    (
        re.compile(
            r"(?i)\b(api[_-]?key|key|token|access[_-]?token|secret|client[_-]?secret|password|"
            r"passwd|authorization)(\s*[=:]\s*)(bearer\s+)?[^\s&\"',;]+"
        ),
        rf"\1\2\3{MASK}",
    ),
    # En-tête Authorization isolé
    (re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]{8,}"), f"Bearer {MASK}"),
    # Clés d'API usuelles (Google, OpenAI-like)
    (re.compile(r"\bAIza[0-9A-Za-z_-]{20,}"), MASK),
    (re.compile(r"\bsk-[0-9A-Za-z_-]{16,}"), MASK),
    # Adresses e-mail (données personnelles)
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "***@***"),
)


def redact(texte: str) -> str:
    for motif, remplacement in _MOTIFS:
        texte = motif.sub(remplacement, texte)
    return texte
