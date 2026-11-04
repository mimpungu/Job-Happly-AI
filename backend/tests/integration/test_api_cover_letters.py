"""Tests d'intégration des endpoints REST de génération de lettres de motivation (EPIC 013)."""

import httpx

from tests.unit.candidate_profile.extraction.cv_samples import CV_FR


async def _initialiser_profil(client: httpx.AsyncClient) -> None:
    """Importe et valide un profil pour le candidat de test."""
    reponse_import = await client.post(
        "/api/v1/profile/import", files={"fichier": ("cv.txt", CV_FR.encode(), "text/plain")}
    )
    assert reponse_import.status_code == 200
    doc = reponse_import.json()["proposed_document"]

    for cle in ("experiences", "educations", "skills", "languages", "certifications"):
        for elem in doc[cle]:
            elem["validated"] = True
    for lg in doc["languages"]:
        lg["level_text"] = "Courant"

    res_draft = await client.put("/api/v1/profile/draft", json=doc)
    assert res_draft.status_code == 200

    res_val = await client.post("/api/v1/profile/validate")
    assert res_val.status_code == 200


async def _creer_offre(client: httpx.AsyncClient) -> str:
    """Crée une offre manuelle de test et retourne son ID."""
    offre_body = {
        "title": "Ingénieure Backend Python",
        "company_name": "Doctolib",
        "description": "Nous recherchons un ingénieur backend pour concevoir des APIs.",
        "location": "Paris, France",
        "country_code": "FR",
        "application_url": "https://careers.doctolib.fr/jobs/123",
    }
    res = await client.post("/api/v1/manual-offers", json=offre_body)
    assert res.status_code == 201
    return str(res.json()["id"])


async def test_generation_lettre_cycle_complet(client: httpx.AsyncClient) -> None:
    await _initialiser_profil(client)
    offer_id = await _creer_offre(client)

    # 1. Génération de la lettre de motivation (version 1)
    gen_res = await client.post(
        "/api/v1/cover-letters/generate",
        json={
            "offer_id": offer_id,
            "language": "fr",
            "recipient_department": "Équipe Plateforme",
        },
    )
    assert gen_res.status_code == 201
    doc_data = gen_res.json()
    doc_id = doc_data["id"]
    assert doc_data["kind"] == "cover_letter"
    assert "Doctolib" in doc_data["title"]
    assert len(doc_data["versions"]) == 1
    assert doc_data["versions"][0]["version"] == 1

    # 2. Consultation de la liste et du détail
    list_res = await client.get("/api/v1/cover-letters")
    assert list_res.status_code == 200
    assert any(d["id"] == doc_id for d in list_res.json())

    detail_res = await client.get(f"/api/v1/cover-letters/{doc_id}")
    assert detail_res.status_code == 200
    assert detail_res.json()["id"] == doc_id

    # 3. Téléchargement du LaTeX (TASK-013-14)
    latex_res = await client.get(f"/api/v1/cover-letters/{doc_id}/versions/1/latex")
    assert latex_res.status_code == 200
    assert "Doctolib" in latex_res.text
    assert "Objet" in latex_res.text

    # 4. Téléchargement du PDF réel (TASK-013-13)
    pdf_res = await client.get(f"/api/v1/cover-letters/{doc_id}/versions/1/pdf")
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"
    assert pdf_res.content.startswith(b"%PDF-")

    # 5. Compilation d'une version 2 manuelle (TASK-013-14, 15)
    source_v2 = latex_res.text + "\n% Version 2 modifiee manuellement"
    compile_res = await client.post(
        f"/api/v1/cover-letters/{doc_id}/compile",
        json={"latex_source": source_v2},
    )
    assert compile_res.status_code == 201
    assert compile_res.json()["version"] == 2

    # 6. Comparaison des versions (TASK-013-15)
    comp_res = await client.get(f"/api/v1/cover-letters/{doc_id}/compare?version_a=1&version_b=2")
    assert comp_res.status_code == 200
    comp_data = comp_res.json()
    assert comp_data["version_a"] == 1
    assert comp_data["version_b"] == 2
    assert "+% Version 2 modifiee manuellement" in comp_data["diff_latex"]
