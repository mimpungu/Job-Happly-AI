"""Éléments partagés par les tests d'intégration des CV et des lettres (EPIC 012 et 013)."""

import uuid
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from app.core.config import get_settings
from tests.unit.candidate_profile.extraction.cv_samples import CV_FR


@pytest.fixture
def stockage_isole(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Les PDF de test ne doivent pas polluer le dossier de stockage réel."""
    monkeypatch.setenv("HAPPLY_STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def initialiser_profil_valide(client: httpx.AsyncClient) -> dict[str, object]:
    """Importe puis valide un profil maître ; retourne le document validé."""
    importation = await client.post(
        "/api/v1/profile/import", files={"fichier": ("cv.txt", CV_FR.encode(), "text/plain")}
    )
    assert importation.status_code == 200
    document = importation.json()["proposed_document"]

    for cle in ("experiences", "educations", "skills", "languages", "certifications"):
        for element in document[cle]:
            element["validated"] = True
    for langue in document["languages"]:
        langue["proficiency"] = langue["proficiency"] or "b2"  # niveau requis pour confirmer

    brouillon = await client.put("/api/v1/profile/draft", json=document)
    assert brouillon.status_code == 200
    validation = await client.post("/api/v1/profile/validate")
    assert validation.status_code == 200
    return document  # type: ignore[no-any-return]


async def creer_offre(
    client: httpx.AsyncClient,
    *,
    titre: str = "Développeur Python",
    entreprise: str | None = "Doctolib",
    description: str,
    pays: str | None = "FR",
) -> str:
    """Ajoute une offre manuelle ; retourne son identifiant."""
    corps: dict[str, object] = {
        "title": titre,
        "description": description,
        "application_url": f"https://exemple.test/offre/{uuid.uuid4()}",
        "location": "Paris, France",
    }
    if entreprise:
        corps["company_name"] = entreprise
    if pays:
        corps["country_code"] = pays
    reponse = await client.post("/api/v1/offers/manual", json=corps)
    assert reponse.status_code == 201, reponse.text
    return str(reponse.json()["offer_id"])
