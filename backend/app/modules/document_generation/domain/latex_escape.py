"""Échappement LaTeX sécurisé pour empêcher injections et erreurs de syntaxe."""

from __future__ import annotations

import re

# Caractères spéciaux LaTeX à échapper obligatoirement en une seule passe
_LATEX_ESCAPES: dict[str, str] = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}

_LATEX_REGEX = re.compile(r"([\\&%$#_{}~^])")


def latex_escape(text: str | None) -> str:
    """Échappe les caractères réservés de LaTeX tout en préservant le texte UTF-8.

    Exemple : 'R&D / C# / 100% / $50k' -> 'R\\&D / C\\# / 100\\% / \\$50k'
    Les caractères accentués français (é, è, ê, à, ç, etc.) sont intégralement préservés.
    """
    if not text:
        return ""

    # Substitution en une seule passe : les accolades introduites ne sont pas re-échappées
    escaped = _LATEX_REGEX.sub(lambda m: _LATEX_ESCAPES[m.group(1)], text)
    return re.sub(r"\s+", " ", escaped).strip()


def latex_escape_url(url: str | None) -> str:
    """Échappe une URL pour utilisation dans \\href{url}{label}."""
    if not url:
        return ""
    # Dans \href{url}, les caractères comme % et # doivent être protégés
    safe = url.strip()
    safe = safe.replace("%", r"\%").replace("#", r"\#")
    return safe
