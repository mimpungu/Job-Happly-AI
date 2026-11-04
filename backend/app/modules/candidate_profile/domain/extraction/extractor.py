"""Point d'entrée : texte normalisé d'un CV -> profil proposé (règles classiques uniquement)."""

from __future__ import annotations

from app.modules.candidate_profile.domain.extraction.certifications import extract_certifications
from app.modules.candidate_profile.domain.extraction.contact import extract_contact
from app.modules.candidate_profile.domain.extraction.education import extract_educations
from app.modules.candidate_profile.domain.extraction.experience import extract_experiences
from app.modules.candidate_profile.domain.extraction.languages import extract_languages
from app.modules.candidate_profile.domain.extraction.models import ExtractedProfile
from app.modules.candidate_profile.domain.extraction.sections import SectionKind, split_sections
from app.modules.candidate_profile.domain.extraction.skills import extract_skills


def extract_profile(texte: str) -> ExtractedProfile:
    """Propose un profil à valider. Ne complète, ne devine ni n'invente aucune donnée.

    Tout ce que les règles ne savent pas lire est signalé dans `warnings` : le résultat est un
    point de départ pour la validation humaine (TASK-005-15), pas un profil validé.
    """
    document = split_sections(texte)
    experiences = extract_experiences(document.lines_of(SectionKind.EXPERIENCE))
    educations = extract_educations(document.lines_of(SectionKind.EDUCATION))
    competences = extract_skills(document.lines_of(SectionKind.SKILLS))
    langues = extract_languages(document.lines_of(SectionKind.LANGUAGES))
    certifications = extract_certifications(document.lines_of(SectionKind.CERTIFICATIONS))
    resume = " ".join(
        ligne.strip() for ligne in document.lines_of(SectionKind.SUMMARY) if ligne.strip()
    )

    avertissements: list[str] = []
    kinds = {s.kind for s in document.sections}
    for kind, libelle, trouve in (
        (SectionKind.EXPERIENCE, "expérience", experiences),
        (SectionKind.EDUCATION, "formation", educations),
        (SectionKind.SKILLS, "compétence", competences),
    ):
        if kind not in kinds:
            avertissements.append(f"Aucune section « {libelle} » reconnue dans le document.")
        elif not trouve:
            avertissements.append(
                f"La section « {libelle} » est présente mais aucun élément n'a pu être lu : "
                "saisissez-les à la main."
            )

    return ExtractedProfile(
        contact=extract_contact(document.preamble, texte),
        experiences=experiences,
        educations=educations,
        skills=competences,
        languages=langues,
        certifications=certifications,
        summary=resume or None,
        warnings=tuple(avertissements),
    )
