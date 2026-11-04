import httpx
import pytest

from app.main import create_app
from app.modules.candidate_profile.domain.documents import MAX_UPLOAD_BYTES

from .builders import make_docx, make_pdf, make_pdf_positioned, paragraphe
from .extraction.cv_samples import CV_FR


@pytest.fixture
async def client():  # type: ignore[no-untyped-def]
    transport = httpx.ASGITransport(app=create_app(), raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as c:
        yield c


def _envoyer(client: httpx.AsyncClient, nom: str, contenu: bytes, type_mime: str = "text/plain"):  # type: ignore[no-untyped-def]
    return client.post("/api/v1/profile/import", files={"fichier": (nom, contenu, type_mime)})


async def test_import_txt_retourne_texte_et_profil_propose(client: httpx.AsyncClient) -> None:
    reponse = await _envoyer(client, "mon cv.txt", CV_FR.encode())

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["format"] == "txt"
    assert corps["filename"] == "mon cv.txt"
    assert corps["proposed_profile"]["contact"]["email"] == "marie.dupont@exemple.test"
    assert len(corps["proposed_profile"]["experiences"]) == 2
    assert corps["proposed_profile"]["experiences"][0]["start"] == {"year": 2021, "month": 1}


async def test_import_pdf_et_docx(client: httpx.AsyncClient) -> None:
    pdf = make_pdf([["Marie Dupont", "marie@exemple.test", "Developpeuse Python confirmee"]])
    docx = make_docx(paragraphe("Marie Dupont") + paragraphe("marie@exemple.test, développeuse"))

    r_pdf = await _envoyer(client, "cv.pdf", pdf, "application/pdf")
    r_docx = await _envoyer(client, "cv.docx", docx, "application/octet-stream")

    assert r_pdf.status_code == r_docx.status_code == 200
    assert r_pdf.json()["page_count"] == 1
    assert r_docx.json()["proposed_profile"]["contact"]["email"] == "marie@exemple.test"


async def test_le_nom_renvoye_est_assaini(client: httpx.AsyncClient) -> None:
    traversee = await _envoyer(client, "../../etc/passwd.txt", CV_FR.encode())
    balise = await _envoyer(client, "cv<script>.txt", CV_FR.encode())

    assert traversee.json()["filename"] == "passwd.txt"
    assert balise.json()["filename"] == "cv_script_.txt"


async def test_fichier_trop_gros_refuse_en_413_sans_tout_charger(client: httpx.AsyncClient) -> None:
    reponse = await _envoyer(client, "cv.txt", b"a" * (MAX_UPLOAD_BYTES + 1))

    assert reponse.status_code == 413
    assert reponse.json()["error"]["code"] == "document_error"


@pytest.mark.parametrize(
    ("nom", "contenu", "statut"),
    [
        ("cv.exe", b"MZ\x90\x00texte", 415),
        ("cv.pdf", b"juste du texte", 415),
        ("cv.pdf", b"%PDF-1.4 abime", 422),
        ("cv.txt", b"   ", 422),
        ("cv.txt", b"", 422),
    ],
)
async def test_erreurs_de_document_avec_messages_clairs(
    client: httpx.AsyncClient, nom: str, contenu: bytes, statut: int
) -> None:
    reponse = await _envoyer(client, nom, contenu)

    assert reponse.status_code == statut
    erreur = reponse.json()["error"]
    assert erreur["code"] == "document_error"
    assert "Traceback" not in reponse.text
    assert erreur["message"]


async def test_champ_fichier_manquant(client: httpx.AsyncClient) -> None:
    reponse = await client.post("/api/v1/profile/import")

    assert reponse.status_code == 422
    assert reponse.json()["error"]["code"] == "validation_error"


async def test_le_texte_renvoye_ne_contient_aucun_marqueur_interne(
    client: httpx.AsyncClient,
) -> None:
    from .test_coupures_de_ligne import _DROITE, _GAUCHE, _colonne

    fragments = [
        *((int(f.x), int(f.y), f.text) for f in _colonne(40, _GAUCHE)),
        *((int(f.x), int(f.y), f.text) for f in _colonne(272, _DROITE)),
    ]

    reponse = await _envoyer(client, "cv.pdf", make_pdf_positioned(fragments), "application/pdf")

    corps = reponse.json()
    assert reponse.status_code == 200
    assert "￻" not in corps["text"] and "￼" not in corps["text"]
    assert "Wmware" in corps["text"]
    noms = [c["name"] for c in corps["proposed_profile"]["skills"]]
    assert "Wmware Fusion" in noms
