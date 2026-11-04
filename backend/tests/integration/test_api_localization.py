"""Préférences générales et référentiel géographique via l'API (vraie base PostgreSQL)."""

import httpx

PREFS = {
    "ui_language": "en",
    "country_code": "ca",
    "currency": "cad",
    "timezone": "America/Toronto",
    "willing_to_relocate": True,
    "target_countries": ["fr", "de"],
    "work_permit_countries": ["CA"],
    "needs_sponsorship": False,
}


async def test_par_defaut_rien_n_est_renseigne(client: httpx.AsyncClient) -> None:
    corps = (await client.get("/api/v1/preferences")).json()

    assert corps["ui_language"] == "fr"
    assert corps["country_code"] is None and corps["currency"] is None
    assert corps["willing_to_relocate"] is None and corps["needs_sponsorship"] is None
    assert corps["supported_ui_languages"] == ["fr", "en"]


async def test_enregistre_normalise_puis_relit(client: httpx.AsyncClient) -> None:
    ecriture = await client.put("/api/v1/preferences", json=PREFS)
    relu = (await client.get("/api/v1/preferences")).json()

    assert ecriture.status_code == 200
    assert relu["country_code"] == "CA" and relu["currency"] == "CAD"
    assert relu["target_countries"] == ["FR", "DE"]
    assert relu["needs_sponsorship"] is False and relu["willing_to_relocate"] is True


async def test_une_seconde_ecriture_remplace_la_premiere(client: httpx.AsyncClient) -> None:
    await client.put("/api/v1/preferences", json=PREFS)
    await client.put("/api/v1/preferences", json={"ui_language": "fr"})

    relu = (await client.get("/api/v1/preferences")).json()

    assert relu["ui_language"] == "fr" and relu["country_code"] is None
    assert relu["target_countries"] == []


async def test_refuse_les_valeurs_hors_referentiel_avec_un_message_clair(
    client: httpx.AsyncClient,
) -> None:
    for corps, extrait in (
        ({"ui_language": "de"}, "Langue d'interface"),
        ({"ui_language": "fr", "country_code": "ZZ"}, "Pays inconnu"),
        ({"ui_language": "fr", "currency": "ABC"}, "Devise inconnue"),
        ({"ui_language": "fr", "timezone": "Mars/Olympus"}, "Fuseau horaire inconnu"),
    ):
        reponse = await client.put("/api/v1/preferences", json=corps)

        assert reponse.status_code == 422
        assert reponse.json()["error"]["code"] == "preferences_invalid"
        assert extrait in reponse.json()["error"]["message"]


async def test_le_referentiel_est_expose_dans_les_deux_langues(client: httpx.AsyncClient) -> None:
    fr = (await client.get("/api/v1/reference/countries")).json()
    en = (await client.get("/api/v1/reference/countries?locale=en")).json()
    devises = (await client.get("/api/v1/reference/currencies?locale=en")).json()
    fuseaux = (await client.get("/api/v1/reference/timezones")).json()
    refuse = await client.get("/api/v1/reference/countries?locale=de")

    assert {"code": "CH", "name": "Suisse"}.items() <= next(
        c for c in fr if c["code"] == "CH"
    ).items()
    assert next(c for c in en if c["code"] == "CH")["name"] == "Switzerland"
    assert any(d["code"] == "EUR" for d in devises)
    assert "Europe/Paris" in fuseaux
    assert refuse.status_code == 422
