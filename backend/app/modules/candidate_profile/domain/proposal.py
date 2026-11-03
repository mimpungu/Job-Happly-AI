"""Conversion d'une extraction de CV en brouillon éditable.

Tout élément converti est `imported` et **non validé** : l'utilisateur doit le relire. Rien
n'est complété — une donnée que l'extraction n'a pas lue reste absente.
"""

from __future__ import annotations

from app.modules.candidate_profile.domain.enums import DataOrigin, LanguageProficiency
from app.modules.candidate_profile.domain.extraction.dates import PartialDate
from app.modules.candidate_profile.domain.extraction.models import ExtractedProfile
from app.modules.candidate_profile.domain.profile import (
    CertificationDoc,
    DocDate,
    EducationDoc,
    ExperienceDoc,
    Identity,
    LanguageDoc,
    ProfileDocument,
    SkillDoc,
)


def _date(valeur: PartialDate | None) -> DocDate | None:
    return DocDate(year=valeur.year, month=valeur.month) if valeur else None


def _nom_et_prenom(nom_complet: str | None) -> tuple[str | None, str | None]:
    """« Marie Dupont » -> (Marie, Dupont). Au-delà de deux mots, le découpage est ambigu
    (« Jean Pierre Martin »), donc le nom est laissé à l'utilisateur plutôt que deviné."""
    if not nom_complet:
        return None, None
    mots = nom_complet.split()
    return (mots[0], mots[1]) if len(mots) == 2 else (None, None)


def proposal_to_document(extrait: ExtractedProfile) -> ProfileDocument:
    prenom, nom = _nom_et_prenom(extrait.contact.full_name)
    contact = extrait.contact
    return ProfileDocument(
        identity=Identity(
            first_name=prenom,
            last_name=nom,
            email=_email_ou_none(contact.email),
            phone=contact.phone,
            city=contact.city,
        ),
        summary=extrait.summary,
        experiences=tuple(
            ExperienceDoc(
                origin=DataOrigin.IMPORTED,
                source_text=e.source_text[:4000],
                title=e.title,
                company=e.company,
                location=e.location,
                start=_date(e.start),
                end=_date(e.end),
                is_current=e.is_current,
                description=e.description,
                achievements=e.achievements[:50],
            )
            for e in extrait.experiences
        ),
        educations=tuple(
            EducationDoc(
                origin=DataOrigin.IMPORTED,
                source_text=f.source_text[:4000],
                degree=f.degree,
                institution=f.institution,
                field_of_study=f.field_of_study,
                start=_date(f.start),
                end=_date(f.end),
            )
            for f in extrait.educations
        ),
        skills=tuple(
            SkillDoc(
                origin=DataOrigin.IMPORTED,
                source_text=s.source_text[:4000],
                name=s.name,
                category=s.category,
            )
            for s in extrait.skills
        ),
        languages=tuple(
            LanguageDoc(
                origin=DataOrigin.IMPORTED,
                source_text=lg.source_text[:4000],
                language_code=lg.language_code,
                proficiency=LanguageProficiency(lg.proficiency) if lg.proficiency else None,
                level_text=lg.level_text,
            )
            for lg in extrait.languages
            if lg.language_code
        ),
        certifications=tuple(
            CertificationDoc(
                origin=DataOrigin.IMPORTED,
                source_text=c.source_text[:4000],
                name=c.name[:200],
                issued_on=DocDate(year=c.year) if c.year else None,
            )
            for c in extrait.certifications
        ),
    )


def _email_ou_none(email: str | None) -> str | None:
    # Une adresse extraite mal formée ne doit pas faire échouer tout le brouillon.
    try:
        return Identity(email=email).email
    except ValueError:
        return None
