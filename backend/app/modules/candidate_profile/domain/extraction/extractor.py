"""Point d'entrée : texte normalisé d'un CV -> profil proposé (règles classiques uniquement)."""

from __future__ import annotations

from dataclasses import replace

from app.modules.candidate_profile.domain.extraction.certifications import extract_certifications
from app.modules.candidate_profile.domain.extraction.contact import extract_contact
from app.modules.candidate_profile.domain.extraction.education import extract_educations
from app.modules.candidate_profile.domain.extraction.experience import extract_experiences
from app.modules.candidate_profile.domain.extraction.geography import (
    CountryResolver,
    no_countries,
)
from app.modules.candidate_profile.domain.extraction.languages import extract_languages
from app.modules.candidate_profile.domain.extraction.models import ExtractedProfile
from app.modules.candidate_profile.domain.extraction.sections import SectionKind, split_sections
from app.modules.candidate_profile.domain.extraction.skills import extract_skills
from app.modules.candidate_profile.domain.text_columns import SOFT_WRAP

_MAX_TITRE = 80


def _introduction(tetes: tuple[tuple[str, ...], ...]) -> tuple[str | None, str]:
    """(titre professionnel, résumé) du texte sans titre qui suit le nom, en tête de colonne.

    La première ligne après le nom est un titre si elle est courte, ne finit pas comme une phrase
    et qu'un paragraphe la suit ; une ligne seule reste un résumé (rien n'est déduit de trop peu).
    """
    lignes = [ligne.strip() for tete in tetes for ligne in tete[1:] if ligne.strip()]
    if (
        len(lignes) >= 2
        and len(lignes[0]) <= _MAX_TITRE
        and not lignes[0].endswith((".", ":", ";"))
    ):
        return lignes[0], " ".join(lignes[1:])
    return None, " ".join(lignes)


def extract_profile(texte: str, *, country_of: CountryResolver = no_countries) -> ExtractedProfile:
    """Propose un profil à valider. Ne complète, ne devine ni n'invente aucune donnée.

    Tout ce que les règles ne savent pas lire est signalé dans `warnings` : le résultat est un
    point de départ pour la validation humaine (TASK-005-15), pas un profil validé.
    """
    document = split_sections(texte)
    experiences = extract_experiences(document.lines_of(SectionKind.EXPERIENCE), country_of)
    educations = extract_educations(document.lines_of(SectionKind.EDUCATION), country_of)
    competences = extract_skills(document.lines_of(SectionKind.SKILLS))
    langues = extract_languages(document.lines_of(SectionKind.LANGUAGES))
    certifications = extract_certifications(document.lines_of(SectionKind.CERTIFICATIONS))
    resume = " ".join(
        ligne.strip() for ligne in document.lines_of(SectionKind.SUMMARY) if ligne.strip()
    )
    titre: str | None = None
    if not resume:
        titre, resume = _introduction(document.column_heads)

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
        contact=replace(
            extract_contact(
                document.preamble,
                texte.replace(SOFT_WRAP, ""),
                document.column_heads,
                country_of,
            ),
            headline=titre,
        ),
        experiences=experiences,
        educations=educations,
        skills=competences,
        languages=langues,
        certifications=certifications,
        summary=resume or None,
        warnings=tuple(avertissements),
    )
