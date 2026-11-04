"""Tests unitaires du service ResumeService (EPIC 012)."""

import uuid
from typing import Any

from app.modules.candidate_profile.domain.profile import (
    DocDate,
    ExperienceDoc,
    Identity,
    ProfileDocument,
    SkillDoc,
)
from app.modules.document_generation.application.ports import (
    DocumentRepositoryPort,
    DocumentStoragePort,
    LaTeXCompilerPort,
)
from app.modules.document_generation.application.resume_service import ResumeService
from app.modules.document_generation.domain.enums import DocumentKind
from app.modules.document_generation.domain.models import ResumeGenerationOptions
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
            ),
        ),
        skills=(SkillDoc(name="Python"), SkillDoc(name="FastAPI")),
    )


async def test_generation_cv_complet_version_1() -> None:
    repo = InMemoryRepository()
    storage = InMemoryStorage()
    compiler = DummyCompiler()
    service = ResumeService(repository=repo, storage=storage, compiler=compiler)

    owner_id = uuid.uuid4()
    profil = _profil_valide()
    options = ResumeGenerationOptions(target_role="Lead Python")

    doc, ver, _ats = await service.generate_tailored_resume(
        owner_id=owner_id,
        master_profile=profil,
        options=options,
        offer_title="Lead Python Developer",
    )

    assert doc.id is not None
    assert ver.version == 1
    assert ver.latex_source is not None
    assert "OpenCorp" in ver.latex_source
    assert len(storage.files) == 1


async def test_compilation_nouvelle_version_et_comparaison() -> None:
    repo = InMemoryRepository()
    storage = InMemoryStorage()
    compiler = DummyCompiler()
    service = ResumeService(repository=repo, storage=storage, compiler=compiler)

    owner_id = uuid.uuid4()
    profil = _profil_valide()
    doc, ver1, _ = await service.generate_tailored_resume(
        owner_id=owner_id,
        master_profile=profil,
        options=ResumeGenerationOptions(),
    )

    # Compilation d'une version 2 avec code source LaTeX modifié
    source_initiale = ver1.latex_source or ""
    latex_modifie = source_initiale + "\n% Modification manuelle pour v2"
    ver2, _ats2 = await service.compile_custom_version(
        owner_id=owner_id,
        document_id=doc.id,
        latex_source=latex_modifie,
    )

    assert ver2.version == 2
    assert len(storage.files) == 2

    # Comparaison entre version 1 et version 2 (TASK-012-26)
    comp = await service.compare_versions(
        owner_id=owner_id,
        document_id=doc.id,
        version_a=1,
        version_b=2,
    )

    assert comp.version_a == 1
    assert comp.version_b == 2
    assert "+% Modification manuelle pour v2" in comp.diff_latex
