"""Documents importés (CV) : formats acceptés, limites et erreurs.

Un fichier importé est une entrée **non fiable** : le format est déduit du contenu réel
(octets magiques), jamais de l'extension seule, et le nom fourni n'est jamais utilisé pour
écrire sur le disque.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from enum import StrEnum

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_PDF_PAGES = 30
# Limites anti « bombe de décompression » pour le DOCX (archive ZIP).
MAX_DOCX_XML_BYTES = 20 * 1024 * 1024
MAX_DOCX_COMPRESSION_RATIO = 100
MAX_TEXT_CHARS = 200_000
# En dessous, le document est considéré sans texte exploitable (ex. PDF scanné).
MIN_USEFUL_CHARS = 30


class DocumentFormat(StrEnum):
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"


_EXTENSIONS: dict[str, DocumentFormat] = {
    ".pdf": DocumentFormat.PDF,
    ".docx": DocumentFormat.DOCX,
    ".txt": DocumentFormat.TXT,
}


class DocumentError(ValueError):
    """Erreur d'import dont le message peut être montré à l'utilisateur (sans détail technique)."""


class UnsupportedDocumentError(DocumentError):
    """Format non pris en charge, ou extension qui ne correspond pas au contenu."""


class DocumentTooLargeError(DocumentError):
    """Taille ou nombre de pages au-delà des limites."""


class MalformedDocumentError(DocumentError):
    """Fichier corrompu ou illisible."""


class EncryptedDocumentError(DocumentError):
    """Document protégé par mot de passe : on ne tente jamais de le déchiffrer."""


class EmptyDocumentError(DocumentError):
    """Aucun texte exploitable (scan : la reconnaissance de caractères n'est pas gérée)."""


@dataclass(frozen=True, slots=True)
class ExtractedText:
    text: str
    format: DocumentFormat
    page_count: int | None = None
    # Points d'attention à montrer à l'utilisateur (ex. encodage deviné).
    warnings: tuple[str, ...] = field(default_factory=tuple)


def detect_format(filename: str, content: bytes) -> DocumentFormat:
    """Déduit le format du contenu et refuse une extension incohérente.

    Le DOCX est une archive ZIP : seule l'ouverture du fichier confirme qu'il s'agit bien d'un
    document Word (contrôle fait par l'extracteur).
    """
    if not content:
        raise MalformedDocumentError("Le fichier est vide.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise DocumentTooLargeError(f"Le fichier dépasse {MAX_UPLOAD_BYTES // (1024 * 1024)} Mo.")

    if content.startswith(b"%PDF-"):
        reel = DocumentFormat.PDF
    elif content.startswith(b"PK\x03\x04"):
        reel = DocumentFormat.DOCX
    elif _ressemble_a_du_texte(content):
        reel = DocumentFormat.TXT
    else:
        raise UnsupportedDocumentError(
            "Format non pris en charge. Formats acceptés : PDF, DOCX, TXT."
        )

    extension = _extension(filename)
    declare = _EXTENSIONS.get(extension)
    if declare is None:
        raise UnsupportedDocumentError(
            "Format non pris en charge. Formats acceptés : PDF, DOCX, TXT."
        )
    if declare is not reel:
        raise UnsupportedDocumentError(
            "L'extension du fichier ne correspond pas à son contenu réel."
        )
    return reel


def _extension(filename: str) -> str:
    nom = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    return "." + nom.rsplit(".", 1)[-1].lower() if "." in nom else ""


def _ressemble_a_du_texte(content: bytes) -> bool:
    # Un octet nul trahit un binaire ; UTF-16 en contient légitimement, d'où la nomenclature.
    if content.startswith((b"\xff\xfe", b"\xfe\xff")):
        return True
    return b"\x00" not in content[:8192]


_NON_SURE = re.compile(r"[^\w.\- ]+", re.UNICODE)


def display_filename(filename: str) -> str:
    """Nom **d'affichage** assaini. Ne jamais l'employer comme chemin de fichier."""
    nom = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    nom = unicodedata.normalize("NFC", nom)
    nom = _NON_SURE.sub("_", nom).strip(" ._")
    return nom[:120] or "document"
