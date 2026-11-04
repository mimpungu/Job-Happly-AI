"""Contrôle des faits et audit éditorial de la lettre (TASK-013-09, 10, 11, 18).

Deux niveaux, distincts :
- `verify_letter_facts` : structurel, bloquant. Tout fait cité (employeur, intitulé, compétence,
  réalisation, coordonnées) doit exister dans le profil maître ; tout nombre du texte généré
  doit provenir du profil ou de l'offre. Les textes saisis par l'utilisateur ne sont pas jugés.
- `audit_letter` : éditorial, indicatif (grille sur 100 du prompt maître §12).

Limite assumée : la correction orthographique s'arrête aux erreurs typographiques évidentes
(mots répétés, majuscule oubliée, ponctuation, parenthèses) ; aucun dictionnaire n'est embarqué.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from app.modules.document_generation.domain.content_selection import (
    mentions_term,
    resolve_offer_terms,
)
from app.modules.document_generation.domain.cover_letter_models import (
    CompanyOfferContext,
    CoverLetterAudit,
    CoverLetterContent,
    count_words,
)
from app.modules.document_generation.domain.spelling import SpellingChecker, find_spelling_issues
from app.modules.job_intelligence.domain.matching.skills import canonique

if TYPE_CHECKING:
    from app.modules.candidate_profile.domain.profile import ProfileDocument

OPTIMAL_MIN_WORDS = 250
OPTIMAL_MAX_WORDS = 350
_ACCEPTABLE_MIN_WORDS = 150
_ACCEPTABLE_MAX_WORDS = 400
_VERY_SHORT_WORDS = 120
_PASS_SCORE = 70
_MAX_PAGES = 1
_RESPONSIBILITY_PROBE = 25  # caractères comparés pour reconnaître une mission citée

# Formulations proscrites par le prompt maître (§7), comparées après normalisation.
_CLICHES = (
    "extrêmement motivé",
    "très motivé",
    "dynamique et motivé",
    "candidat idéal",
    "candidat parfait",
    "candidate idéale",
    "profil est idéal",
    "véritable opportunité",
    "formidable opportunité",
    "entière disposition",
    "me permets de vous adresser",
    "à la recherche d'un emploi",
    "fort d'une solide expérience",
    "forte d'une solide expérience",
    "perfect candidate",
    "ideal candidate",
    "perfect fit",
    "dynamic and motivated",
    "extremely motivated",
)
_INTERVIEW = re.compile(r"entretien|rencontre|interview|meet(?:ing)?\b|discuss", re.IGNORECASE)
_TONE = {
    "fr": (
        re.compile(r"madame|monsieur", re.I),
        re.compile(r"agréer|salutations|cordialement", re.I),
    ),
    "en": (re.compile(r"\bdear\b", re.I), re.compile(r"sincerely|faithfully|regards", re.I)),
}
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
_REPEATED_WORD = re.compile(r"\b(\w{2,})\s+\1\b", re.IGNORECASE)
_LEGIT_REPEATS = frozenset({"nous", "vous", "that", "had", "bye"})
_LOWER_AFTER_STOP = re.compile(r"(\w{4,})[.!?]\s+([a-zà-ÿ])")
_NO_SPACE_AFTER = re.compile(r"[a-zà-ÿ][,;][A-Za-zÀ-ÿ]")
_DOUBLE_PUNCT = re.compile(r"[,;:]{2,}|\.{4,}|\?{2,}|!{2,}")


def normalize(texte: str) -> str:
    """Casse, apostrophes et espaces unifiés pour comparer des textes."""
    sans_typo = texte.replace("\u2019", "'").replace("\u2018", "'")
    sans_typo = sans_typo.replace("\u00a0", " ").replace("\u202f", " ")
    return re.sub(r"\s+", " ", sans_typo).strip().casefold()


def _nombres(texte: str) -> set[str]:
    return {n.replace(",", ".") for n in _NUMBER.findall(texte)}


def find_writing_issues(texte: str) -> list[str]:
    """Erreurs d'écriture évidentes, détectables sans dictionnaire."""
    problemes: list[str] = []
    for m in _REPEATED_WORD.finditer(texte):
        if m.group(1).casefold() not in _LEGIT_REPEATS:
            problemes.append(f"Mot répété : « {m.group(0)} »")
    if _LOWER_AFTER_STOP.search(texte):
        problemes.append("Phrase commençant par une minuscule.")
    if _NO_SPACE_AFTER.search(texte):
        problemes.append("Espace manquant après une virgule ou un point-virgule.")
    if _DOUBLE_PUNCT.search(texte):
        problemes.append("Ponctuation doublée.")
    if texte.count("(") != texte.count(")"):
        problemes.append("Parenthèses non appariées.")
    if texte.count("«") != texte.count("»"):
        problemes.append("Guillemets français non appariés.")
    return problemes


