"""Tests d'intégration des endpoints REST de lettres de motivation (EPIC 013)."""

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

DESCRIPTION = """Nous construisons une plateforme de données de santé.

Vos missions
- Concevoir des API robustes
- Écrire des requêtes SQL

Compétences requises : Python, Docker, Rust
"""

pytestmark = pytest.mark.usefixtures("stockage_isole")
__all__ = ["stockage_isole"]


async def test_sans_profil_valide_renvoie_409(client: httpx.AsyncClient) -> None:
    offre = await creer_offre(client, description=DESCRIPTION)
    reponse = await client.post("/api/v1/cover-letters/generate", json={"offer_id": offre})

    assert reponse.status_code == 409
    assert reponse.json()["error"]["code"] == "no_validated_profile"


async def test_offre_inconnue_renvoie_404(client: httpx.AsyncClient) -> None:
    await initialiser_profil_valide(client)
    reponse = await client.post(
        "/api/v1/cover-letters/generate", json={"offer_id": str(uuid.uuid4())}
    )
    assert reponse.status_code == 404
    assert reponse.json()["error"]["code"] == "offer_not_found"


async def test_langue_non_geree_renvoie_422(client: httpx.AsyncClient) -> None:
    offre = await creer_offre(client, description=DESCRIPTION)
    reponse = await client.post(
        "/api/v1/cover-letters/generate", json={"offer_id": offre, "language": "de"}
    )
    assert reponse.status_code == 422


async def test_cycle_complet_generation_audit_edition_versions(
    client: httpx.AsyncClient,
) -> None:
    profil = await initialiser_profil_valide(client)
    offre = await creer_offre(client, titre="Ingénieure Backend Python", description=DESCRIPTION)

    # 1. Génération : texte, audit et traçabilité sont renvoyés (avant : rien de tout cela)
    generation = await client.post(
        "/api/v1/cover-letters/generate",
        json={
            "offer_id": offre,
            "motivation": "J'apprécie votre approche produit centrée sur les soignants.",
        },
    )
    assert generation.status_code == 201, generation.text
    lettre = generation.json()
    doc_id = lettre["id"]
    assert lettre["kind"] == "cover_letter"
    assert lettre["offer_id"] == offre
    assert lettre["title"] == "Lettre - Ingénieure Backend Python (Doctolib)"

    contenu = lettre["content"]
    assert contenu["subject"] == "Candidature au poste de Ingénieure Backend Python"
    assert contenu["salutation"] == "Madame, Monsieur,"
    assert "Doctolib" in contenu["introduction"]
    assert "J'apprécie votre approche produit" in contenu["added_value"]
    assert contenu["signature"] == (
        f"{profil['identity']['first_name']} {profil['identity']['last_name']}".strip()  # type: ignore[index]
    )

    version = lettre["versions"][0]
    assert version["version"] == 1
    assert version["generation"]["origin"] == "generated"
    assert version["generation"]["prompt_version"]
    audit = version["audit"]
    assert audit["cv_coherent"] is True
    assert audit["page_count"] == 1
    assert audit["generic_phrases_detected"] == []
    assert audit["word_count"] == contenu["word_count"]

    # 2. Le PDF est réel, sur une page, et son texte est sélectionnable
    pdf = await client.get(f"/api/v1/cover-letters/{doc_id}/versions/1/pdf")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    pages = PdfReader(io.BytesIO(pdf.content)).pages
    assert len(pages) == 1
    assert "Madame, Monsieur," in pages[0].extract_text()
    assert "Ingénieure Backend Python" in pages[0].extract_text()

    # 3. Source LaTeX modifiable
    latex = await client.get(f"/api/v1/cover-letters/{doc_id}/versions/1/latex")
    assert latex.status_code == 200
    assert "Objet : Candidature" in latex.text

    # 4. Édition manuelle : réellement auditée (avant : faux score de 85)
    edite = latex.text.replace(
        "Je vous remercie", "Je suis extrêmement motivé et ai dirigé 900 clients. Je vous remercie"
    )
    v2 = await client.post(f"/api/v1/cover-letters/{doc_id}/compile", json={"latex_source": edite})
    assert v2.status_code == 201, v2.text
    audit2 = v2.json()["audit"]
    assert v2.json()["version"] == 2
    assert v2.json()["generation"]["origin"] == "manual_edit"
    assert audit2["passed"] is False
    assert audit2["generic_phrases_detected"] == ["extrêmement motivé"]
    assert audit2["cv_coherent"] is False
    assert audit2["score"] != 85

    # 5. Comparaison, liste, détail
    comparaison = await client.get(
        f"/api/v1/cover-letters/{doc_id}/compare?version_a=1&version_b=2"
    )
    assert comparaison.status_code == 200
    assert "extrêmement motivé" in comparaison.json()["diff_latex"]
    assert comparaison.json()["score_a"] == audit["score"]
    assert comparaison.json()["score_b"] == audit2["score"]

    liste = await client.get(f"/api/v1/cover-letters?offer_id={offre}")
    assert [d["id"] for d in liste.json()] == [doc_id]
    detail = await client.get(f"/api/v1/cover-letters/{doc_id}")
    assert [v["version"] for v in detail.json()["versions"]] == [1, 2]


