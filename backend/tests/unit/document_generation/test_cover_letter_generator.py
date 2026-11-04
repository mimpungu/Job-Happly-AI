"""Tests unitaires du générateur et de l'audit de lettre de motivation (FEATURE 013.1 et 013.2)."""

from app.modules.candidate_profile.domain.profile import (
    DocDate,
    ExperienceDoc,
    Identity,
    ProfileDocument,
    SkillDoc,
)
from app.modules.document_generation.domain.cover_letter_generator import (
    audit_cover_letter,
    extract_company_offer_context,
    generate_cover_letter_content,
)
from app.modules.document_generation.domain.cover_letter_models import (
    CoverLetterContent,
    CoverLetterOptions,
)


def _profil_candidat() -> ProfileDocument:
    return ProfileDocument(
        identity=Identity(
            first_name="Marc",
            last_name="Lambert",
            city="Nantes",
            email="marc.lambert@example.com",
            phone="+33 6 11 22 33 44",
            headline="Ingénieur Cloud & DevOps",
        ),
        experiences=(
            ExperienceDoc(
                title="DevOps Engineer",
                company="SaaS Corp",
                start=DocDate(year=2021),
                is_current=True,
                description="Automatisation d'infrastructures avec Terraform et AWS.",
                achievements=("Disponibilité portée à 99.99%", "Migration Kubernetes"),
            ),
        ),
        skills=(
            SkillDoc(name="Terraform", category="DevOps"),
            SkillDoc(name="AWS", category="Cloud"),
            SkillDoc(name="Kubernetes", category="DevOps"),
            SkillDoc(name="Python", category="Langages"),
        ),
    )


def test_extraction_contexte_offre() -> None:
    """Vérifie l'extraction structurée des données de l'offre et entreprise (TASK-013-01 à 03)."""
    desc = """À propos de Datadog : leader mondial du monitoring cloud.
    Vos missions :
    - Concevoir des pipelines d'automatisation Terraform
    - Optimiser le déploiement sur Kubernetes
    - Assurer la fiabilité des infrastructures de production
    """
    context = extract_company_offer_context(
        job_title="Senior Site Reliability Engineer",
        company_name="Datadog France",
        offer_description=desc,
        company_location="Paris",
        required_skills=("Terraform", "Kubernetes", "AWS"),
    )

    assert context.company_name == "Datadog France"
    assert context.job_title == "Senior Site Reliability Engineer"
    assert len(context.responsibilities) >= 2
    assert "Terraform" in context.keywords
    assert "Kubernetes" in context.keywords


def test_generation_fr_structure_en_quatre_parties() -> None:
    """Vérifie la rédaction en 4 parties professionnelles (TASK-013-07, 08)."""
    profil = _profil_candidat()
    context = extract_company_offer_context(
        job_title="Lead DevOps",
        company_name="Acme Cloud",
        offer_description="Missions de déploiement d'infrastructure sur AWS.",
        required_skills=("AWS", "Terraform"),
    )
    options = CoverLetterOptions(language="fr")

    content = generate_cover_letter_content(profil, context, options)

    assert content.candidate_name == "Marc Lambert"
    assert content.recipient_company == "Acme Cloud"
    assert "Candidature au poste de Lead DevOps" in content.subject
    assert "Madame, Monsieur" in content.salutation

    # 4 parties distinctes
    assert "Acme Cloud" in content.introduction
    assert "SaaS Corp" in content.background_highlight
    assert "Terraform" in content.added_value or "AWS" in content.added_value
    assert "entretien" in content.closing_and_call_to_action
    assert content.word_count >= 150


def test_generation_en_adaptation_ton_et_langue() -> None:
    """Vérifie l'adaptation des formules en langue anglaise (TASK-013-16, 18)."""
    profil = _profil_candidat()
    context = extract_company_offer_context(
        job_title="Cloud Engineer",
        company_name="Global Tech Ltd",
        offer_description="Deploying multi-region systems on AWS.",
        required_skills=("AWS", "Terraform"),
    )
    options = CoverLetterOptions(language="en")

    content = generate_cover_letter_content(profil, context, options)

    assert "Application for Cloud Engineer position" in content.subject
    assert "Dear Hiring Team at Global Tech Ltd," in content.salutation
    assert "Sincerely," in content.complimentary_close
    assert "interview" in content.closing_and_call_to_action


def test_audit_qualite_et_detection_cliches() -> None:
    """Vérifie l'évaluation sur 100 points et le rejet des clichés creux (TASK-013-11)."""
    profil = _profil_candidat()
    context = extract_company_offer_context(
        job_title="DevOps Specialist",
        company_name="Fintech SAS",
        offer_description="Gestion d'infrastructure sécurisée.",
    )
    content = generate_cover_letter_content(profil, context, CoverLetterOptions())

    audit = audit_cover_letter(content, profil, context)
    assert audit.score >= 70
    assert audit.passed is True
    assert len(audit.generic_phrases_detected) == 0

    # Test avec cliché interdit injecté
    content_modifie = CoverLetterContent(
        candidate_name=content.candidate_name,
        candidate_address=content.candidate_address,
        candidate_email=content.candidate_email,
        candidate_phone=content.candidate_phone,
        recipient_company=content.recipient_company,
        recipient_department=content.recipient_department,
        date_and_location=content.date_and_location,
        subject=content.subject,
        salutation=content.salutation,
        introduction="Je suis extrêmement motivé par cette opportunité.",
        background_highlight=content.background_highlight,
        added_value=content.added_value,
        closing_and_call_to_action=content.closing_and_call_to_action,
        complimentary_close=content.complimentary_close,
        signature=content.signature,
        word_count=content.word_count,
    )
    audit_cliche = audit_cover_letter(content_modifie, profil, context)
    assert audit_cliche.passed is False
    assert "extrêmement motivé" in audit_cliche.generic_phrases_detected
