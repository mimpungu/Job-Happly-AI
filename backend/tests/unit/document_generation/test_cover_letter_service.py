"""CoverLetterService : génération factuelle, audit réel, versions, nettoyage (EPIC 013)."""

import uuid
from datetime import date
from typing import Any

import pytest

from app.modules.document_generation.application.cover_letter_service import CoverLetterService
from app.modules.document_generation.application.ports import (
    DocumentNotFoundError,
    LaTeXCompilerPort,
    NoValidatedProfileError,
    OfferContext,
    OfferNotFoundError,
)
from app.modules.document_generation.domain.cover_letter_models import (
    CoverLetterOptions,
    IncompleteProfileError,
)
from app.modules.document_generation.domain.cover_letter_prompts import (
    COVER_LETTER_PROMPT_VERSION,
)
from app.modules.document_generation.domain.enums import DocumentKind
from app.modules.document_generation.domain.fact_checker import UnverifiedFactError
from app.modules.document_generation.infrastructure.models import DocumentVersionModel
from tests.unit.document_generation.cover_letter_samples import (
    AUJOURDHUI,
    DESCRIPTION_OFFRE,
    profil_alice,
)
from tests.unit.document_generation.test_resume_service import (
    DummyCompiler,
    FakeInputs,
    InMemoryRepository,
    InMemoryStorage,
)

OFFRE = OfferContext(
    title="Développeur Python Backend",
    company="Doctolib",
    description=DESCRIPTION_OFFRE,
    required_skills=("Python", "FastAPI", "Rust"),
    location="Paris",
    country_code="FR",
)


def _service(
    compiler: LaTeXCompilerPort,
    *,
    offre_id: uuid.UUID,
    profil: Any = "defaut",
    repo: InMemoryRepository | None = None,
    storage: InMemoryStorage | None = None,
    offre: OfferContext = OFFRE,
) -> CoverLetterService:
    return CoverLetterService(
        repository=repo or InMemoryRepository(),
        storage=storage or InMemoryStorage(),
        compiler=compiler,
        inputs=FakeInputs(profil_alice() if profil == "defaut" else profil, {offre_id: offre}),
        today=lambda: AUJOURDHUI,
    )


async def test_generation_version_1_avec_audit_et_traçabilite() -> None:
    offre_id, storage = uuid.uuid4(), InMemoryStorage()
    service = _service(DummyCompiler(), offre_id=offre_id, storage=storage)

    document, version, content, audit = await service.generate_tailored_letter(
        owner_id=uuid.uuid4(), offer_id=offre_id, options=CoverLetterOptions()
    )

    assert document.kind == DocumentKind.COVER_LETTER.value
    assert document.title == "Lettre - Développeur Python Backend (Doctolib)"
    assert document.offer_id == offre_id  # TASK-013-15 : liée à l'offre
    assert version.version == 1
    assert "Doctolib" in (version.latex_source or "")
    assert audit.cv_coherent is True
    assert content.word_count == audit.word_count
    assert len(storage.files) == 1
    assert version.ats_report is not None
    assert version.ats_report["score"] == audit.score
    assert version.ats_report["generation"] == {
        "origin": "generated",
        "prompt_version": COVER_LETTER_PROMPT_VERSION,
        "language": "fr",
        "country_code": "FR",
    }


async def test_pays_de_l_offre_pilote_les_usages_sauf_indication_contraire() -> None:
    offre_id = uuid.uuid4()
    offre = OfferContext(**{**OFFRE.__dict__, "country_code": "GB"})
    service = _service(DummyCompiler(), offre_id=offre_id, offre=offre)

    _, _, content, _ = await service.generate_tailored_letter(
        owner_id=uuid.uuid4(), offer_id=offre_id, options=CoverLetterOptions(language="en")
    )
    assert content.complimentary_close == "Yours faithfully,"

    _, _, americaine, _ = await service.generate_tailored_letter(
        owner_id=uuid.uuid4(),
        offer_id=offre_id,
        options=CoverLetterOptions(language="en", country_code="us"),
    )
    assert americaine.complimentary_close == "Sincerely,"


