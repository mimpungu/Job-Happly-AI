"""Extraction du texte brut d'un PDF, d'un DOCX ou d'un TXT.

Fonctions synchrones et CPU-bound : l'appelant les exécute hors de la boucle d'événements.
Rien n'est écrit sur le disque : le contenu reste en mémoire et le fichier n'est pas conservé.
Aucune reconnaissance de caractères (OCR) : un PDF scanné est signalé, pas deviné.
"""

from __future__ import annotations

import io
import re
import zipfile
from xml.etree.ElementTree import Element

from defusedxml import ElementTree as SafeElementTree
from defusedxml.common import DefusedXmlException
from pypdf import PageObject, PdfReader
from pypdf.errors import PyPdfError

from app.modules.candidate_profile.domain.documents import (
    MAX_DOCX_COMPRESSION_RATIO,
    MAX_DOCX_XML_BYTES,
    MAX_PDF_PAGES,
    MAX_TEXT_CHARS,
    DocumentFormat,
    DocumentTooLargeError,
    EncryptedDocumentError,
    ExtractedText,
    MalformedDocumentError,
    detect_format,
)
from app.modules.candidate_profile.domain.text_columns import TextFragment, read_in_columns

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def extract_document_text(filename: str, content: bytes) -> ExtractedText:
    """Valide le format réel puis extrait le texte (non normalisé)."""
    format_reel = detect_format(filename, content)
    if format_reel is DocumentFormat.PDF:
        resultat = _extraire_pdf(content)
    elif format_reel is DocumentFormat.DOCX:
        resultat = _extraire_docx(content)
    else:
        resultat = _extraire_txt(content)
    if len(resultat.text) > MAX_TEXT_CHARS:
        raise DocumentTooLargeError("Le texte du document est trop volumineux pour être analysé.")
    return resultat


def _extraire_pdf(content: bytes) -> ExtractedText:
    try:
        lecteur = PdfReader(io.BytesIO(content), strict=False)
        if lecteur.is_encrypted:
            raise EncryptedDocumentError(
                "Ce PDF est protégé par un mot de passe. Importez une version non protégée."
            )
        pages = lecteur.pages
        nombre = len(pages)
        if nombre == 0:
            raise MalformedDocumentError("Le PDF ne contient aucune page.")
        if nombre > MAX_PDF_PAGES:
            raise DocumentTooLargeError(f"Le PDF dépasse {MAX_PDF_PAGES} pages.")
        textes = [_texte_de_page(page) for page in pages]
    except (EncryptedDocumentError, MalformedDocumentError, DocumentTooLargeError):
        raise
    except (PyPdfError, ValueError, KeyError, TypeError, AttributeError, RecursionError) as erreur:
        # pypdf lève des types variés sur un fichier corrompu : tous deviennent une erreur claire.
        raise MalformedDocumentError("Le PDF est corrompu ou illisible.") from erreur
    return ExtractedText("\n\n".join(textes), DocumentFormat.PDF, page_count=nombre)


def _texte_de_page(page: PageObject) -> str:
    """Texte brut de la page ; lu colonne par colonne si la page a deux colonnes nettes."""
    brut = page.extract_text() or ""
    fragments: list[TextFragment] = []

    def collecter(
        texte: str, cm: list[float], tm: list[float], _police: object, taille: float
    ) -> None:
        # Position réelle sur la page : la matrice de texte (tm) vit dans l'espace défini par cm.
        fragments.append(
            TextFragment(
                x=tm[4] * cm[0] + tm[5] * cm[2] + cm[4],
                y=tm[4] * cm[1] + tm[5] * cm[3] + cm[5],
                size=abs(taille * tm[0] * cm[0]) or abs(taille),
                text=texte,
            )
        )

    try:
        page.extract_text(visitor_text=collecter)
        en_colonnes = read_in_columns(fragments)
    except (PyPdfError, ValueError, KeyError, TypeError, AttributeError, RecursionError):
        # Une lecture par position qui échoue ne doit pas rendre illisible un PDF lisible.
        return brut
    return en_colonnes if en_colonnes is not None else brut


