"""Tests d'intégration des endpoints REST de génération de CV LaTeX (EPIC 012)."""

import io
import uuid

import httpx
import pytest
from pypdf import PdfReader

from tests.integration.documents_support import (
    creer_offre,
    initialiser_profil_valide,
    stockage_isole,
)
from tests.unit.candidate_profile.extraction.cv_samples import CV_FR

DESCRIPTION_OFFRE = """Nous construisons une plateforme de données.

Compétences requises
- Python
- Docker
- Rust
"""

_initialiser_profil = initialiser_profil_valide
pytestmark = pytest.mark.usefixtures("stockage_isole")
__all__ = ["stockage_isole"]


async def test_generation_sans_profil_renvoie_409(client: httpx.AsyncClient) -> None:
    reponse = await client.post("/api/v1/resumes/generate", json={"title": "Mon CV"})
    assert reponse.status_code == 409
    assert reponse.json()["error"]["code"] == "no_validated_profile"


async def test_un_profil_en_brouillon_ne_suffit_pas(client: httpx.AsyncClient) -> None:
    """Seules des données confirmées par l'utilisateur peuvent finir dans un CV."""
    imp = await client.post(
        "/api/v1/profile/import", files={"fichier": ("cv.txt", CV_FR.encode(), "text/plain")}
    )
    assert imp.status_code == 200  # un brouillon existe, mais il n'est pas validé

    reponse = await client.post("/api/v1/resumes/generate", json={})
    assert reponse.status_code == 409


async def test_offre_inconnue_renvoie_404(client: httpx.AsyncClient) -> None:
    await _initialiser_profil(client)
    reponse = await client.post("/api/v1/resumes/generate", json={"offer_id": str(uuid.uuid4())})
    assert reponse.status_code == 404
    assert reponse.json()["error"]["code"] == "offer_not_found"


async def test_ciblage_sur_une_offre_analysee(client: httpx.AsyncClient) -> None:
    """Les compétences de l'analyse (EPIC 011) pilotent le CV ; une absente n'est jamais ajoutée."""
    await _initialiser_profil(client)
    offre_id = await creer_offre(client, description=DESCRIPTION_OFFRE)
    analyse = (await client.get(f"/api/v1/offers/{offre_id}/analysis")).json()["analysis"]
    assert {"Python", "Docker", "Rust"} <= set(
        analyse["mandatory_skills"] + analyse["technologies"]
    )

    generation = await client.post(
        "/api/v1/resumes/generate", json={"offer_id": offre_id, "length_target": "one_page"}
    )
    assert generation.status_code == 201
    doc = generation.json()
    assert doc["offer_id"] == offre_id
    assert doc["title"] == "CV - Développeur Python"
    version = doc["versions"][0]
    assert version["generation"]["origin"] == "generated"
    assert version["generation"]["prompt_version"]

    rapport = version["ats_report"]
    assert "Rust" in rapport["keywords_missing"]  # signalé, pas inventé
    assert "Python" in rapport["keywords_found"]

    latex = (await client.get(f"/api/v1/resumes/{doc['id']}/versions/1/latex")).text
    assert "Rust" not in latex

    filtre = (await client.get(f"/api/v1/resumes?offer_id={offre_id}")).json()
    assert [d["id"] for d in filtre] == [doc["id"]]


