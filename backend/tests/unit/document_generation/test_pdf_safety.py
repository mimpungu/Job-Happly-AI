"""Contrôle des PDF générés : contenu actif, fichiers joints, fichiers non PDF (TASK-018-16)."""

import io

import pytest
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, TextStringObject

from app.modules.document_generation.domain.pdf_safety import (
    MAX_PDF_BYTES,
    UnsafePdfError,
    assert_safe_pdf,
)


def _pdf(modif=None) -> bytes:  # type: ignore[no-untyped-def]
    ecrivain = PdfWriter()
    ecrivain.add_blank_page(200, 200)
    if modif:
        modif(ecrivain)
    tampon = io.BytesIO()
    ecrivain.write(tampon)
    return tampon.getvalue()


def test_un_pdf_ordinaire_est_accepte() -> None:
    assert_safe_pdf(_pdf())


def test_un_lien_hypertexte_est_accepte() -> None:
    from pypdf.annotations import Link

    assert_safe_pdf(
        _pdf(lambda w: w.add_annotation(0, Link(rect=(0, 0, 50, 20), url="https://x.test")))
    )


@pytest.mark.parametrize("contenu", [b"", b"MZ\x90\x00pas un pdf", b"<html>%PDF-</html>"])
def test_un_fichier_qui_n_est_pas_un_pdf_est_refuse(contenu: bytes) -> None:
    with pytest.raises(UnsafePdfError):
        assert_safe_pdf(contenu)


def test_un_pdf_tronque_ou_corrompu_est_refuse() -> None:
    with pytest.raises(UnsafePdfError):
        assert_safe_pdf(_pdf()[:60])


def test_un_javascript_a_l_ouverture_est_refuse() -> None:
    with pytest.raises(UnsafePdfError):
        assert_safe_pdf(_pdf(lambda w: w.add_js("app.alert('x')")))


def test_une_action_a_l_ouverture_est_refusee() -> None:
    def ouvrir(w: PdfWriter) -> None:
        action = DictionaryObject(
            {
                NameObject("/S"): NameObject("/Launch"),
                NameObject("/F"): TextStringObject("calc.exe"),
            }
        )
        w._root_object[NameObject("/OpenAction")] = w._add_object(action)

    with pytest.raises(UnsafePdfError):
        assert_safe_pdf(_pdf(ouvrir))


def test_un_fichier_joint_est_refuse() -> None:
    with pytest.raises(UnsafePdfError):
        assert_safe_pdf(_pdf(lambda w: w.add_attachment("secret.txt", b"donnees")))


def test_un_pdf_demesure_est_refuse() -> None:
    with pytest.raises(UnsafePdfError):
        assert_safe_pdf(b"%PDF-" + b"0" * MAX_PDF_BYTES)


def test_une_destination_a_l_ouverture_posee_par_hyperref_est_acceptee() -> None:
    """pdfLaTeX + hyperref écrit `/OpenAction [page /Fit]` : un tableau, pas une action."""
    from pypdf.generic import ArrayObject

    def destination(w: PdfWriter) -> None:
        w._root_object[NameObject("/OpenAction")] = ArrayObject(
            [w.pages[0].indirect_reference, NameObject("/Fit")]
        )

    assert_safe_pdf(_pdf(destination))


def test_une_action_javascript_chainee_apres_une_action_inoffensive_est_refusee() -> None:
    def chaine(w: PdfWriter) -> None:
        dangereuse = w._add_object(DictionaryObject({NameObject("/S"): NameObject("/JavaScript")}))
        premiere = DictionaryObject(
            {NameObject("/S"): NameObject("/GoTo"), NameObject("/Next"): dangereuse}
        )
        w._root_object[NameObject("/OpenAction")] = w._add_object(premiere)

    with pytest.raises(UnsafePdfError):
        assert_safe_pdf(_pdf(chaine))
