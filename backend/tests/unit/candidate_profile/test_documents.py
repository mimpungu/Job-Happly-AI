import pytest

from app.modules.candidate_profile.domain.documents import (
    MAX_UPLOAD_BYTES,
    DocumentFormat,
    DocumentTooLargeError,
    MalformedDocumentError,
    UnsupportedDocumentError,
    detect_format,
    display_filename,
)

from .builders import make_docx, make_pdf, paragraphe


def test_detecte_le_format_a_partir_du_contenu() -> None:
    assert detect_format("cv.pdf", make_pdf([["Bonjour"]])) is DocumentFormat.PDF
    assert detect_format("cv.docx", make_docx(paragraphe("x"))) is DocumentFormat.DOCX
    assert detect_format("cv.txt", "Bonjour é".encode()) is DocumentFormat.TXT


def test_l_extension_est_insensible_a_la_casse() -> None:
    assert detect_format("CV.PDF", make_pdf([["x"]])) is DocumentFormat.PDF


@pytest.mark.parametrize(
    ("nom", "contenu"),
    [
        ("cv.pdf", b"Simple texte deguise"),
        ("cv.txt", b"%PDF-1.4 vrai pdf"),
        ("cv.docx", b"%PDF-1.4 vrai pdf"),
        ("cv.pdf", make_docx(paragraphe("x"))),
    ],
)
def test_refuse_une_extension_qui_ment(nom: str, contenu: bytes) -> None:
    with pytest.raises(UnsupportedDocumentError, match="ne correspond pas"):
        detect_format(nom, contenu)


@pytest.mark.parametrize("nom", ["cv.exe", "cv", "cv.doc", "cv.pdf.exe", ""])
def test_refuse_les_formats_non_pris_en_charge(nom: str) -> None:
    with pytest.raises(UnsupportedDocumentError, match="PDF, DOCX, TXT"):
        detect_format(nom, b"texte")


def test_refuse_un_binaire_inconnu() -> None:
    with pytest.raises(UnsupportedDocumentError):
        detect_format("cv.txt", b"MZ\x90\x00\x03\x00\x00\x00")


def test_refuse_un_fichier_vide() -> None:
    with pytest.raises(MalformedDocumentError, match="vide"):
        detect_format("cv.txt", b"")


def test_refuse_un_fichier_trop_gros() -> None:
    with pytest.raises(DocumentTooLargeError):
        detect_format("cv.txt", b"a" * (MAX_UPLOAD_BYTES + 1))


@pytest.mark.parametrize(
    ("brut", "attendu"),
    [
        ("../../etc/passwd", "passwd"),
        ("C:\\Users\\moi\\cv final.pdf", "cv final.pdf"),
        ("cv<script>.pdf", "cv_script_.pdf"),
        ("..", "document"),
        ("", "document"),
        ("é" * 300 + ".pdf", "é" * 120),
    ],
)
def test_nom_d_affichage_assaini(brut: str, attendu: str) -> None:
    assert display_filename(brut) == attendu
