"""Ajout manuel d'une offre : base PostgreSQL réelle, aucune requête vers le site d'origine."""

import httpx

DESCRIPTION = (
    "Vous rejoignez la direction des systèmes d'information pour développer des applications "
    "Java et Python au service des métiers de la banque de détail."
)
CORPS = {
    "title": "Développeur Java H/F",
    "company_name": "BNP Paribas",
    "location": "Paris, France",
    "description": DESCRIPTION,
    "application_url": "https://group.bnpparibas/emploi-carriere/offre/123",
}


async def test_ajoute_une_offre_retrouvable_par_entreprise_et_ville(
    client: httpx.AsyncClient,
) -> None:
    reponse = await client.post("/api/v1/offers/manual", json=CORPS)

    assert reponse.status_code == 201
    assert reponse.json()["created"] is True and reponse.json()["already_known"] is False
    trouvees = await client.get(
        "/api/v1/offers", params={"company": "BNP Paribas", "city": "Paris"}
    )
    offre = trouvees.json()["items"][0]
    assert offre["title"] == "Développeur Java"  # même normalisation que les offres collectées
    assert offre["source_keys"] == ["manual"]
    detail = await client.get(f"/api/v1/offers/{reponse.json()['offer_id']}")
    assert detail.json()["sources"][0]["source_name"] == "Saisie manuelle"


async def test_saisir_deux_fois_la_meme_adresse_ne_cree_pas_de_doublon(
    client: httpx.AsyncClient,
) -> None:
    premiere = await client.post("/api/v1/offers/manual", json=CORPS)
    seconde = await client.post(
        "/api/v1/offers/manual",
        json={**CORPS, "application_url": CORPS["application_url"] + "/#postuler"},
    )

    assert seconde.json()["already_known"] is True
    assert seconde.json()["offer_id"] == premiere.json()["offer_id"]
    liste = await client.get("/api/v1/offers", params={"company": "BNP Paribas"})
    assert liste.json()["total"] == 1


async def test_refuse_une_saisie_invalide_avec_un_message_clair(client: httpx.AsyncClient) -> None:
    http = await client.post(
        "/api/v1/offers/manual", json={**CORPS, "application_url": "http://group.bnpparibas/o/1"}
    )
    courte = await client.post("/api/v1/offers/manual", json={**CORPS, "description": "trop court"})
    inconnu = await client.post("/api/v1/offers/manual", json={**CORPS, "champ": 1})

    assert http.status_code == 422
    assert http.json()["error"]["code"] == "manual_offer_invalid"
    assert "https://" in http.json()["error"]["message"]
    assert courte.status_code == 422 and inconnu.status_code == 422


async def test_l_offre_manuelle_est_scorable_et_sauvegardable(client: httpx.AsyncClient) -> None:
    offre = (await client.post("/api/v1/offers/manual", json=CORPS)).json()["offer_id"]

    sauvegarde = await client.put(f"/api/v1/offers/{offre}/state", json={"state": "saved"})

    assert sauvegarde.status_code == 204
