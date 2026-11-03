"""Utilitaires de texte purs : normalisation, nettoyage HTML, empreinte de contenu."""

from __future__ import annotations

import hashlib
import html
import re
import unicodedata
from html.parser import HTMLParser

_ESPACES = re.compile(r"[ \t\f\v\u00a0]+")
_LIGNES_VIDES = re.compile(r"\n{3,}")
_BLOCS = frozenset(
    {"p", "div", "br", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section"}
)
_IGNORES = frozenset({"script", "style", "noscript", "template"})


def normalize_text(valeur: str) -> str:
    """Minuscules sans accents ni ponctuation superflue, pour comparer des intitulés."""
    decompose = unicodedata.normalize("NFKD", valeur)
    sans_accents = "".join(c for c in decompose if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^\w]+", " ", sans_accents.casefold()).split())


class _Extracteur(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._morceaux: list[str] = []
        self._ignore = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _IGNORES:
            self._ignore += 1
        elif tag in _BLOCS:
            self._morceaux.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _IGNORES:
            self._ignore = max(0, self._ignore - 1)
        elif tag in _BLOCS:
            self._morceaux.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._ignore:
            self._morceaux.append(data)

    def texte(self) -> str:
        return "".join(self._morceaux)


def html_to_text(contenu: str) -> str:
    """Convertit du HTML non fiable en texte brut : aucune balise ni script n'est conservé.

    Certaines sources fournissent du HTML échappé (`&lt;p&gt;`) : il est d'abord décodé.
    """
    candidat = html.unescape(contenu) if "&lt;" in contenu else contenu
    extracteur = _Extracteur()
    extracteur.feed(candidat)
    extracteur.close()
    lignes = (_ESPACES.sub(" ", ligne).strip() for ligne in extracteur.texte().splitlines())
    return _LIGNES_VIDES.sub("\n\n", "\n".join(lignes)).strip()


def content_hash(*parties: str | None) -> str:
    """Empreinte SHA-256 stable d'un contenu (absent et vide sont distingués du reste)."""
    morceaux = ["\x00" if p is None else p for p in parties]
    return hashlib.sha256("\x1f".join(morceaux).encode("utf-8")).hexdigest()
