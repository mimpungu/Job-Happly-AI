"""Tests d'intégration des endpoints REST de génération de CV LaTeX (EPIC 012)."""

import httpx

from tests.unit.candidate_profile.extraction.cv_samples import CV_FR


async def _initialiser_profil(client: httpx.AsyncClient) -> None:
    """Importe et valide un profil pour le candidat de test."""
    reponse_import = await client.post(
        "/api/v1/profile/import", files={"fichier": ("cv.txt", CV_FR.encode(), "text/plain")}
    )
    assert reponse_import.status_code == 200
    doc = reponse_import.json()["proposed_document"]

    # Confirmation de tous les éléments
    for cle in ("experiences", "educations", "skills", "languages", "certifications"):
        for elem in doc[cle]:
            elem["validated"] = True
    for lg in doc["languages"]:
        lg["level_text"] = "Courant"

    res_draft = await client.put("/api/v1/profile/draft", json=doc)
    assert res_draft.status_code == 200

    res_val = await client.post("/api/v1/profile/validate")
    assert res_val.status_code == 200


async def test_generation_sans_profil_renvoie_400(client: httpx.AsyncClient) -> None:
    reponse = await client.post("/api/v1/resumes/generate", json={"title": "Mon CV"})
    assert reponse.status_code == 400
    assert "Aucun profil candidat trouvé" in reponse.json()["error"]["message"]


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