async def test_cycle_complet_generation_versionnage_export_et_comparaison(
    client: httpx.AsyncClient,
) -> None:
    # 1. Initialisation du profil maître
    await _initialiser_profil(client)

    # 2. Génération du premier CV (version 1)
    gen_res = await client.post(
        "/api/v1/resumes/generate",
        json={
            "title": "CV Lead Développeuse",
            "target_role": "Lead Tech Python",
            "length_target": "one_page",
        },
    )
    assert gen_res.status_code == 201
    doc_data = gen_res.json()
    doc_id = doc_data["id"]
    assert doc_data["kind"] == "cv"
    assert doc_data["title"] == "CV Lead Développeuse"
    assert len(doc_data["versions"]) == 1
    assert doc_data["versions"][0]["version"] == 1
    assert doc_data["versions"][0]["ats_report"]["passed"] is True

    # 3. Consultation du détail du document et de la liste
    list_res = await client.get("/api/v1/resumes")
    assert list_res.status_code == 200
    assert any(d["id"] == doc_id for d in list_res.json())

    detail_res = await client.get(f"/api/v1/resumes/{doc_id}")
    assert detail_res.status_code == 200
    assert detail_res.json()["id"] == doc_id

    # 4. Téléchargement du code source LaTeX (TASK-012-25)
    latex_res = await client.get(f"/api/v1/resumes/{doc_id}/versions/1/latex")
    assert latex_res.status_code == 200
    assert "documentclass" in latex_res.text
    assert "Lead Tech Python" in latex_res.text

    # 5. Téléchargement du binaire PDF réel (TASK-012-24)
    pdf_res = await client.get(f"/api/v1/resumes/{doc_id}/versions/1/pdf")
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"
    assert pdf_res.content.startswith(b"%PDF-")
    texte = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf_res.content)).pages)
    assert "Lead Tech Python" in texte  # texte réellement sélectionnable

    # 6. Compilation d'une version 2 manuelle (TASK-012-22)
    source_modifiee = latex_res.text + "\n% Version 2 modifiee manuellement"
    compile_res = await client.post(
        f"/api/v1/resumes/{doc_id}/compile",
        json={"latex_source": source_modifiee},
    )
    assert compile_res.status_code == 201
    v2_data = compile_res.json()
    assert v2_data["version"] == 2

    # 7. Comparaison des versions (TASK-012-26)
    comp_res = await client.get(f"/api/v1/resumes/{doc_id}/compare?version_a=1&version_b=2")
    assert comp_res.status_code == 200
    comp_data = comp_res.json()
    assert comp_data["version_a"] == 1
    assert comp_data["version_b"] == 2
    assert "+% Version 2 modifiee manuellement" in comp_data["diff_latex"]

    # 7 bis. Ressources inconnues : 404 normalisés, pas de 500
    inconnu = uuid.uuid4()
    assert (await client.get(f"/api/v1/resumes/{inconnu}")).status_code == 404
    assert (await client.get(f"/api/v1/resumes/{doc_id}/versions/9/pdf")).status_code == 404
    assert (
        await client.get(f"/api/v1/resumes/{doc_id}/compare?version_a=1&version_b=9")
    ).status_code == 404
    assert (
        await client.post(
            f"/api/v1/resumes/{inconnu}/compile", json={"latex_source": source_modifiee}
        )
    ).status_code == 404

    # 8. Audit ATS direct du PDF (TASK-012-17 à 21)
    audit_res = await client.post(
        "/api/v1/resumes/audit-ats",
        files={"file": ("mon_cv.pdf", pdf_res.content, "application/pdf")},
    )
    assert audit_res.status_code == 200
    audit_data = audit_res.json()
    assert audit_data["passed"] is True
    assert audit_data["score"] >= 75
    assert audit_data["page_count"] >= 1


async def test_source_latex_dangereuse_refusee_en_422(client: httpx.AsyncClient) -> None:
    """Une source éditée ne peut ni lire de fichier ni exécuter de commande (CLAUDE.md §11)."""
    await _initialiser_profil(client)
    doc_id = (await client.post("/api/v1/resumes/generate", json={})).json()["id"]

    for source in (
        "\\documentclass{article}\\begin{document}\\input{/etc/passwd}\\end{document}",
        "\\documentclass{article}\\begin{document}\\immediate\\write18{id}\\end{document}",
    ):
        reponse = await client.post(
            f"/api/v1/resumes/{doc_id}/compile", json={"latex_source": source}
        )
        assert reponse.status_code == 422
        assert reponse.json()["error"]["code"] == "latex_compilation"
        assert "interdit" in reponse.json()["error"]["message"]

    versions = (await client.get(f"/api/v1/resumes/{doc_id}")).json()["versions"]
    assert len(versions) == 1  # rien n'a été enregistré


async def test_source_latex_invalide_renvoie_422_sans_trace(client: httpx.AsyncClient) -> None:
    await _initialiser_profil(client)
    doc_id = (await client.post("/api/v1/resumes/generate", json={})).json()["id"]

    reponse = await client.post(
        f"/api/v1/resumes/{doc_id}/compile",
        json={"latex_source": "\\documentclass{article}\\begin{document}\\boum\\end{document}"},
    )
    assert reponse.status_code == 422
    assert "Traceback" not in reponse.text
