"""Tests unitaires du service ResumeService (EPIC 012)."""

import uuid
from typing import Any

import pytest

from app.modules.candidate_profile.domain.profile import (
    DocDate,
    ExperienceDoc,
    Identity,
    ProfileDocument,
    SkillDoc,
)
from app.modules.document_generation.application.ports import (
    DocumentNotFoundError,
    DocumentRepositoryPort,
    DocumentStoragePort,
    DocumentVersionNotFoundError,
    LaTeXCompilerPort,
    NoValidatedProfileError,
    OfferContext,
    OfferNotFoundError,
)
from app.modules.document_generation.application.resume_service import ResumeService
from app.modules.document_generation.domain.enums import DocumentKind, LengthTarget
from app.modules.document_generation.domain.fact_checker import UnverifiedFactError
from app.modules.document_generation.domain.models import ResumeGenerationOptions
from app.modules.document_generation.domain.prompts import CV_PROMPT_VERSION
from app.modules.document_generation.infrastructure.models import (
    DocumentVersionModel,
    GeneratedDocumentModel,
)


class InMemoryStorage(DocumentStoragePort):
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    async def store(self, content: bytes, *, extension: str = "pdf") -> tuple[str, str, int]:
        cle = f"{uuid.uuid4().hex}.{extension}"
        self.files[cle] = content
        return cle, "a" * 64, len(content)

    async def read(self, storage_key: str) -> bytes:
        if storage_key not in self.files:
            raise FileNotFoundError(storage_key)
        return self.files[storage_key]

    async def delete(self, storage_key: str) -> None:
        self.files.pop(storage_key, None)


class InMemoryRepository(DocumentRepositoryPort):
    def __init__(self) -> None:
        self.documents: dict[uuid.UUID, GeneratedDocumentModel] = {}
        self.versions: dict[uuid.UUID, list[DocumentVersionModel]] = {}

    async def create_document(
        self,
        *,
        owner_id: uuid.UUID,
        kind: DocumentKind,
        title: str,
        language: str,
        offer_id: uuid.UUID | None,
    ) -> GeneratedDocumentModel:
        doc = GeneratedDocumentModel(
            owner_id=owner_id,
            kind=kind.value,
            title=title,
            language=language,
            offer_id=offer_id,
        )
        doc.id = uuid.uuid4()
        self.documents[doc.id] = doc
        self.versions[doc.id] = []
        return doc

    async def get_document(
        self, *, owner_id: uuid.UUID, document_id: uuid.UUID
    ) -> GeneratedDocumentModel | None:
        return self.documents.get(document_id)

    async def list_documents(
        self,
        *,
        owner_id: uuid.UUID,
        kind: DocumentKind | None = None,
        offer_id: uuid.UUID | None = None,
    ) -> list[GeneratedDocumentModel]:
        return list(self.documents.values())

    async def add_version(
        self,
        *,
        owner_id: uuid.UUID,
        document_id: uuid.UUID,
        latex_source: str,
        storage_key: str,
        sha256: str,
        size_bytes: int,
        ats_report: dict[str, Any] | None,
    ) -> DocumentVersionModel:
        versions_list = self.versions.setdefault(document_id, [])
        num_v = len(versions_list) + 1
        ver = DocumentVersionModel(
            owner_id=owner_id,
            document_id=document_id,
            version=num_v,
            latex_source=latex_source,
            storage_key=storage_key,
            sha256=sha256,
            size_bytes=size_bytes,
            ats_report=ats_report,
        )
        ver.id = uuid.uuid4()
        versions_list.append(ver)
        return ver

    async def get_version(
        self, *, owner_id: uuid.UUID, document_id: uuid.UUID, version: int
    ) -> DocumentVersionModel | None:
        for v in self.versions.get(document_id, []):
            if v.version == version:
                return v
        return None

    async def list_versions(
        self, *, owner_id: uuid.UUID, document_id: uuid.UUID
    ) -> list[DocumentVersionModel]:
        return self.versions.get(document_id, [])


