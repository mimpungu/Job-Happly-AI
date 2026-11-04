"""Tests unitaires de l'endpoint d'audit ATS (TASK-012-17 à 21)."""

import httpx
import pytest

from app.main import create_app
from app.modules.document_generation.infrastructure.latex_compiler import (
    IsolatedLaTeXCompiler,
)
from app.modules.document_generation.presentation.downloads import attachment_headers
from app.modules.document_generation.presentation.router import MAX_AUDIT_PDF_BYTES


@pytest.fixture
async def client():  # type: ignore[no-untyped-def]
    transport = httpx.ASGITransport(app=create_app(), raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as c:
        yield c


async def test_audit_ats_endpoint_sur_pdf_reel(
    client: httpx.AsyncClient, compiler: IsolatedLaTeXCompiler
) -> None:
    tex = r"""\documentclass[10pt,a4paper]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\begin{document}
\section*{Curriculum Vitae}
\section*{Expériences professionnelles}
Développeur Python chez Acme Corp.
\section*{Compétences techniques}
Python, FastAPI, SQL.
\section*{Formation}
Master Informatique.
\end{document}
"""
    pdf_bytes = await compiler.compile(tex)

    reponse = await client.post(
        "/api/v1/resumes/audit-ats",
        files={"file": ("cv_test.pdf", pdf_bytes, "application/pdf")},
    )

    assert reponse.status_code == 200
    data = reponse.json()
    assert data["passed"] is True
    assert data["score"] >= 75
    assert data["page_count"] == 1
    assert data["reading_order_valid"] is True


async def test_audit_ats_fichier_vide_renvoie_400(client: httpx.AsyncClient) -> None:
    reponse = await client.post(
        "/api/v1/resumes/audit-ats",
        files={"file": ("vide.pdf", b"", "application/pdf")},
    )
    assert reponse.status_code == 400
    assert "Fichier PDF vide" in reponse.json()["error"]["message"]


async def test_audit_ats_refuse_un_fichier_qui_n_est_pas_un_pdf(client: httpx.AsyncClient) -> None:
    reponse = await client.post(
        "/api/v1/resumes/audit-ats",
        files={"file": ("cv.pdf", b"MZ\x90 executable deguise", "application/pdf")},
    )
    assert reponse.status_code == 415


async def test_audit_ats_refuse_un_fichier_trop_volumineux(client: httpx.AsyncClient) -> None:
    contenu = b"%PDF-1.4\n" + b"0" * MAX_AUDIT_PDF_BYTES
    reponse = await client.post(
        "/api/v1/resumes/audit-ats", files={"file": ("gros.pdf", contenu, "application/pdf")}
    )
    assert reponse.status_code == 413


async def test_audit_ats_pdf_corrompu_donne_un_rapport_en_echec_sans_erreur_500(
    client: httpx.AsyncClient,
) -> None:
    reponse = await client.post(
        "/api/v1/resumes/audit-ats",
        files={"file": ("casse.pdf", b"%PDF-1.4 contenu tronque", "application/pdf")},
    )
    assert reponse.status_code == 200
    assert reponse.json()["passed"] is False
    assert reponse.json()["score"] == 0


def test_en_tete_de_telechargement_gere_les_noms_accentues_et_non_latins() -> None:
    """Un titre « Łukasz — CV » ne doit pas provoquer d'erreur d'encodage d'en-tête HTTP."""
    en_tete = attachment_headers('Łukasz Wójcik "CV" é_v1.pdf')["Content-Disposition"]

    assert en_tete.isascii()
    assert "filename*=UTF-8''" in en_tete
    assert '""' not in en_tete.split(";")[1]
