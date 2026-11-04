"""Contrôle strict des faits (TASK-012-10).

Règle absolue du projet : l'IA ou les générateurs ne doivent JAMAIS inventer
de faits (entreprises, diplômes, compétences, dates, responsabilités).
Tout élément présent dans le document généré doit impérativement provenir du profil maître.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.modules.document_generation.domain.models import FactCheckResult

if TYPE_CHECKING:
    from app.modules.candidate_profile.domain.profile import ProfileDocument


class UnverifiedFactError(ValueError):
    """Exception levée lorsqu'un fait inventé ou non sourcé est détecté."""


def verify_facts(
    master_profile: ProfileDocument, generated_profile: ProfileDocument
) -> FactCheckResult:
    """Compare le profil généré au profil maître pour garantir la véracité absolue des faits."""
    issues: list[str] = []
    unverified_companies: list[str] = []
    unverified_institutions: list[str] = []
    unverified_skills: list[str] = []

    # 1. Vérification des entreprises
    master_companies = {
        (exp.company or "").casefold().strip() for exp in master_profile.experiences if exp.company
    }
    for exp in generated_profile.experiences:
        c_clean = (exp.company or "").casefold().strip()
        if c_clean and c_clean not in master_companies:
            unverified_companies.append(exp.company or "")
            issues.append(f"Entreprise non vérifiée dans le profil maître : '{exp.company}'")

    # 2. Vérification des établissements de formation
    master_institutions = {
        (edu.institution or "").casefold().strip()
        for edu in master_profile.educations
        if edu.institution
    }
    master_degrees = {
        (edu.degree or "").casefold().strip() for edu in master_profile.educations if edu.degree
    }
    for edu in generated_profile.educations:
        inst_clean = (edu.institution or "").casefold().strip()
        deg_clean = (edu.degree or "").casefold().strip()
        if inst_clean and inst_clean not in master_institutions:
            unverified_institutions.append(edu.institution or "")
            issues.append(f"Établissement non vérifié dans le profil maître : '{edu.institution}'")
        if deg_clean and deg_clean not in master_degrees:
            issues.append(f"Diplôme non vérifié dans le profil maître : '{edu.degree}'")

    # 3. Vérification des compétences
    master_skills = {s.name.casefold().strip() for s in master_profile.skills}
    for s in generated_profile.skills:
        s_clean = s.name.casefold().strip()
        if s_clean not in master_skills:
            unverified_skills.append(s.name)
            issues.append(f"Compétence non vérifiée dans le profil maître : '{s.name}'")

    # 4. Vérification des certifications
    master_certs = {c.name.casefold().strip() for c in master_profile.certifications}
    for c in generated_profile.certifications:
        c_clean = c.name.casefold().strip()
        if c_clean not in master_certs:
            issues.append(f"Certification non vérifiée dans le profil maître : '{c.name}'")

    is_valid = len(issues) == 0

    return FactCheckResult(
        is_valid=is_valid,
        unverified_companies=tuple(unverified_companies),
        unverified_institutions=tuple(unverified_institutions),
        unverified_skills=tuple(unverified_skills),
        issues=tuple(issues),
    )


def assert_facts_verified(
    master_profile: ProfileDocument, generated_profile: ProfileDocument
) -> None:
    """Valide les faits ou lève UnverifiedFactError."""
    result = verify_facts(master_profile, generated_profile)
    if not result.is_valid:
        raise UnverifiedFactError(
            "Le CV généré contient des faits non prouvés : " + "; ".join(result.issues)
        )