async def test_sans_profil_valide_ou_sans_offre_rien_n_est_genere() -> None:
    storage, offre_id = InMemoryStorage(), uuid.uuid4()

    sans_profil = _service(DummyCompiler(), offre_id=offre_id, profil=None, storage=storage)
    with pytest.raises(NoValidatedProfileError):
        await sans_profil.generate_tailored_letter(
            owner_id=uuid.uuid4(), offer_id=offre_id, options=CoverLetterOptions()
        )

    service = _service(DummyCompiler(), offre_id=offre_id, storage=storage)
    with pytest.raises(OfferNotFoundError):
        await service.generate_tailored_letter(
            owner_id=uuid.uuid4(), offer_id=uuid.uuid4(), options=CoverLetterOptions()
        )
    assert storage.files == {}


async def test_profil_incomplet_refuse() -> None:
    from app.modules.candidate_profile.domain.profile import Identity, ProfileDocument

    offre_id = uuid.uuid4()
    service = _service(
        DummyCompiler(),
        offre_id=offre_id,
        profil=ProfileDocument(identity=Identity(city="Paris")),
    )
    with pytest.raises(IncompleteProfileError):
        await service.generate_tailored_letter(
            owner_id=uuid.uuid4(), offer_id=offre_id, options=CoverLetterOptions()
        )


