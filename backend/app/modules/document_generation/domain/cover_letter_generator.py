"""Génération déterministe (niveau 0, sans IA) d'une lettre de motivation factuelle.

Chaque phrase est bâtie sur une donnée du profil validé ou de l'offre ; aucune qualité, aucun
résultat ni aucune ancienneté n'est affirmé sans source (prompt maître §8). Une lettre produite
ainsi est une base solide, volontairement sobre : la motivation personnelle est apportée par
l'utilisateur (`custom_opening`, `motivation`).

- TASK-013-01 à 03, 05 : contexte de l'offre (sans recherche externe).
- TASK-013-04 : expériences et compétences choisies par pertinence, comme pour le CV.
- TASK-013-07, 08 : contexte minimal, lettre en 4 parties.
- TASK-013-16, 18 : langue et conventions du pays.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from app.modules.document_generation.domain.content_selection import (
    experience_mentions_terms,
    mentions_term,
    prioritize_achievements,
    rank_experiences,
    resolve_offer_terms,
    verified_skills,
)
from app.modules.document_generation.domain.cover_letter_conventions import (
    conventions_for,
    format_letter_date,
)
from app.modules.document_generation.domain.cover_letter_models import (
    CompanyOfferContext,
    CoverLetterContent,
    CoverLetterOptions,
    IncompleteProfileError,
    LetterFacts,
)

if TYPE_CHECKING:
    from app.modules.candidate_profile.domain.profile import ExperienceDoc, ProfileDocument

_MAX_RESPONSIBILITIES = 4
_MIN_RESPONSIBILITY_CHARS = 10
_MAX_SKILLS_SHOWN = 4
_MAX_ACHIEVEMENTS = 2
_BULLET = ("-", "*", "•")


def extract_company_offer_context(
    *,
    job_title: str,
    company_name: str | None,
    offer_description: str,
    company_location: str | None = None,
    company_sector: str | None = None,
    required_skills: tuple[str, ...] = (),
) -> CompanyOfferContext:
    """Structure ce que l'annonce dit du poste ; rien n'est déduit ni cherché ailleurs."""
    responsabilites: list[str] = []
    for ligne in (line.strip() for line in offer_description.splitlines()):
        if ligne.startswith(_BULLET):
            texte = ligne.lstrip("-*• ").strip().rstrip(".;")
            if len(texte) >= _MIN_RESPONSIBILITY_CHARS:
                responsabilites.append(texte)
        if len(responsabilites) >= _MAX_RESPONSIBILITIES:
            break

    return CompanyOfferContext(
        job_title=job_title.strip(),
        company_name=(company_name or "").strip() or None,
        company_location=(company_location or "").strip() or None,
        company_sector=(company_sector or "").strip() or None,
        responsibilities=tuple(responsabilites),
        required_skills=required_skills,
        offer_text=offer_description,
    )


def generate_cover_letter_content(
    profile: ProfileDocument,
    context: CompanyOfferContext,
    options: CoverLetterOptions,
    *,
    today: date,
) -> CoverLetterContent:
    """Rédige la lettre en 4 parties à partir du seul profil validé et de l'offre."""
    identite = profile.identity
    nom = f"{identite.first_name or ''} {identite.last_name or ''}".strip()
    if not nom:
        raise IncompleteProfileError("Le profil doit contenir un nom pour signer la lettre.")
    if not (profile.experiences or profile.educations or profile.skills):
        raise IncompleteProfileError(
            "Le profil ne contient ni expérience, ni formation, ni compétence à valoriser."
        )

    langue = options.language
    termes = resolve_offer_terms(
        profile, required_skills=context.required_skills, description=context.offer_text
    )
    competences = verified_skills(profile, termes)
    classees = rank_experiences(profile.experiences, termes)

    pertinent = bool(competences) or any(experience_mentions_terms(e, termes) for e in classees[:1])
    intro, user_intro = _introduction(context, options, pertinent)
    parcours, faits = _parcours(profile, classees, termes, competences, langue)
    valeur, user_valeur = _valeur_ajoutee(context, options, competences)
    conclusion = _conclusion(context, langue)

    usages = conventions_for(
        language=langue, country_code=options.country_code, recipient_name=options.recipient_name
    )
    return CoverLetterContent(
        language=langue,
        candidate_name=nom,
        candidate_city=identite.city,
        candidate_email=identite.email,
        candidate_phone=identite.phone,
        recipient_company=context.company_name,
        recipient_department=options.recipient_department,
        recipient_name=options.recipient_name,
        date_and_location=format_letter_date(
            today, language=langue, country_code=options.country_code, city=identite.city
        ),
        subject=(
            f"Candidature au poste de {context.job_title}"
            if langue == "fr"
            else f"Application for the position of {context.job_title}"
        ),
        salutation=usages.salutation,
        introduction=intro,
        background_highlight=parcours,
        added_value=valeur,
        closing_and_call_to_action=conclusion,
        complimentary_close=usages.complimentary_close,
        signature=nom,
        user_written=tuple(t for t in (user_intro, user_valeur) if t),
        facts=faits,
    )


