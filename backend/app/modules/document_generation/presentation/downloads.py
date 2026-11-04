"""En-têtes HTTP de téléchargement partagés par les routes de CV et de lettres."""

from __future__ import annotations

from urllib.parse import quote


def attachment_headers(filename: str) -> dict[str, str]:
    """`Content-Disposition` valable pour un nom accentué ou non latin (RFC 6266 / 5987)."""
    ascii_name = filename.encode("ascii", "ignore").decode() or "document"
    ascii_name = ascii_name.replace('"', "").replace("\\", "")
    return {
        "Content-Disposition": (
            f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"
        )
    }
