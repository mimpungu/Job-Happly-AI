"""Tests unitaires de l'endpoint d'audit ATS (TASK-012-17 à 21)."""

import httpx
import pytest

from app.main import create_app
from app.modules.document_generation.infrastructure.latex_compiler import (
    IsolatedLaTeXCompiler,
)


@pytest.fixture
async def client():  # type: ignore[no-untyped-def]
    transport = httpx.ASGITransport(app=create_app(), raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as c:
        yield c


async def test_audit_ats_endpoint_sur_pdf_reel(client: httpx.AsyncClient) -> None:
    compiler = IsolatedLaTeXCompiler()
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