def _lower_first(texte: str) -> str:
    """Abaisse la majuscule initiale d'un verbe, sans toucher à un sigle (« API », « SQL »)."""
    if len(texte) > 1 and texte[0].isupper() and texte[1].islower():
        return texte[0].lower() + texte[1:]
    return texte


def _enumeration(elements: list[str], langue: str) -> str:
    if len(elements) <= 1:
        return "".join(elements)
    lien = " et " if langue == "fr" else " and "
    return ", ".join(elements[:-1]) + lien + elements[-1]


def _introduction(
    context: CompanyOfferContext,
    options: CoverLetterOptions,
    pertinent: bool,
) -> tuple[str, str | None]:
    """Retourne (paragraphe, texte saisi par l'utilisateur ou None)."""
    if options.custom_opening:
        return options.custom_opening, options.custom_opening

    fr = options.language == "fr"
    entreprise = context.company_name
    lieu = context.company_location
    if fr:
        phrase = f"Je vous adresse ma candidature au poste de {context.job_title}"
        phrase += f" chez {entreprise}" if entreprise else ""
        phrase += f" ({lieu})" if lieu else ""
    else:
        phrase = f"I am applying for the position of {context.job_title}"
        phrase += f" at {entreprise}" if entreprise else ""
        phrase += f" ({lieu})" if lieu else ""
    phrase += "."

    missions = [_lower_first(r) for r in context.responsibilities[:2]]
    if missions and pertinent:  # n'affirmer un lien que s'il existe vraiment
        liste = _enumeration(missions, options.language)
        if fr:
            phrase += f" Les missions décrites, notamment {liste}, rejoignent mon parcours."
        else:
            phrase += f" The responsibilities described, notably {liste}, relate to my background."
    return phrase, None


def _periode(exp: ExperienceDoc, langue: str) -> str:
    debut = exp.start.year if exp.start else None
    fin = exp.end.year if exp.end else None
    if exp.is_current and debut:
        return f"Depuis {debut}" if langue == "fr" else f"Since {debut}"
    if debut and fin:
        return f"De {debut} à {fin}" if langue == "fr" else f"From {debut} to {fin}"
    return ""


def _phrase_experience(exp: ExperienceDoc, langue: str, *, ancienne: bool) -> str:
    """Une phrase strictement tirée des champs de l'expérience (période, intitulé, société)."""
    titre, societe = exp.title, exp.company
    if not titre and not societe:
        return ""
    periode = _periode(exp, langue)
    passe = bool(exp.end) and not exp.is_current
    fr = langue == "fr"

    if fr:
        verbe = "j'ai exercé" if passe else "j'exerce"
        repli = "Auparavant, j'ai exercé" if ancienne else verbe.capitalize()
        role = f"comme {titre}" if titre else "une activité"
        lieu = f" chez {societe}" if societe else ""
    else:
        verbe = "I worked" if passe else "I work"
        repli = "Previously, I worked" if ancienne else verbe
        role = f"as {titre}" if titre else "in a role"
        lieu = f" at {societe}" if societe else ""
    debut = f"{periode}, {verbe}" if periode else repli
    return f"{debut} {role}{lieu}."