class FakeInputs:
    """Port d'entrées en mémoire : profil validé (ou absent) et offres connues."""

    def __init__(
        self, profile: ProfileDocument | None, offers: dict[uuid.UUID, OfferContext] | None = None
    ) -> None:
        self.profile = profile
        self.offers = offers or {}

    async def validated_profile(self, *, owner_id: uuid.UUID) -> ProfileDocument:
        if self.profile is None:
            raise NoValidatedProfileError
        return self.profile

    async def offer_context(self, *, owner_id: uuid.UUID, offer_id: uuid.UUID) -> OfferContext:
        if offer_id not in self.offers:
            raise OfferNotFoundError(str(offer_id))
        return self.offers[offer_id]


class RealCompiler:
    """Délègue au vrai compilateur (fixture) ; compte les appels."""

    def __init__(self, inner: LaTeXCompilerPort) -> None:
        self.inner = inner
        self.sources: list[str] = []

    async def compile(self, latex_source: str) -> bytes:
        self.sources.append(latex_source)
        return await self.inner.compile(latex_source)


class DummyCompiler(LaTeXCompilerPort):
    async def compile(self, latex_source: str) -> bytes:
        return b"%PDF-1.4 dummy pdf for tests"


def _profil_valide() -> ProfileDocument:
    return ProfileDocument(
        identity=Identity(first_name="Camille", last_name="Dubois", headline="Dev Python"),
        experiences=(
            ExperienceDoc(
                title="Ingénieur Logiciel",
                company="OpenCorp",
                start=DocDate(year=2020),
                is_current=True,
                description="Développement de services en Python.",
                achievements=("Migration vers FastAPI", "Revue de code"),
            ),
        ),
        skills=(SkillDoc(name="Python"), SkillDoc(name="FastAPI")),
    )


def _service(
    compiler: LaTeXCompilerPort,
    inputs: FakeInputs,
    repo: InMemoryRepository | None = None,
    storage: InMemoryStorage | None = None,
) -> ResumeService:
    return ResumeService(
        repository=repo or InMemoryRepository(),
        storage=storage or InMemoryStorage(),
        compiler=compiler,
        inputs=inputs,
    )


async def test_generation_cv_complet_version_1() -> None:
    storage = InMemoryStorage()
    service = _service(DummyCompiler(), FakeInputs(_profil_valide()), storage=storage)

    doc, ver, _ats = await service.generate_tailored_resume(
        owner_id=uuid.uuid4(), options=ResumeGenerationOptions(target_role="Lead Python")
    )

    assert ver.version == 1
    assert doc.title == "CV - Lead Python"
    assert "OpenCorp" in (ver.latex_source or "")
    assert len(storage.files) == 1
    assert ver.ats_report is not None
    assert ver.ats_report["generation"] == {
        "origin": "generated",
        "prompt_version": CV_PROMPT_VERSION,
        "style": "classic",
        "length_target": "auto",
        "language": "fr",
    }


async def test_sans_profil_valide_aucune_generation() -> None:
    storage = InMemoryStorage()
    service = _service(DummyCompiler(), FakeInputs(None), storage=storage)

    with pytest.raises(NoValidatedProfileError):
        await service.generate_tailored_resume(
            owner_id=uuid.uuid4(), options=ResumeGenerationOptions()
        )
    assert storage.files == {}


async def test_offre_inconnue() -> None:
    service = _service(DummyCompiler(), FakeInputs(_profil_valide()))
    with pytest.raises(OfferNotFoundError):
        await service.generate_tailored_resume(
            owner_id=uuid.uuid4(), options=ResumeGenerationOptions(), offer_id=uuid.uuid4()
        )