def _termes_du_profil(
    profile: ProfileDocument | None, context: CompanyOfferContext | None
) -> list[str]:
    """Noms propres et jargon que le dictionnaire ne connaît pas : jamais des fautes."""
    termes: list[str] = []
    if profile is not None:
        termes += [s.name for s in profile.skills]
        termes += [e.company or "" for e in profile.experiences]
        termes += [e.institution or "" for e in profile.educations]
    if context is not None:
        termes += [context.company_name or "", context.job_title, *context.required_skills]
    return termes


def _corpus_de_nombres(
    profile: ProfileDocument, context: CompanyOfferContext | None, today: date
) -> set[str]:
    sources = [profile.model_dump_json()]
    if context is not None:
        sources += [
            context.offer_text,
            context.job_title,
            context.company_name or "",
            context.company_location or "",
        ]
    autorises = {str(today.year), str(today.day)}
    return _nombres(" ".join(sources)) | autorises


def verify_letter_facts(
    content: CoverLetterContent,
    profile: ProfileDocument,
    context: CompanyOfferContext,
    *,
    today: date,
) -> tuple[str, ...]:
    """Problèmes factuels de la lettre ; vide si tout provient du profil ou de l'offre."""
    problemes: list[str] = []
    identite = profile.identity
    attendu = f"{identite.first_name or ''} {identite.last_name or ''}".strip()
    for libelle, genere, source in (
        ("nom", content.candidate_name, attendu),
        ("e-mail", content.candidate_email, identite.email),
        ("téléphone", content.candidate_phone, identite.phone),
        ("ville", content.candidate_city, identite.city),
    ):
        if genere != source:
            problemes.append(f"Coordonnée « {libelle} » différente du profil maître.")

    employeurs = {
        (normalize(e.company or ""), normalize(e.title or "")) for e in profile.experiences
    }
    for societe, titre in content.facts.experiences:
        if (normalize(societe or ""), normalize(titre or "")) not in employeurs:
            problemes.append(f"Expérience absente du profil maître : {titre} chez {societe}.")

    competences = {canonique(s.name) for s in profile.skills}
    problemes += [
        f"Compétence absente du profil maître : {c}."
        for c in content.facts.skills
        if canonique(c) not in competences
    ]
    realisations = {a for e in profile.experiences for a in e.achievements}
    problemes += [
        f"Réalisation absente du profil maître : {a}."
        for a in content.facts.achievements
        if a not in realisations
    ]
    diplomes = {
        d for e in profile.educations for d in (e.degree, e.field_of_study) if d is not None
    }
    problemes += [
        f"Diplôme absent du profil maître : {d}."
        for d in content.facts.degrees
        if d not in diplomes
    ]

    genere = content.body_text()
    # Du plus long au plus court : un texte inclus dans un autre ne doit pas le casser.
    for texte_utilisateur in sorted(content.user_written, key=len, reverse=True):
        genere = genere.replace(texte_utilisateur, " ")
    corpus = _corpus_de_nombres(profile, context, today)
    problemes += [
        f"Nombre sans source dans le profil ou l'offre : {n}."
        for n in sorted(_nombres(genere) - corpus)
    ]
    return tuple(problemes)


