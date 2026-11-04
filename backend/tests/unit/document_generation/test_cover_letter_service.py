"""Tests unitaires du service CoverLetterService (EPIC 013)."""

import uuid

from app.modules.candidate_profile.domain.profile import (
    DocDate,
    ExperienceDoc,
    Identity,
    ProfileDocument,
    SkillDoc,
)
from app.modules.document_generation.application.cover_letter_service import (
    CoverLetterService,
)
from app.modules.document_generation.domain.cover_letter_models import CoverLetterOptions
from tests.unit.document_generation.test_resume_service import (
    DummyCompiler,
    InMemoryRepository,
    InMemoryStorage,
)


def _profil_valide() -> ProfileDocument:
    return ProfileDocument(
        identity=Identity(first_name="Alice", last_name="Mercier", city="Paris"),
        experiences=(
            ExperienceDoc(
                title="Lead Tech Python",
                company="DataCorp",
                start=DocDate(year=2021),
                is_current=True,
                description="Architecture et développement de microservices.",
            ),
        ),
        skills=(SkillDoc(name="Python"), SkillDoc(name="FastAPI")),
    )


async def test_generation_lettre_de_motivation_version_1() -> None:
    repo = InMemoryRepository()
    storage = InMemoryStorage()
    compiler = DummyCompiler()
    service = CoverLetterService(repository=repo, storage=storage, compiler=compiler)

    owner_id = uuid.uuid4()
    profil = _profil_valide()
    options = CoverLetterOptions(language="fr")

    doc, ver, content, audit = await service.generate_tailored_letter(
        owner_id=owner_id,
        master_profile=profil,
        options=options,
        job_title="Senior Python Developer",
        company_name="Innovate SAS",
        offer_description="Recherche développeur senior Python et FastAPI.",
    )

    assert doc.id is not None
    assert doc.kind == "cover_letter"
    assert "Innovate SAS" in doc.title
    assert ver.version == 1
    assert "Alice Mercier" in content.candidate_name
    assert audit.score >= 70
    assert len(storage.files) == 1


async def test_compilation_nouvelle_version_manuelle_et_comparaison() -> None:
    repo = InMemoryRepository()
    storage = InMemoryStorage()
    compiler = DummyCompiler()
    service = CoverLetterService(repository=repo, storage=storage, compiler=compiler)

    owner_id = uuid.uuid4()
    profil = _profil_valide()

    doc, ver1, _, _ = await service.generate_tailored_letter(
        owner_id=owner_id,
        master_profile=profil,
        options=CoverLetterOptions(),
        job_title="Python Engineer",
        company_name="Cloud Corp",
        offer_description="Ingénierie cloud.",
    )

    # Modification manuelle du code LaTeX
    source_initiale = ver1.latex_source or ""
    source_modifiee = source_initiale + "\n% Paragraphe supplémentaire édité manuellement"
    ver2 = await service.compile_custom_version(
        owner_id=owner_id,
        document_id=doc.id,
        latex_source=source_modifiee,
    )

    assert ver2.version == 2
    assert len(storage.files) == 2

    comp = await service.compare_versions(
        owner_id=owner_id,
        document_id=doc.id,
        version_a=1,
        version_b=2,
    )
    assert comp.version_a == 1
    assert comp.version_b == 2
    assert "+% Paragraphe supplémentaire édité manuellement" in comp.diff_latex