def _extraire_docx(content: bytes) -> ExtractedText:
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as erreur:
        raise MalformedDocumentError("Le document Word est corrompu ou illisible.") from erreur
    with archive:
        noms = set(archive.namelist())
        if "word/document.xml" not in noms:
            raise MalformedDocumentError("Ce fichier n'est pas un document Word valide.")
        # En-têtes d'abord : les coordonnées d'un CV y figurent souvent. Pieds de page ignorés.
        parties = sorted(n for n in noms if re.fullmatch(r"word/header\d*\.xml", n))
        parties.append("word/document.xml")
        paragraphes: list[str] = []
        for nom in parties:
            paragraphes.extend(_paragraphes(_lire_xml(archive, nom)))
    return ExtractedText("\n".join(paragraphes), DocumentFormat.DOCX)


def _lire_xml(archive: zipfile.ZipFile, nom: str) -> Element:
    info = archive.getinfo(nom)
    # Contrôle sur la taille déclarée *et* à la lecture : l'en-tête ZIP peut mentir.
    if info.file_size > MAX_DOCX_XML_BYTES:
        raise DocumentTooLargeError("Le document Word est trop volumineux.")
    if info.compress_size and info.file_size / info.compress_size > MAX_DOCX_COMPRESSION_RATIO:
        raise MalformedDocumentError("Le document Word est suspect (taux de compression anormal).")
    try:
        with archive.open(info) as flux:
            donnees = flux.read(MAX_DOCX_XML_BYTES + 1)
    except (zipfile.BadZipFile, RuntimeError, OSError) as erreur:
        raise MalformedDocumentError("Le document Word est corrompu ou illisible.") from erreur
    if len(donnees) > MAX_DOCX_XML_BYTES:
        raise DocumentTooLargeError("Le document Word est trop volumineux.")
    try:
        return SafeElementTree.fromstring(donnees)
    except (DefusedXmlException, SafeElementTree.ParseError) as erreur:
        # DTD/entités refusées par defusedxml (XXE, « milliard de rires ») ou XML invalide.
        raise MalformedDocumentError("Le document Word est corrompu ou illisible.") from erreur


def _paragraphes(racine: Element) -> list[str]:
    lignes: list[str] = []
    for paragraphe in racine.iter(f"{_W}p"):
        morceaux: list[str] = []
        for element in paragraphe.iter():
            if element.tag == f"{_W}t" and element.text:
                morceaux.append(element.text)
            elif element.tag == f"{_W}tab":
                morceaux.append("\t")
            elif element.tag in (f"{_W}br", f"{_W}cr"):
                morceaux.append("\n")
        texte = "".join(morceaux)
        if paragraphe.find(f"{_W}pPr/{_W}numPr") is not None and texte.strip():
            texte = "- " + texte  # élément de liste Word : rendu comme une puce
        lignes.append(texte)
    return lignes


def _extraire_txt(content: bytes) -> ExtractedText:
    if content.startswith((b"\xff\xfe", b"\xfe\xff")):
        return ExtractedText(_decoder(content, "utf-16"), DocumentFormat.TXT)
    try:
        return ExtractedText(content.decode("utf-8-sig"), DocumentFormat.TXT)
    except UnicodeDecodeError:
        pass
    try:
        # Anciens fichiers Windows : encodage deviné, donc signalé à l'utilisateur.
        texte = content.decode("cp1252")
    except UnicodeDecodeError as erreur:
        raise MalformedDocumentError(
            "L'encodage du fichier texte n'est pas reconnu. Enregistrez-le en UTF-8."
        ) from erreur
    return ExtractedText(
        texte,
        DocumentFormat.TXT,
        warnings=("Encodage non UTF-8 : lu en Windows-1252, vérifiez les accents.",),
    )


def _decoder(content: bytes, encodage: str) -> str:
    try:
        return content.decode(encodage)
    except UnicodeDecodeError as erreur:
        raise MalformedDocumentError("Le fichier texte est illisible.") from erreur