@dataclass(frozen=True)
class _Inputs:
    """Ce que l'audit a besoin de savoir, que la lettre soit générée ou éditée."""

    body: str
    full: str
    language: str
    parts_present: bool
    has_user_text: bool
    employer_cited: bool
    concrete_cited: bool
    recipient_personalized: bool
    fact_issues: tuple[str, ...]


def audit_letter(
    content: CoverLetterContent,
    profile: ProfileDocument,
    context: CompanyOfferContext,
    *,
    today: date,
    page_count: int | None = None,
    spelling: SpellingChecker | None = None,
) -> CoverLetterAudit:
    """Audit d'une lettre générée (structure connue)."""
    return _audit(
        _Inputs(
            body=content.body_text(),
            full=content.full_text(),
            language=content.language,
            parts_present=all(content.body_paragraphs()),
            has_user_text=bool(content.user_written),
            employer_cited=bool(content.facts.experiences or content.facts.degrees),
            concrete_cited=bool(content.facts.skills or content.facts.achievements),
            recipient_personalized=bool(content.recipient_name or content.recipient_department),
            fact_issues=verify_letter_facts(content, profile, context, today=today),
        ),
        profile,
        context,
        page_count,
        spelling,
    )


def audit_letter_text(
    texte: str,
    *,
    language: str,
    profile: ProfileDocument | None,
    context: CompanyOfferContext | None,
    today: date,
    page_count: int | None,
    spelling: SpellingChecker | None = None,
) -> CoverLetterAudit:
    """Audit d'une lettre éditée, à partir du texte extrait du PDF (structure inconnue).

    Le texte entier est analysé, en-tête compris : le nombre de mots est donc légèrement
    surévalué par rapport à celui d'une lettre générée.
    """
    problemes_faits: list[str] = []
    if profile is None:
        problemes_faits.append("Profil validé introuvable : cohérence avec le CV non vérifiable.")
    else:
        corpus = _corpus_de_nombres(profile, context, today)
        problemes_faits += [
            f"Nombre sans source dans le profil ou l'offre : {n}."
            for n in sorted(_nombres(texte) - corpus)
        ]
    normalise = normalize(texte)
    employeurs = [e.company for e in profile.experiences if e.company] if profile else []
    concrets = [s.name for s in profile.skills] if profile else []
    return _audit(
        _Inputs(
            body=texte,
            full=texte,
            language=language,
            parts_present=count_words(texte) >= _VERY_SHORT_WORDS,
            has_user_text=True,  # texte édité par l'utilisateur : origine indistinguable
            employer_cited=any(normalize(e) in normalise for e in employeurs),
            concrete_cited=any(mentions_term(texte, c) for c in concrets),
            recipient_personalized=False,
            fact_issues=tuple(problemes_faits),
        ),
        profile,
        context,
        page_count,
        spelling,
    )