def _parcours(
    profile: ProfileDocument,
    classees: list[ExperienceDoc],
    termes: list[str],
    competences: list[str],
    langue: str,
) -> tuple[str, LetterFacts]:
    if not classees:
        return _parcours_sans_experience(profile, langue)

    principale = prioritize_achievements(classees[0], termes, _MAX_ACHIEVEMENTS)
    phrases = [_phrase_experience(principale, langue, ancienne=False)]
    texte_exp = " ".join(
        [principale.title or "", principale.description or "", *principale.achievements]
    )
    utilisees = [c for c in competences if mentions_term(texte_exp, c)][:_MAX_SKILLS_SHOWN]
    if utilisees:
        liste = _enumeration(utilisees, langue)
        phrases.append(
            f"J'y mobilise notamment {liste}." if langue == "fr" else f"I use {liste} there."
        )
    realisations = [a.rstrip(".;") for a in principale.achievements]
    if realisations:
        sep = " ; " if langue == "fr" else "; "
        intro = "Parmi mes réalisations : " if langue == "fr" else "Among my achievements: "
        phrases.append(f"{intro}{sep.join(realisations)}.")

    experiences = [(principale.company, principale.title)]
    if len(classees) > 1 and experience_mentions_terms(classees[1], termes):
        seconde = classees[1]
        phrase = _phrase_experience(seconde, langue, ancienne=True)
        if phrase:
            phrases.append(phrase)
            experiences.append((seconde.company, seconde.title))

    faits = LetterFacts(
        experiences=tuple(experiences),
        skills=tuple(utilisees),
        achievements=tuple(principale.achievements),
    )
    return " ".join(p for p in phrases if p), faits


def _parcours_sans_experience(profile: ProfileDocument, langue: str) -> tuple[str, LetterFacts]:
    """Sans expérience : formation, puis compétences du profil, telles quelles."""
    if profile.educations:
        edu = profile.educations[0]
        diplome = edu.degree or edu.field_of_study
        if diplome:
            ecole = f" ({edu.institution})" if edu.institution else ""
            texte = (
                f"Mon parcours de formation comprend {diplome}{ecole}."
                if langue == "fr"
                else f"My education includes {diplome}{ecole}."
            )
            return texte, LetterFacts(degrees=(diplome,))
    noms = [s.name for s in profile.skills[:_MAX_SKILLS_SHOWN]]
    liste = _enumeration(noms, langue)
    texte = (
        f"Mon profil inclut les compétences suivantes : {liste}."
        if langue == "fr"
        else f"My profile includes the following skills: {liste}."
    )
    return texte, LetterFacts(skills=tuple(noms))


def _valeur_ajoutee(
    context: CompanyOfferContext, options: CoverLetterOptions, competences: list[str]
) -> tuple[str, str | None]:
    fr = options.language == "fr"
    parties: list[str] = []
    if competences:
        liste = _enumeration(competences[:_MAX_SKILLS_SHOWN], options.language)
        parties.append(
            f"Plusieurs compétences demandées par l'offre figurent dans mon profil : {liste}."
            if fr
            else f"Several skills requested in the offer appear in my profile: {liste}."
        )
    if options.motivation:
        parties.append(options.motivation)
    if not parties:
        cible = context.company_name or ("votre équipe" if fr else "your team")
        parties.append(
            f"Un échange me permettrait de comprendre les besoins de {cible} et de détailler "
            "la façon dont mon parcours peut y répondre."
            if fr
            else f"A conversation would let me understand the needs of {cible} and explain how "
            "my background can address them."
        )
    return " ".join(parties), options.motivation


def _conclusion(context: CompanyOfferContext, langue: str) -> str:
    entreprise = context.company_name
    if langue == "fr":
        cible = f" avec {entreprise}" if entreprise else ""
        return (
            f"Je serais disponible pour un entretien afin de détailler mon parcours et d'échanger"
            f"{cible} sur les besoins du poste. Je vous remercie de l'attention portée à ma "
            "candidature."
        )
    cible = f" with {entreprise}" if entreprise else ""
    return (
        f"I would welcome an interview to discuss my background{cible} and the needs of the "
        "role. Thank you for considering my application."
    )
