import httpx

from tests.unit.candidate_profile.extraction.cv_samples import CV_FR


async def _importer(client: httpx.AsyncClient) -> dict:  # type: ignore[type-arg]
    reponse = await client.post(
        "/api/v1/profile/import", files={"fichier": ("cv.txt", CV_FR.encode(), "text/plain")}
    )
    assert reponse.status_code == 200
    return reponse.json()["proposed_document"]  # type: ignore[no-any-return]


def _tout_confirmer(document: dict) -> dict:  # type: ignore[type-arg]
    for cle in ("experiences", "educations", "skills", "languages", "certifications"):
        for element in document[cle]:
            element["validated"] = True
    return document


async def test_aucun_profil_au_depart(client: httpx.AsyncClient) -> None:
    reponse = await client.get("/api/v1/profile")

    assert reponse.status_code == 200
    assert reponse.json() is None


async def test_parcours_complet_import_relecture_validation_nouvelle_version(
    client: httpx.AsyncClient,
) -> None:
    document = await _importer(client)

    # 1. Le brouillon importé est enregistré tel quel : rien n'est validé.
    brouillon = await client.put("/api/v1/profile/draft", json=document)
    assert brouillon.status_code == 200
    corps = brouillon.json()
    assert corps["meta"]["version"] == 1
    assert corps["meta"]["status"] == "draft"
    assert corps["document"]["identity"]["first_name"] == "Marie"
    experience = corps["document"]["experiences"][0]
    assert experience["origin"] == "imported"
    assert experience["validated"] is False
    assert experience["source_text"]
    assert experience["start"] == {"year": 2021, "month": 1}

    # 2. Validation refusée : l'espagnol n'a pas de niveau, rien n'est confirmé.
    refus = await client.post("/api/v1/profile/validate")
    assert refus.status_code == 422
    erreur = refus.json()["error"]
    assert erreur["code"] == "profile_incomplete"
    champs = {d["field"] for d in erreur["details"]}
    assert "experiences[0]" in champs
    assert "skills[0]" in champs

    # 3. Confirmer un élément incomplet est refusé, élément par élément.
    document2 = corps["document"]
    langue_es = next(lg for lg in document2["languages"] if lg["language_code"] == "es")
    langue_es["validated"] = True
    incomplet = await client.put("/api/v1/profile/draft", json=document2)
    assert incomplet.status_code == 422
    assert any("proficiency" in d["field"] for d in incomplet.json()["error"]["details"])

    # 4. L'utilisateur choisit le niveau de l'espagnol, puis confirme tout.
    langue_es["proficiency"] = "a2"
    _tout_confirmer(document2)
    confirme = await client.put("/api/v1/profile/draft", json=document2)
    assert confirme.status_code == 200

    # 5. Validation réussie.
    valide = await client.post("/api/v1/profile/validate")
    assert valide.status_code == 200
    assert valide.json()["meta"]["status"] == "validated"

    # 6. Une version validée n'est pas modifiable directement.
    interdit = await client.put("/api/v1/profile/draft", json=valide.json()["document"])
    assert (interdit.status_code, interdit.json()["error"]["code"]) == (409, "no_draft")

    # 7. Nouvelle version, modifiée ; la version 1 reste intacte.
    v2 = await client.post("/api/v1/profile/versions")
    assert v2.status_code == 201
    doc_v2 = v2.json()["document"]
    doc_v2["summary"] = "Résumé modifié"
    assert (await client.put("/api/v1/profile/draft", json=doc_v2)).status_code == 200
    doublon = await client.post("/api/v1/profile/versions")
    assert (doublon.status_code, doublon.json()["error"]["code"]) == (409, "draft_exists")

    v1 = await client.get("/api/v1/profile/versions/1")
    assert v1.json()["document"]["summary"] != "Résumé modifié"
    versions = await client.get("/api/v1/profile/versions")
    assert [(v["version"], v["status"]) for v in versions.json()] == [
        (2, "draft"),
        (1, "validated"),
    ]

    # 8. Le journal retrace tout.
    historique = (await client.get("/api/v1/profile/history")).json()
    actions = [(h["entity_type"], h["action"]) for h in historique]
    assert ("profile", "import") in actions
    assert ("profile", "validate") in actions
    assert ("summary", "update") in actions


async def test_validation_sans_profil_donne_404(client: httpx.AsyncClient) -> None:
    reponse = await client.post("/api/v1/profile/validate")

    assert (reponse.status_code, reponse.json()["error"]["code"]) == (404, "profile_not_found")


async def test_version_inconnue(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/v1/profile/versions/42")).status_code == 404


async def test_donnees_invalides_refusees_avec_le_champ_en_cause(
    client: httpx.AsyncClient,
) -> None:
    document = {
        "identity": {"email": "pas-un-email"},
        "experiences": [{"start": {"year": 2022}, "end": {"year": 2020}}],
        "preferences": {"salary_min": "45000"},
    }

    reponse = await client.put("/api/v1/profile/draft", json=document)

    assert reponse.status_code == 422
    erreur = reponse.json()["error"]
    assert erreur["code"] == "validation_error"
    champs = {d["field"] for d in erreur["details"]}
    assert "identity.email" in champs
    assert "experiences.0" in champs
    assert "preferences" in champs


async def test_le_client_ne_peut_pas_imposer_le_proprietaire_ni_des_champs_inconnus(
    client: httpx.AsyncClient,
) -> None:
    reponse = await client.put("/api/v1/profile/draft", json={"owner_id": "x"})

    assert reponse.status_code == 422


async def test_identifiant_d_element_inconnu(client: httpx.AsyncClient) -> None:
    await client.put("/api/v1/profile/draft", json={"skills": [{"name": "Python"}]})

    reponse = await client.put(
        "/api/v1/profile/draft",
        json={"skills": [{"id": "00000000-0000-4000-8000-000000000000", "name": "Python"}]},
    )

    assert (reponse.status_code, reponse.json()["error"]["code"]) == (422, "unknown_item")


async def test_preferences_professionnelles_enregistrees(client: httpx.AsyncClient) -> None:
    preferences = {
        "job_titles": ["Data Analyst"],
        "country_codes": ["fr", "BE"],
        "cities": ["Lyon"],
        "remote_types": ["hybrid", "remote"],
        "employment_types": ["permanent"],
        "salary_min": "45000",
        "salary_currency": "eur",
        "application_languages": ["fr", "en"],
    }

    reponse = await client.put("/api/v1/profile/draft", json={"preferences": preferences})

    assert reponse.status_code == 200
    relues = reponse.json()["document"]["preferences"]
    assert relues["country_codes"] == ["FR", "BE"]
    assert relues["salary_currency"] == "EUR"
    assert relues["remote_types"] == ["hybrid", "remote"]