def _audit(
    data: _Inputs,
    profile: ProfileDocument | None,
    context: CompanyOfferContext | None,
    page_count: int | None,
    spelling: SpellingChecker | None = None,
) -> CoverLetterAudit:
    issues: list[str] = list(data.fact_issues)
    texte = normalize(data.full)
    corps = normalize(data.body)

    cliches = [c for c in _CLICHES if c in texte]
    issues += [f"Formulation artificielle à éviter : « {c} »" for c in cliches]
    ecriture = find_writing_issues(data.body) + find_spelling_issues(
        data.body, data.language, spelling, ignore=_termes_du_profil(profile, context)
    )
    issues += ecriture

    mots = count_words(data.body)
    if mots < _ACCEPTABLE_MIN_WORDS:
        statut = "short"
    elif mots > _ACCEPTABLE_MAX_WORDS:
        statut = "long"
    else:
        statut = "optimal" if OPTIMAL_MIN_WORDS <= mots <= OPTIMAL_MAX_WORDS else "acceptable"
    if mots < OPTIMAL_MIN_WORDS:
        issues.append(
            f"Lettre courte ({mots} mots, 250 à 350 visés) : ajoutez votre motivation personnelle."
        )
    elif mots > OPTIMAL_MAX_WORDS:
        issues.append(f"Lettre longue ({mots} mots, 250 à 350 visés) : resserrez le propos.")
    if page_count is not None and page_count > _MAX_PAGES:
        issues.append(f"La lettre dépasse une page ({page_count} pages).")

    relevance = _pertinence(data, profile, context, texte, corps, issues)
    personalization = _personnalisation(data, context, texte, issues)
    experience = (10 if data.employer_cited else 0) + (10 if data.concrete_cited else 0)
    if not data.employer_cited:
        issues.append("Aucune expérience ni formation du CV n'est citée.")
    if not data.concrete_cited:
        issues.append("Aucune compétence ni réalisation concrète du CV n'est citée.")

    salutation, formule = _TONE.get(data.language, _TONE["fr"])
    ton_ok = bool(salutation.search(data.full) and formule.search(data.full))
    if not ton_ok:
        issues.append("Salutation ou formule de politesse non conforme à la langue de la lettre.")
    editorial = (0 if cliches else 8) + max(0, 4 - len(ecriture)) + (3 if ton_ok else 0)

    entretien = bool(_INTERVIEW.search(data.full))
    if not entretien:
        issues.append("Aucune demande d'entretien.")
    tient_en_une_page = page_count is None or page_count <= _MAX_PAGES
    longueur = 3 if statut == "optimal" else 2 if statut == "acceptable" else 0
    structure = (
        (4 if data.parts_present else 0)
        + (3 if entretien else 0)
        + (longueur if tient_en_une_page else 0)
    )

    total = relevance + personalization + experience + editorial + structure
    coherent = not data.fact_issues
    return CoverLetterAudit(
        score=total,
        passed=total >= _PASS_SCORE and not cliches and coherent and tient_en_une_page,
        relevance_score=relevance,
        personalization_score=personalization,
        experience_score=experience,
        editorial_score=editorial,
        structure_score=structure,
        word_count=mots,
        length_status=statut,
        is_length_optimal=statut == "optimal",
        cv_coherent=coherent,
        page_count=page_count,
        generic_phrases_detected=tuple(cliches),
        spelling_issues=tuple(ecriture),
        issues=tuple(issues),
    )


def _pertinence(
    data: _Inputs,
    profile: ProfileDocument | None,
    context: CompanyOfferContext | None,
    texte: str,
    corps: str,
    issues: list[str],
) -> int:
    """30 points : intitulé du poste, termes de l'offre, missions citées."""
    if context is None:
        return 0
    points = 0
    if normalize(context.job_title) in texte:
        points += 10
    else:
        issues.append("L'intitulé exact du poste n'est pas mentionné.")

    termes = (
        resolve_offer_terms(
            profile, required_skills=context.required_skills, description=context.offer_text
        )
        if profile is not None
        else list(context.required_skills)
    )
    if not termes or any(normalize(t) in corps for t in termes):
        points += 10
    else:
        issues.append("Aucun terme de l'offre n'apparaît dans la lettre.")

    if not context.responsibilities or any(
        normalize(r)[:_RESPONSIBILITY_PROBE] in corps for r in context.responsibilities
    ):
        points += 10
    else:
        issues.append("Aucune mission du poste n'est reprise.")
    return points


def _personnalisation(
    data: _Inputs, context: CompanyOfferContext | None, texte: str, issues: list[str]
) -> int:
    """25 points : entreprise, destinataire ou lieu, apport personnel de l'utilisateur."""
    if context is None:
        return 0
    points = 0
    if not context.company_name or normalize(context.company_name) in texte:
        points += 10
    else:
        issues.append("Le nom de l'entreprise n'apparaît pas dans la lettre.")
    lieu_cite = bool(context.company_location and normalize(context.company_location) in texte)
    if data.recipient_personalized or lieu_cite or not context.company_location:
        points += 5
    if data.has_user_text:
        points += 10
    else:
        issues.append("Aucun texte personnel : ajoutez votre motivation (champ « motivation »).")
    return points
