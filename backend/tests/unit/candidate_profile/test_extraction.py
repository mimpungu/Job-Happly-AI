import contextlib
import io
import zipfile

import pytest
from pypdf import PdfWriter

from app.modules.candidate_profile.application.import_document import DocumentReader
from app.modules.candidate_profile.domain.documents import (
    MAX_PDF_PAGES,
    DocumentFormat,
    DocumentTooLargeError,
    EmptyDocumentError,
    EncryptedDocumentError,
    MalformedDocumentError,
)
from app.modules.candidate_profile.infrastructure.extraction import extract_document_text

from .builders import make_docx, make_pdf, paragraphe


def _pdf_vide(pages: int = 1, mot_de_passe: str | None = None) -> bytes:
    ecrivain = PdfWriter()
    for _ in range(pages):
        ecrivain.add_blank_page(width=595, height=842)
    if mot_de_passe:
        ecrivain.encrypt(mot_de_passe)
    tampon = io.BytesIO()
    ecrivain.write(tampon)
    return tampon.getvalue()


class TestPdf:
    def test_extrait_le_texte_accentue_de_plusieurs_pages(self) -> None:
        contenu = make_pdf([["Marie Dupont", "Développeuse à Paris"], ["Compétences : Python"]])

        resultat = extract_document_text("cv.pdf", contenu)

        assert resultat.format is DocumentFormat.PDF
        assert resultat.page_count == 2
        assert "Développeuse à Paris" in resultat.text
        assert "Compétences : Python" in resultat.text

    def test_caracteres_speciaux_du_pdf_ne_cassent_pas_la_lecture(self) -> None:
        resultat = extract_document_text("cv.pdf", make_pdf([["C++ (avancé) \\ SQL"]]))

        assert "C++ (avancé)" in resultat.text

    def test_pdf_protege_par_mot_de_passe_est_refuse_sans_tentative(self) -> None:
        with pytest.raises(EncryptedDocumentError, match="mot de passe"):
            extract_document_text("cv.pdf", _pdf_vide(mot_de_passe="secret"))

    @pytest.mark.parametrize(
        "contenu",
        [
            b"%PDF-1.4\nn'importe quoi",
            b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog",
            b"%PDF-",
        ],
    )
    def test_pdf_corrompu_donne_une_erreur_claire(self, contenu: bytes) -> None:
        with pytest.raises(MalformedDocumentError):
            extract_document_text("cv.pdf", contenu)

    def test_pdf_tronque_ne_plante_pas(self) -> None:
        complet = make_pdf([["Texte " * 20]])

        for coupe in (len(complet) // 2, len(complet) - 30):
            # Une erreur claire est acceptée ; toute autre exception serait un bug.
            with contextlib.suppress(MalformedDocumentError):
                extract_document_text("cv.pdf", complet[:coupe])

    def test_trop_de_pages(self) -> None:
        with pytest.raises(DocumentTooLargeError, match="pages"):
            extract_document_text("cv.pdf", _pdf_vide(MAX_PDF_PAGES + 1))

    async def test_pdf_scanne_sans_texte_est_signale_pas_devine(self) -> None:
        lecteur = DocumentReader(extract_document_text)

        with pytest.raises(EmptyDocumentError, match="reconnaissance de caractères"):
            await lecteur.read("scan.pdf", _pdf_vide())


class TestDocx:
    def test_extrait_paragraphes_listes_tableaux_et_tabulations(self) -> None:
        corps = (
            paragraphe("Marie Dupont")
            + paragraphe("Python", puce=True)
            + "<w:tbl><w:tr><w:tc>"
            + paragraphe("Cellule A")
            + "</w:tc><w:tc>"
            + paragraphe("Cellule B")
            + "</w:tc></w:tr></w:tbl>"
            + "<w:p><w:r><w:t>2020</w:t></w:r><w:r><w:tab/></w:r><w:r><w:t>2023</w:t></w:r></w:p>"
        )

        resultat = extract_document_text("cv.docx", make_docx(corps))

        assert resultat.format is DocumentFormat.DOCX
        lignes = resultat.text.split("\n")
        assert "Marie Dupont" in lignes
        assert "- Python" in lignes
        assert {"Cellule A", "Cellule B"} <= set(lignes)
        assert "2020\t2023" in lignes

    def test_les_coordonnees_de_l_en_tete_sont_lues_avant_le_corps(self) -> None:
        contenu = make_docx(paragraphe("Corps"), entetes=[paragraphe("marie@exemple.test")])

        assert extract_document_text("cv.docx", contenu).text.startswith("marie@exemple.test")

    def test_pied_de_page_ignore(self) -> None:
        contenu = make_docx(paragraphe("Corps"), extra={"word/footer1.xml": b"<w:ftr/>"})

        assert extract_document_text("cv.docx", contenu).text == "Corps"

    def test_archive_sans_document_word(self) -> None:
        tampon = io.BytesIO()
        with zipfile.ZipFile(tampon, "w") as z:
            z.writestr("autre.txt", "x")

        with pytest.raises(MalformedDocumentError, match="pas un document Word"):
            extract_document_text("cv.docx", tampon.getvalue())

    def test_zip_corrompu(self) -> None:
        with pytest.raises(MalformedDocumentError):
            extract_document_text("cv.docx", b"PK\x03\x04" + b"\x00" * 50)

    def test_xml_invalide(self) -> None:
        tampon = io.BytesIO()
        with zipfile.ZipFile(tampon, "w") as z:
            z.writestr("word/document.xml", "<w:document><pas ferme")

        with pytest.raises(MalformedDocumentError):
            extract_document_text("cv.docx", tampon.getvalue())

    def test_entite_externe_xxe_refusee(self) -> None:
        xxe = (
            '<?xml version="1.0"?><!DOCTYPE d [<!ENTITY x SYSTEM "file:///etc/passwd">]>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body><w:p><w:r><w:t>&x;</w:t></w:r></w:p></w:body></w:document>"
        )
        tampon = io.BytesIO()
        with zipfile.ZipFile(tampon, "w") as z:
            z.writestr("word/document.xml", xxe)

        with pytest.raises(MalformedDocumentError):
            extract_document_text("cv.docx", tampon.getvalue())

    def test_milliard_de_rires_refuse(self) -> None:
        bombe = (
            '<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "aaaaaaaaaa">'
            '<!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">]>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body><w:p><w:r><w:t>&b;</w:t></w:r></w:p></w:body></w:document>"
        )
        tampon = io.BytesIO()
        with zipfile.ZipFile(tampon, "w") as z:
            z.writestr("word/document.xml", bombe)

        with pytest.raises(MalformedDocumentError):
            extract_document_text("cv.docx", tampon.getvalue())

    def test_bombe_de_decompression_refusee_par_le_taux(self) -> None:
        # 1 Mo de « a » se compresse ~1000 fois : bien au-delà du taux toléré.
        contenu = make_docx(paragraphe("a" * 1_000_000))

        with pytest.raises(MalformedDocumentError, match="compression"):
            extract_document_text("cv.docx", contenu)

    def test_xml_declare_trop_volumineux(self) -> None:
        contenu = make_docx("<w:p/>" * 4_000_000)  # ~24 Mo décompressés

        with pytest.raises(DocumentTooLargeError):
            extract_document_text("cv.docx", contenu)


class TestTxt:
    def test_utf8_et_bom(self) -> None:
        assert extract_document_text("cv.txt", "Éric\n".encode("utf-8-sig")).text == "Éric\n"

    def test_utf16(self) -> None:
        resultat = extract_document_text("cv.txt", "Éric café".encode("utf-16"))

        assert resultat.text == "Éric café"

    def test_windows_1252_est_lu_et_signale(self) -> None:
        resultat = extract_document_text("cv.txt", "Éric café".encode("cp1252"))

        assert resultat.text == "Éric café"
        assert "Windows-1252" in resultat.warnings[0]

    def test_encodage_irrecuperable(self) -> None:
        # 0x81 n'existe pas en cp1252 : ni UTF-8 ni cp1252 ne conviennent.
        with pytest.raises(MalformedDocumentError, match="encodage"):
            extract_document_text("cv.txt", b"abc \x81\x8d\x8f\x90\x9d")

    def test_utf16_tronque(self) -> None:
        with pytest.raises(MalformedDocumentError):
            extract_document_text("cv.txt", b"\xff\xfeA")


class TestLecteur:
    async def test_normalise_le_texte_extrait(self) -> None:
        contenu = make_pdf([["• Développeuse Python confirmée", "• Experte SQL et données"]])

        resultat = await DocumentReader(extract_document_text).read("cv.pdf", contenu)

        assert resultat.text == "- Développeuse Python confirmée\n- Experte SQL et données"

    async def test_document_presque_vide_refuse(self) -> None:
        with pytest.raises(EmptyDocumentError):
            await DocumentReader(extract_document_text).read("cv.txt", b"   \n\n  ok  ")

    async def test_les_avertissements_sont_conserves(self) -> None:
        texte = "Éric Dupont, développeur à Paris depuis dix ans".encode("cp1252")

        resultat = await DocumentReader(extract_document_text).read("cv.txt", texte)

        assert resultat.warnings