async def test_fait_non_verifie_bloque_la_generation(monkeypatch: pytest.MonkeyPatch) -> None:
    """TASK-013-10 : l'ancien service n'appelait aucun contrôle de faits."""
    from dataclasses import replace

    from app.modules.document_generation.domain.cover_letter_generator import (
        generate_cover_letter_content as original,
    )

    def _falsifie(*args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
        lettre = original(*args, **kwargs)
        return replace(lettre, background_highlight="J'ai dirigé 300 personnes chez Google.")

    monkeypatch.setattr(
        "app.modules.document_generation.application.cover_letter_service."
        "generate_cover_letter_content",
        _falsifie,
    )
    offre_id, storage = uuid.uuid4(), InMemoryStorage()
    service = _service(DummyCompiler(), offre_id=offre_id, storage=storage)

    with pytest.raises(UnverifiedFactError, match="300"):
        await service.generate_tailored_letter(
            owner_id=uuid.uuid4(), offer_id=offre_id, options=CoverLetterOptions()
        )
    assert storage.files == {}


async def test_pdf_supprime_si_la_base_echoue() -> None:
    class RepoEnPanne(InMemoryRepository):
        async def add_version(self, **kwargs: Any) -> DocumentVersionModel:
            raise RuntimeError("base indisponible")

    offre_id, storage = uuid.uuid4(), InMemoryStorage()
    service = _service(DummyCompiler(), offre_id=offre_id, repo=RepoEnPanne(), storage=storage)

    with pytest.raises(RuntimeError):
        await service.generate_tailored_letter(
            owner_id=uuid.uuid4(), offer_id=offre_id, options=CoverLetterOptions()
        )
    assert storage.files == {}


async def test_un_cv_n_est_pas_servi_comme_une_lettre() -> None:
    offre_id, repo = uuid.uuid4(), InMemoryRepository()
    service = _service(DummyCompiler(), offre_id=offre_id, repo=repo)
    owner_id = uuid.uuid4()
    cv = await repo.create_document(
        owner_id=owner_id, kind=DocumentKind.CV, title="CV", language="fr", offer_id=None
    )

    with pytest.raises(DocumentNotFoundError):
        await service.library.get_document(owner_id=owner_id, document_id=cv.id)
    with pytest.raises(DocumentNotFoundError):
        await service.compile_custom_version(
            owner_id=owner_id, document_id=cv.id, latex_source="\\documentclass{article}"
        )


async def test_generation_reelle_une_page_audit_complet(compiler: LaTeXCompilerPort) -> None:
    offre_id = uuid.uuid4()
    service = _service(compiler, offre_id=offre_id)

    _, version, _, audit = await service.generate_tailored_letter(
        owner_id=uuid.uuid4(),
        offer_id=offre_id,
        options=CoverLetterOptions(motivation="J'apprécie votre approche produit."),
    )

    assert audit.page_count == 1
    assert audit.passed is True
    assert audit.cv_coherent is True
    assert version.size_bytes > 1000


class _PagesScriptees:
    """Compilateur factice : renvoie des PDF vides de 2 pages, puis de 1 page."""

    def __init__(self) -> None:
        self.sources: list[str] = []

    async def compile(self, latex_source: str) -> bytes:
        import io

        from pypdf import PdfWriter

        self.sources.append(latex_source)
        ecrivain = PdfWriter()
        for _ in range(2 if len(self.sources) == 1 else 1):
            ecrivain.add_blank_page(width=595, height=842)
        sortie = io.BytesIO()
        ecrivain.write(sortie)
        return sortie.getvalue()


async def test_une_lettre_qui_deborde_est_resserree_pas_tronquee() -> None:
    offre_id = uuid.uuid4()
    compilateur = _PagesScriptees()
    service = _service(compilateur, offre_id=offre_id)

    _, version, content, audit = await service.generate_tailored_letter(
        owner_id=uuid.uuid4(),
        offer_id=offre_id,
        options=CoverLetterOptions(motivation="Mon texte personnel, conservé tel quel."),
    )

    assert len(compilateur.sources) == 2  # standard (2 pages), puis compact
    assert r"\documentclass[11pt,a4paper]{article}" in compilateur.sources[0]
    assert r"\documentclass[10pt,a4paper]{article}" in compilateur.sources[1]
    assert version.latex_source == compilateur.sources[1]
    assert "Mon texte personnel, conservé tel quel." in content.added_value  # jamais coupé
    assert audit.page_count == 1
    assert not any("dépasse une page" in i for i in audit.issues)


async def test_une_lettre_qui_deborde_meme_en_compact_n_est_pas_validee() -> None:
    class _TouteTrop(_PagesScriptees):
        async def compile(self, latex_source: str) -> bytes:
            self.sources.append(latex_source)
            import io

            from pypdf import PdfWriter

            ecrivain = PdfWriter()
            ecrivain.add_blank_page(width=595, height=842)
            ecrivain.add_blank_page(width=595, height=842)
            sortie = io.BytesIO()
            ecrivain.write(sortie)
            return sortie.getvalue()

    offre_id = uuid.uuid4()
    service = _service(_TouteTrop(), offre_id=offre_id)

    _, _, _, audit = await service.generate_tailored_letter(
        owner_id=uuid.uuid4(), offer_id=offre_id, options=CoverLetterOptions()
    )
    assert audit.page_count == 2
    assert audit.passed is False
    assert any("dépasse une page" in i for i in audit.issues)


async def test_edition_manuelle_est_reellement_auditee(compiler: LaTeXCompilerPort) -> None:
    """Avant : toute version éditée recevait un faux {"score": 85, "passed": True}."""
    offre_id, owner_id = uuid.uuid4(), uuid.uuid4()
    service = _service(compiler, offre_id=offre_id)
    document, v1, _, _ = await service.generate_tailored_letter(
        owner_id=owner_id, offer_id=offre_id, options=CoverLetterOptions()
    )

    edite = (v1.latex_source or "").replace(
        "Je vous remercie", "Je suis extrêmement motivé et ai géré 900 clients. Je vous remercie"
    )
    v2, audit = await service.compile_custom_version(
        owner_id=owner_id, document_id=document.id, latex_source=edite
    )

    assert v2.version == 2
    assert audit.passed is False
    assert audit.generic_phrases_detected == ("extrêmement motivé",)
    assert audit.cv_coherent is False  # « 900 » absent du profil et de l'offre
    assert audit.score != 85
    assert v2.ats_report is not None
    assert v2.ats_report["generation"] == {"origin": "manual_edit"}
    assert v2.ats_report["score"] == audit.score

    comparaison = await service.library.compare_versions(
        owner_id=owner_id, document_id=document.id, version_a=1, version_b=2
    )
    assert "extrêmement motivé" in comparaison.diff_latex
    assert comparaison.score_a == v1.ats_report["score"]  # type: ignore[index]


async def test_edition_sur_offre_supprimee_reste_possible(compiler: LaTeXCompilerPort) -> None:
    offre_id, owner_id = uuid.uuid4(), uuid.uuid4()
    service = _service(compiler, offre_id=offre_id)
    document, v1, _, _ = await service.generate_tailored_letter(
        owner_id=owner_id, offer_id=offre_id, options=CoverLetterOptions()
    )
    service._inputs = FakeInputs(profil_alice(), {})

    version, audit = await service.compile_custom_version(
        owner_id=owner_id, document_id=document.id, latex_source=v1.latex_source or ""
    )
    assert version.version == 2
    assert audit.relevance_score == 0  # sans offre, aucune pertinence ne peut être attestée


def test_date_injectable_pour_des_lettres_deterministes() -> None:
    service = _service(DummyCompiler(), offre_id=uuid.uuid4())
    assert service._today() == date(2026, 11, 4)
