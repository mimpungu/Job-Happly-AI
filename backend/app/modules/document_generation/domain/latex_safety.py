"""Contrôle statique d'une source LaTeX avant compilation (CLAUDE.md §11).

Une source modifiée par l'utilisateur est une entrée non fiable. Cette liste de refus n'est
qu'une première barrière : elle est doublée à l'exécution par le mode « paranoïaque » de
TeX (`openin_any=p`, `openout_any=p`), l'absence de shell-escape et l'isolation du processus.
"""

from __future__ import annotations

import re

# Primitives et commandes qui lisent, écrivent ou exécutent hors du document.
_COMMANDES_INTERDITES = (
    "input",
    "include",
    "includeonly",
    "openin",
    "openout",
    "read",
    "readline",
    "write",
    "newwrite",
    "newread",
    "immediate",
    "catcode",
    "csname",
    "pdffilesize",
    "pdffiledump",
    "pdfmdfivesum",
    "pdfshellescape",
    "pdfobj",
    "pdfannot",
    "pdfliteral",
    "special",
    "lstinputlisting",
    "verbatiminput",
)

# Paquets permettant d'inclure des fichiers, d'exécuter du code ou d'en écrire.
_PAQUETS_INTERDITS = frozenset(
    {
        "catchfile",
        "filecontents",
        "import",
        "subfiles",
        "embedfile",
        "attachfile",
        "attachfile2",
        "pdfpages",
        "shellesc",
        "minted",
        "pythontex",
        "luacode",
        "sagetex",
        "svg",
        "newfile",
        "datatool",
        "csvsimple",
        "readarray",
        "listings",
        "verbatim",
        "fancyvrb",
        "epstopdf",
        "write18",
    }
)

_COMMENTAIRE = re.compile(r"(?<!\\)%.*")
_MOTIF_COMMANDE = re.compile(r"\\(" + "|".join(_COMMANDES_INTERDITES) + r")(?![A-Za-z])")
_MOTIF_PAQUET = re.compile(r"\\(?:usepackage|RequirePackage)\s*(?:\[[^\]]*\])?\s*\{([^}]*)\}")


class ForbiddenLaTeXError(ValueError):
    """La source contient une commande interdite (lecture de fichier, exécution…)."""


def validate_latex_source(source: str) -> None:
    """Lève `ForbiddenLaTeXError` si la source contient une construction interdite."""
    sans_commentaires = _COMMENTAIRE.sub("", source)

    trouvee = _MOTIF_COMMANDE.search(sans_commentaires)
    if trouvee is not None:
        raise ForbiddenLaTeXError(
            f"Commande LaTeX interdite pour des raisons de sécurité : \\{trouvee.group(1)}"
        )
    for liste in _MOTIF_PAQUET.findall(sans_commentaires):
        for paquet in (p.strip() for p in liste.split(",")):
            if paquet in _PAQUETS_INTERDITS:
                raise ForbiddenLaTeXError(
                    f"Paquet LaTeX interdit pour des raisons de sécurité : {paquet}"
                )
