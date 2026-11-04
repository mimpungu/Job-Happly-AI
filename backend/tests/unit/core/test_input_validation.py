"""Garde-fou « toute entrée est bornée » (TASK-018-03).

Parcourt le schéma OpenAPI réel : une chaîne, une liste ou un objet libre sans borne dans le
corps d'une requête fait échouer la CI. Les exceptions sont listées avec leur justification : une
nouvelle exception doit être un choix explicite, jamais un oubli.
"""

from typing import Any

from fastapi.testclient import TestClient

from app.main import app

# « Modèle.champ » -> pourquoi c'est acceptable.
_VALIDE_PAR_LE_DOMAINE = (
    "validé par un validateur de domaine qui impose la borne (longueur, code ISO ou énumération)"
)
_ALLOWLIST: dict[str, str] = {
    "Body_audit_ats_api_v1_resumes_audit_ats_post.file": "fichier : taille bornée par la route",
    "Body_import_cv_api_v1_profile_import_post.fichier": "fichier : 10 Mo + contrôle du contenu",
    "Identity.country_code": _VALIDE_PAR_LE_DOMAINE,
    "LanguageDoc.language_code": _VALIDE_PAR_LE_DOMAINE,
    "ExperienceDoc.achievements": "chaque réalisation limitée à 500 caractères par validateur",
    "Preferences-Input.job_titles": "100 caractères par validateur",
    "Preferences-Input.cities": "100 caractères par validateur",
    "Preferences-Input.country_codes": _VALIDE_PAR_LE_DOMAINE,
    "Preferences-Input.application_languages": _VALIDE_PAR_LE_DOMAINE,
    "Preferences-Input.salary_currency": _VALIDE_PAR_LE_DOMAINE,
    "Preferences-Input.remote_types": "énumération fermée, valeurs distinctes",
    "Preferences-Input.employment_types": "énumération fermée, valeurs distinctes",
    "OfferFilter-Input.country_codes": _VALIDE_PAR_LE_DOMAINE,
    "OfferFilter-Input.salary_currency": _VALIDE_PAR_LE_DOMAINE,
    "OfferFilter-Input.language": _VALIDE_PAR_LE_DOMAINE,
    "OfferFilter-Input.remote_types": "énumération fermée",
    "OfferFilter-Input.employment_types": "énumération fermée",
    "OfferFilter-Input.statuses": "énumération fermée",
    "ScheduledTaskCreateRequest.payload": "taille limitée à 4 Ko par validateur",
    "ScheduledTaskUpdateRequest.payload": "taille limitée à 4 Ko par validateur",
    "WeightsBody.weights": "50 entrées maximum, nombres stricts, clés vérifiées par le service",
}


def _corps_de_requete(spec: dict[str, Any]) -> set[str]:
    noms: set[str] = set()
    for chemins in spec["paths"].values():
        for operation in chemins.values():
            for contenu in operation.get("requestBody", {}).get("content", {}).values():
                reference = contenu["schema"].get("$ref")
                if reference:
                    noms.add(reference.rsplit("/", 1)[-1])
    return noms


def _borne_numerique(propriete: dict[str, Any]) -> bool:
    """Un Decimal est publié « nombre ou chaîne » ; la borne se trouve sur la branche nombre."""
    branches = [propriete, *propriete.get("anyOf", [])]
    return any("maximum" in b or "exclusiveMaximum" in b for b in branches)


def _anomalies(schemas: dict[str, Any], nom: str, vus: set[str]) -> list[str]:
    if nom in vus:
        return []
    vus.add(nom)
    trouvees: list[str] = []

    def verifier(propriete: dict[str, Any], champ: str, numerique_borne: bool = False) -> None:
        cle = f"{nom}.{champ}"
        numerique_borne = numerique_borne or _borne_numerique(propriete)
        if "$ref" in propriete:
            trouvees.extend(_anomalies(schemas, propriete["$ref"].rsplit("/", 1)[-1], vus))
            return
        for sous in (*propriete.get("anyOf", []), *propriete.get("oneOf", [])):
            verifier(sous, champ, numerique_borne)
        genre = propriete.get("type")
        sans_borne_texte = (
            "maxLength" not in propriete
            and "enum" not in propriete
            and "pattern" not in propriete
            and propriete.get("format") not in {"uuid", "date-time", "date", "uri"}
        )
        if genre == "string" and sans_borne_texte and not numerique_borne:
            trouvees.append(f"{cle}: chaîne sans maxLength")
        if genre == "array":
            if "maxItems" not in propriete:
                trouvees.append(f"{cle}: liste sans maxItems")
            elements = propriete.get("items", {})
            if "$ref" in elements:
                trouvees.extend(_anomalies(schemas, elements["$ref"].rsplit("/", 1)[-1], vus))
            elif (
                elements.get("type") == "string"
                and "maxLength" not in elements
                and ("enum" not in elements)
            ):
                trouvees.append(f"{cle}: éléments texte sans maxLength")
        libre = genre == "object" and "properties" not in propriete
        if libre and propriete.get("additionalProperties") is not False:
            trouvees.append(f"{cle}: objet libre")

    for champ, propriete in schemas[nom].get("properties", {}).items():
        verifier(propriete, champ)
    return trouvees


def test_toute_entree_de_l_api_est_bornee() -> None:
    spec = TestClient(app).get("/openapi.json").json()
    schemas = spec["components"]["schemas"]
    vus: set[str] = set()
    anomalies = [
        a for nom in sorted(_corps_de_requete(spec)) for a in _anomalies(schemas, nom, vus)
    ]

    non_justifiees = [a for a in anomalies if a.split(":")[0] not in _ALLOWLIST]

    assert vus, "aucun schéma de requête analysé : le garde-fou ne vérifie plus rien"
    assert non_justifiees == [], (
        "Entrées non bornées : ajoutez maxLength / maxItems ou justifiez l'exception."
    )


def test_les_exceptions_justifiees_existent_encore() -> None:
    """Une exception qui ne correspond plus à rien est supprimée : la liste reste honnête."""
    spec = TestClient(app).get("/openapi.json").json()
    schemas = spec["components"]["schemas"]
    vus: set[str] = set()
    anomalies = {
        a.split(":")[0] for nom in _corps_de_requete(spec) for a in _anomalies(schemas, nom, vus)
    }

    perimees = sorted(set(_ALLOWLIST) - anomalies)

    assert perimees == [], f"Exceptions obsolètes à retirer : {perimees}"
