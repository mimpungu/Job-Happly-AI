"""Fabrication de vrais fichiers PDF et DOCX pour les tests (aucun fichier binaire versionné)."""

import io
import zipfile
from xml.sax.saxutils import escape


def _echapper(ligne: str) -> bytes:
    return (
        ligne.encode("cp1252").replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")
    )


def _assembler_pdf(flux_par_page: list[bytes]) -> bytes:
    """PDF minimal valide : une police Helvetica (WinAnsi) et un flux de contenu par page."""
    objets: list[bytes] = []

    def ajouter(corps: bytes) -> int:
        objets.append(corps)
        return len(objets)

    ajouter(b"<< /Type /Catalog /Pages 2 0 R >>")  # 1
    ajouter(b"")  # 2 : remplacé après connaissance des pages
    police = ajouter(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
    )
    numeros: list[int] = []
    for flux in flux_par_page:
        contenu = ajouter(b"<< /Length %d >>\nstream\n" % len(flux) + flux + b"\nendstream")
        numeros.append(
            ajouter(
                b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                b"/Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>" % (police, contenu)
            )
        )
    kids = b" ".join(b"%d 0 R" % n for n in numeros)
    objets[1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (kids, len(numeros))

    sortie = bytearray(b"%PDF-1.4\n")
    positions = []
    for i, corps in enumerate(objets, start=1):
        positions.append(len(sortie))
        sortie += b"%d 0 obj\n" % i + corps + b"\nendobj\n"
    debut_xref = len(sortie)
    sortie += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objets) + 1)
    for position in positions:
        sortie += b"%010d 00000 n \n" % position
    sortie += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objets) + 1,
        debut_xref,
    )
    return bytes(sortie)


def make_pdf(pages: list[list[str]]) -> bytes:
    """Un texte par ligne et par page, du haut vers le bas."""
    flux_par_page = []
    for lignes in pages:
        flux = b"BT /F1 12 Tf 14 TL 50 750 Td\n"
        for ligne in lignes:
            flux += b"(" + _echapper(ligne) + b") Tj T*\n"
        flux_par_page.append(flux + b"ET")
    return _assembler_pdf(flux_par_page)


def make_pdf_positioned(fragments: list[tuple[int, int, str]]) -> bytes:
    """Une page dont chaque texte (x, y, texte) est posé à sa position, dans l'ordre donné.

    L'ordre du flux n'est pas l'ordre de lecture : reproduit les CV issus de modèles graphiques,
    où les titres de section sont dessinés avant leur contenu.
    """
    flux = b""
    for x, y, texte in fragments:
        flux += b"BT /F1 10 Tf %d %d Td (" % (x, y) + _echapper(texte) + b") Tj ET\n"
    return _assembler_pdf([flux])


_NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
_TYPES = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="xml" ContentType="application/xml"/></Types>'
)


def paragraphe(texte: str, *, puce: bool = False) -> str:
    props = '<w:pPr><w:numPr><w:numId w:val="1"/></w:numPr></w:pPr>' if puce else ""
    return f'<w:p>{props}<w:r><w:t xml:space="preserve">{escape(texte)}</w:t></w:r></w:p>'


def make_docx(
    corps_xml: str, *, entetes: list[str] | None = None, extra: dict[str, bytes] | None = None
) -> bytes:
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _TYPES)
        z.writestr(
            "word/document.xml", f"<w:document {_NS}><w:body>{corps_xml}</w:body></w:document>"
        )
        for i, entete in enumerate(entetes or [], start=1):
            z.writestr(f"word/header{i}.xml", f"<w:hdr {_NS}>{entete}</w:hdr>")
        for nom, donnees in (extra or {}).items():
            z.writestr(nom, donnees)
    return tampon.getvalue()
