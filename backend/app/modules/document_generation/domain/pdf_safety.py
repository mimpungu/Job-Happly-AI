"""Contrôle des fichiers générés (TASK-018-16) : un PDF sorti du compilateur est vérifié avant
d'être stocké ou proposé au téléchargement.

Un CV n'a besoin ni de script, ni de fichier joint, ni d'action automatique à l'ouverture : leur
présence signale une source LaTeX détournée, le document est alors refusé.
"""

from __future__ import annotations

import io
from typing import cast

from pypdf import PdfReader
from pypdf.errors import PyPdfError
from pypdf.generic import DictionaryObject

MAX_PDF_BYTES = 20 * 1024 * 1024
_ACTIONS_INTERDITES = {
    "/JavaScript",
    "/Launch",
    "/ImportData",
    "/SubmitForm",
    "/GoToR",
    "/Rendition",
}


class UnsafePdfError(ValueError):
    """Le PDF produit contient du contenu actif ou n'est pas un PDF valide."""


def _action_dangereuse(objet: object) -> bool:
    """Une action (ou sa chaîne `/Next`) interdite. Une destination (tableau, ex. `/Fit` posé par
    hyperref à l'ouverture) n'est pas une action : seules les actions à effet le sont."""
    for _ in range(10):  # chaîne bornée : jamais de boucle infinie sur un PDF piégé
        resolu = objet.get_object() if hasattr(objet, "get_object") else objet
        if not isinstance(resolu, DictionaryObject):
            return False
        if resolu.get("/S") in _ACTIONS_INTERDITES:
            return True
        suivant = resolu.get("/Next")
        if suivant is None:
            return False
        if isinstance(suivant, list):
            return any(_action_dangereuse(a) for a in suivant)
        objet = suivant
    return True  # chaîne anormalement longue : suspecte


def assert_safe_pdf(donnees: bytes) -> None:
    if len(donnees) > MAX_PDF_BYTES:
        raise UnsafePdfError("Le PDF généré dépasse la taille maximale autorisée.")
    if not donnees.startswith(b"%PDF-"):
        raise UnsafePdfError("Le fichier généré n'est pas un PDF.")
    try:
        lecteur = PdfReader(io.BytesIO(donnees), strict=False)
        catalogue = cast(DictionaryObject, lecteur.trailer["/Root"])
        if "/OpenAction" in catalogue and _action_dangereuse(catalogue["/OpenAction"]):
            raise UnsafePdfError("Le PDF déclenche une action à l'ouverture.")
        supplementaires = catalogue.get("/AA")
        if supplementaires is not None and any(
            _action_dangereuse(a)
            for a in cast(DictionaryObject, supplementaires.get_object()).values()
        ):
            raise UnsafePdfError("Le PDF déclenche une action automatique.")
        noms = catalogue.get("/Names")
        if noms is not None and (
            "/JavaScript" in noms.get_object() or "/EmbeddedFiles" in noms.get_object()
        ):
            raise UnsafePdfError("Le PDF contient un script ou un fichier joint.")
        if len(lecteur.pages) == 0:
            raise UnsafePdfError("Le PDF généré est vide.")
        for page in lecteur.pages:
            for reference in page.get("/Annots", []) or []:
                annotation = cast(DictionaryObject, reference.get_object())
                action = annotation.get("/A")
                if action is not None and _action_dangereuse(action):
                    raise UnsafePdfError("Le PDF contient une action interdite.")
                if annotation.get("/Subtype") == "/FileAttachment":
                    raise UnsafePdfError("Le PDF contient un fichier joint.")
    except UnsafePdfError:
        raise
    except (PyPdfError, KeyError, ValueError, TypeError, AttributeError) as erreur:
        raise UnsafePdfError("Le PDF généré est illisible ou corrompu.") from erreur