async def test_lettre_anglaise_style_britannique(client: httpx.AsyncClient) -> None:
    await initialiser_profil_valide(client)
    offre = await creer_offre(client, description=DESCRIPTION, pays="GB")

    reponse = await client.post(
        "/api/v1/cover-letters/generate", json={"offer_id": offre, "language": "en"}
    )
    assert reponse.status_code == 201, reponse.text
    contenu = reponse.json()["content"]

    assert contenu["salutation"] == "Dear Sir or Madam,"  # pays pris dans l'offre
    assert contenu["complimentary_close"] == "Yours faithfully,"
    assert contenu["subject"].startswith("Application for the position of")


async def test_un_cv_n_est_pas_accessible_comme_une_lettre(client: httpx.AsyncClient) -> None:
    await initialiser_profil_valide(client)
    cv = await client.post("/api/v1/resumes/generate", json={})
    assert cv.status_code == 201, cv.text
    cv_id = cv.json()["id"]

    assert (await client.get(f"/api/v1/cover-letters/{cv_id}")).status_code == 404
    assert (await client.get(f"/api/v1/cover-letters/{cv_id}/versions/1/pdf")).status_code == 404
    assert (
        await client.post(
            f"/api/v1/cover-letters/{cv_id}/compile",
            json={"latex_source": "\\documentclass{article}\\begin{document}x\\end{document}"},
        )
    ).status_code == 404
    assert (await client.get(f"/api/v1/resumes/{cv_id}")).status_code == 200


async def test_source_dangereuse_refusee(client: httpx.AsyncClient) -> None:
    await initialiser_profil_valide(client)
    offre = await creer_offre(client, description=DESCRIPTION)
    doc_id = (await client.post("/api/v1/cover-letters/generate", json={"offer_id": offre})).json()[
        "id"
    ]

    reponse = await client.post(
        f"/api/v1/cover-letters/{doc_id}/compile",
        json={
            "latex_source": "\\documentclass{article}\\begin{document}"
            "\\input{/etc/passwd}\\end{document}"
        },
    )
    assert reponse.status_code == 422
    assert "interdit" in reponse.json()["error"]["message"]
    versions = (await client.get(f"/api/v1/cover-letters/{doc_id}")).json()["versions"]
    assert len(versions) == 1


async def test_ressources_inconnues_renvoient_404(client: httpx.AsyncClient) -> None:
    inconnu = uuid.uuid4()
    assert (await client.get(f"/api/v1/cover-letters/{inconnu}")).status_code == 404
    assert (
        await client.get(f"/api/v1/cover-letters/{inconnu}/versions/1/latex")
    ).status_code == 404