async def test_ciblage_sur_offre_utilise_les_competences_analysees() -> None:
    offre_id = uuid.uuid4()
    offre = OfferContext(
        title="Backend Python", company="Acme", description="x", required_skills=("FastAPI", "Rust")
    )
    service = _service(DummyCompiler(), FakeInputs(_profil_valide(), {offre_id: offre}))

    doc, ver, ats = await service.generate_tailored_resume(
        owner_id=uuid.uuid4(), options=ResumeGenerationOptions(), offer_id=offre_id
    )

    assert doc.offer_id == offre_id  # TASK-012-23 : version associée à l'offre
    assert doc.title == "CV - Backend Python"
    assert "Backend Python — compétences clés pour ce poste : FastAPI." in (ver.latex_source or "")
    assert "Rust" not in (ver.latex_source or "")  # jamais de compétence non possédée
    assert "Rust" in ats.keywords_missing  # signalé comme absent, jamais inventé


async def test_fait_non_verifie_bloque_la_generation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Si une étape amont injectait un fait inventé, le contrôle l'arrête avant compilation."""
    from app.modules.document_generation.domain.content_selection import (
        adapt_resume_content as original,
    )

    storage = InMemoryStorage()
    service = _service(DummyCompiler(), FakeInputs(_profil_valide()), storage=storage)

    def _falsifie(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        adapte = original(*args, **kwargs)  # type: ignore[arg-type]
        faux = adapte.adapted_profile.experiences[0].model_copy(update={"company": "Google"})
        profil = adapte.adapted_profile.model_copy(update={"experiences": (faux,)})
        return adapte.__class__(**{**adapte.__dict__, "adapted_profile": profil})

    monkeypatch.setattr(
        "app.modules.document_generation.application.resume_service.adapt_resume_content",
        _falsifie,
    )

    with pytest.raises(UnverifiedFactError, match="Google"):
        await service.generate_tailored_resume(
            owner_id=uuid.uuid4(), options=ResumeGenerationOptions()
        )
    assert storage.files == {}


async def test_pdf_supprime_si_la_base_echoue() -> None:
    class RepoEnPanne(InMemoryRepository):
        async def add_version(self, **kwargs: Any) -> DocumentVersionModel:
            raise RuntimeError("base indisponible")

    storage = InMemoryStorage()
    service = _service(
        DummyCompiler(), FakeInputs(_profil_valide()), repo=RepoEnPanne(), storage=storage
    )

    with pytest.raises(RuntimeError, match="base indisponible"):
        await service.generate_tailored_resume(
            owner_id=uuid.uuid4(), options=ResumeGenerationOptions()
        )
    assert storage.files == {}  # aucun PDF orphelin


async def test_compilation_nouvelle_version_et_comparaison() -> None:
    storage = InMemoryStorage()
    service = _service(DummyCompiler(), FakeInputs(_profil_valide()), storage=storage)
    owner_id = uuid.uuid4()
    doc, ver1, _ = await service.generate_tailored_resume(
        owner_id=owner_id, options=ResumeGenerationOptions()
    )

    modifie = (ver1.latex_source or "") + "\n% Modification manuelle pour v2"
    ver2, _ = await service.compile_custom_version(
        owner_id=owner_id, document_id=doc.id, latex_source=modifie
    )
    comp = await service.library.compare_versions(
        owner_id=owner_id, document_id=doc.id, version_a=1, version_b=2
    )

    assert ver2.version == 2
    assert ver2.ats_report is not None
    assert ver2.ats_report["generation"] == {"origin": "manual_edit"}
    assert len(storage.files) == 2
    assert "+% Modification manuelle pour v2" in comp.diff_latex
    # La version 1 est immuable : sa source n'a pas bougé.
    assert "Modification manuelle" not in (ver1.latex_source or "")


async def test_pdf_supprime_si_l_enregistrement_d_une_version_editee_echoue() -> None:
    class RepoEnPanne(InMemoryRepository):
        fail = False

        async def add_version(self, **kwargs: Any) -> DocumentVersionModel:
            if self.fail:
                raise RuntimeError("base indisponible")
            return await super().add_version(**kwargs)

    repo, storage = RepoEnPanne(), InMemoryStorage()
    service = _service(DummyCompiler(), FakeInputs(_profil_valide()), repo=repo, storage=storage)
    owner_id = uuid.uuid4()
    doc, ver1, _ = await service.generate_tailored_resume(
        owner_id=owner_id, options=ResumeGenerationOptions()
    )
    repo.fail = True

    with pytest.raises(RuntimeError):
        await service.compile_custom_version(
            owner_id=owner_id, document_id=doc.id, latex_source=ver1.latex_source or ""
        )
    assert len(storage.files) == 1


async def test_documents_et_versions_introuvables() -> None:
    service = _service(DummyCompiler(), FakeInputs(_profil_valide()))
    owner_id = uuid.uuid4()
    inconnu = uuid.uuid4()

    with pytest.raises(DocumentNotFoundError):
        await service.library.get_document(owner_id=owner_id, document_id=inconnu)
    with pytest.raises(DocumentNotFoundError):
        await service.compile_custom_version(
            owner_id=owner_id, document_id=inconnu, latex_source="\\documentclass{article}"
        )

    doc, _, _ = await service.generate_tailored_resume(
        owner_id=owner_id, options=ResumeGenerationOptions()
    )
    with pytest.raises(DocumentVersionNotFoundError):
        await service.library.download_pdf(owner_id=owner_id, document_id=doc.id, version=9)
    with pytest.raises(DocumentVersionNotFoundError):
        await service.library.compare_versions(
            owner_id=owner_id, document_id=doc.id, version_a=1, version_b=9
        )


async def test_telechargements_nom_de_fichier_sur() -> None:
    service = _service(DummyCompiler(), FakeInputs(_profil_valide()))
    owner_id = uuid.uuid4()
    doc, _, _ = await service.generate_tailored_resume(
        owner_id=owner_id,
        options=ResumeGenerationOptions(title='../../CV: <Léa> \\ "x"'),
    )

    contenu, nom_pdf = await service.library.download_pdf(
        owner_id=owner_id, document_id=doc.id, version=1
    )
    source, nom_tex = await service.library.download_latex(
        owner_id=owner_id, document_id=doc.id, version=1
    )

    assert contenu.startswith(b"%PDF")
    assert "documentclass" in source
    for nom in (nom_pdf, nom_tex):
        assert not any(c in nom for c in '/\\:<>"')
    assert nom_pdf.endswith("_v1.pdf")
    assert nom_tex.endswith("_v1.tex")


async def test_generation_reelle_de_bout_en_bout(compiler: LaTeXCompilerPort) -> None:
    """Profil → LaTeX → vrai PDF → audit ATS réel (critères d'acceptation de l'EPIC)."""
    service = _service(compiler, FakeInputs(_profil_valide()))
    owner_id = uuid.uuid4()

    _, ver, ats = await service.generate_tailored_resume(
        owner_id=owner_id, options=ResumeGenerationOptions(length_target=LengthTarget.ONE_PAGE)
    )

    assert ats.passed is True
    assert ats.page_count == 1
    assert ats.single_column is True
    assert ats.accents_preserved is True  # nom, entreprise et titres retrouvés à l'extraction
    assert ver.size_bytes > 1000


async def test_auto_repasse_en_deux_pages_si_une_page_deborde(
    compiler: LaTeXCompilerPort,
) -> None:
    """L'estimation « une page » (≤ 3 expériences) peut être fausse : on le corrige."""
    long = "Mission détaillée avec beaucoup de contexte métier et technique. " * 35
    profil = ProfileDocument(
        identity=Identity(first_name="Camille", last_name="Dubois"),
        experiences=tuple(
            ExperienceDoc(
                title=f"Poste {i}",
                company=f"Société {i}",
                start=DocDate(year=2010 + i),
                end=DocDate(year=2011 + i),
                description=long,
            )
            for i in range(3)
        ),
        skills=(SkillDoc(name="Python"),),
    )
    spy = RealCompiler(compiler)
    service = _service(spy, FakeInputs(profil))

    _, ver, ats = await service.generate_tailored_resume(
        owner_id=uuid.uuid4(), options=ResumeGenerationOptions(length_target=LengthTarget.AUTO)
    )

    assert len(spy.sources) == 2  # première tentative « une page », puis repli aéré
    assert ats.page_count == 2
    assert ver.ats_report is not None
    assert ver.ats_report["generation"]["length_target"] == "two_pages"
