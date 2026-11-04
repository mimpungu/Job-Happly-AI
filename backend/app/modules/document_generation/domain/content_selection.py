"""Sélection déterministe du contenu d'un CV ciblé sur une offre (niveau 0, sans IA).

- TASK-012-06 : contexte de génération (profil maître + offre).
- TASK-012-07 : choix des expériences pertinentes, restituées en ordre antéchronologique.
- TASK-012-08 : priorisation des réalisations et de l'accroche selon l'offre. Rien n'est
  reformulé ni ajouté : on ordonne et on retire, on ne crée pas de contenu.
- TASK-012-09 : mots-clés vérifiés, c'est-à-dire uniquement ceux que le candidat possède.

Contrat intermodule : la normalisation des compétences (synonymes, variantes) est celle du
moteur de matching (`job_intelligence.domain.matching.skills`), pour que « JS » et
« JavaScript » soient reconnus de la même façon à la sélection et au scoring.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.modules.job_intelligence.domain.matching.skills import canonique, skills_in_text

if TYPE_CHECKING:
    from app.modules.candidate_profile.domain.profile import (
        ExperienceDoc,
        ProfileDocument,
        SkillDoc,
    )

_SCORE_CURRENT = 5.0
_SCORE_TITLE_HIT = 4.0
_SCORE_TEXT_HIT = 2.0
_SUMMARY_SKILLS = 5


@dataclass(frozen=True)
class GenerationContext:
    """Contexte complet combinant profil candidat et offre cible."""

    profile: ProfileDocument
    offer_title: str | None = None
    offer_company: str | None = None
    offer_description: str | None = None
    required_skills: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    language: str = "fr"


@dataclass(frozen=True)
class AdaptedContent:
    """Contenu filtré et ordonné pour le CV ciblé."""

    adapted_profile: ProfileDocument
    target_title: str | None
    adapted_summary: str | None
    summary_is_generated: bool
    highlight_skills: tuple[str, ...]
    matched_keywords: tuple[str, ...]
    missing_keywords: tuple[str, ...]
    offer_terms: tuple[str, ...]


def build_generation_context(
    profile: ProfileDocument,
    *,
    offer_title: str | None = None,
    offer_company: str | None = None,
    offer_description: str | None = None,
    required_skills: tuple[str, ...] = (),
    keywords: tuple[str, ...] = (),
    language: str = "fr",
) -> GenerationContext:
    """Construit le contexte de génération à partir du profil et de l'offre (TASK-012-06)."""
    return GenerationContext(
        profile=profile,
        offer_title=offer_title,
        offer_company=offer_company,
        offer_description=offer_description,
        required_skills=required_skills,
        keywords=keywords,
        language=language,
    )


def adapt_resume_content(
    context: GenerationContext,
    *,
    max_experiences: int | None = None,
    max_achievements: int | None = None,
    custom_title: str | None = None,
) -> AdaptedContent:
    """Sélectionne et ordonne le contenu du profil maître pour l'offre ciblée."""
    profile = context.profile
    termes = _termes_de_l_offre(context)

    verifies = verified_skills(profile, termes)
    presentes = {canonique(s.name) for s in profile.skills}
    manquants = [t for t in termes if canonique(t) not in presentes]

    titre = custom_title or context.offer_title or profile.identity.headline
    experiences = _selectionner_experiences(
        profile.experiences,
        termes=termes,
        max_experiences=max_experiences,
        max_achievements=max_achievements,
    )
    competences = _prioriser_competences(profile.skills, verifies)

    resume_perso = profile.summary
    resume = resume_perso or _accroche_factuelle(titre, verifies, context.language)

    return AdaptedContent(
        adapted_profile=profile.model_copy(
            update={"experiences": experiences, "skills": competences}
        ),
        target_title=titre,
        adapted_summary=resume,
        summary_is_generated=resume_perso is None and resume is not None,
        highlight_skills=tuple(verifies),
        matched_keywords=tuple(verifies),
        missing_keywords=tuple(manquants),
        offer_terms=tuple(termes),
    )


def resolve_offer_terms(
    profile: ProfileDocument,
    *,
    required_skills: tuple[str, ...] = (),
    keywords: tuple[str, ...] = (),
    description: str | None = None,
) -> list[str]:
    """Termes explicites de l'offre ; à défaut, compétences du candidat citées dans l'annonce."""
    explicites = [t.strip() for t in (*required_skills, *keywords) if t.strip()]
    termes = list({canonique(t): t for t in explicites}.values())
    if termes or not description:
        return termes
    return skills_in_text(tuple(s.name for s in profile.skills), description)


def _termes_de_l_offre(contexte: GenerationContext) -> list[str]:
    return resolve_offer_terms(
        contexte.profile,
        required_skills=contexte.required_skills,
        keywords=contexte.keywords,
        description=contexte.offer_description,
    )


def verified_skills(profile: ProfileDocument, termes: list[str]) -> list[str]:
    """Compétences du profil (nom exact) que demandent les termes de l'offre, sans doublon."""
    par_forme = {canonique(s.name): s.name for s in profile.skills}
    return list(dict.fromkeys(par_forme[canonique(t)] for t in termes if canonique(t) in par_forme))


def rank_experiences(
    experiences: tuple[ExperienceDoc, ...], termes: list[str]
) -> list[ExperienceDoc]:
    """Expériences de la plus à la moins pertinente pour l'offre (ordre d'origine à égalité)."""
    classees = sorted(
        enumerate(experiences), key=lambda item: (-score_experience(item[1], termes), item[0])
    )
    return [exp for _, exp in classees]


def mentions_term(texte: str, terme: str) -> bool:
    motif = rf"(?<![\w+#]){re.escape(terme)}(?![\w+#])"
    return re.search(motif, texte, re.IGNORECASE) is not None


def experience_mentions_terms(exp: ExperienceDoc, termes: list[str]) -> bool:
    """Vrai si l'expérience cite au moins un terme de l'offre (hors simple bonus « en cours »)."""
    texte = " ".join([exp.title or "", exp.description or "", *exp.achievements])
    return any(mentions_term(texte, t) for t in termes)


def score_experience(exp: ExperienceDoc, termes: list[str]) -> float:
    score = _SCORE_CURRENT if exp.is_current else 0.0
    titre = exp.title or ""
    corps = " ".join([exp.description or "", *exp.achievements])
    for terme in termes:
        if mentions_term(titre, terme):
            score += _SCORE_TITLE_HIT
        if mentions_term(corps, terme):
            score += _SCORE_TEXT_HIT
    return score


def _cle_chronologique(exp: ExperienceDoc) -> tuple[int, int]:
    if exp.is_current:
        return (9999, 12)
    jour = exp.end or exp.start
    return jour.sort_key() if jour else (0, 0)


def _selectionner_experiences(
    experiences: tuple[ExperienceDoc, ...],
    *,
    termes: list[str],
    max_experiences: int | None,
    max_achievements: int | None,
) -> tuple[ExperienceDoc, ...]:
    """Garde les plus pertinentes, puis les restitue de la plus récente à la plus ancienne."""
    gardees = rank_experiences(experiences, termes)[:max_experiences]
    gardees.sort(key=_cle_chronologique, reverse=True)
    return tuple(prioritize_achievements(e, termes, max_achievements) for e in gardees)


def prioritize_achievements(
    exp: ExperienceDoc, termes: list[str], maximum: int | None
) -> ExperienceDoc:
    """Place en tête les réalisations qui parlent de l'offre ; tronque sans jamais réécrire."""
    if len(exp.achievements) < 2 and maximum is None:
        return exp
    classees = sorted(
        enumerate(exp.achievements),
        key=lambda item: (-sum(mentions_term(item[1], t) for t in termes), item[0]),
    )
    ordonnees = tuple(texte for _, texte in classees)
    if maximum is not None:
        ordonnees = ordonnees[:maximum]
    return exp.model_copy(update={"achievements": ordonnees})


def _prioriser_competences(
    skills: tuple[SkillDoc, ...], verifies: list[str]
) -> tuple[SkillDoc, ...]:
    """Les compétences que l'offre demande passent en tête, l'ordre relatif est conservé."""
    prioritaires = {canonique(v) for v in verifies}
    return tuple(sorted(skills, key=lambda s: canonique(s.name) not in prioritaires))


def _accroche_factuelle(titre: str | None, verifies: list[str], language: str) -> str | None:
    """Accroche bâtie uniquement sur des données du profil : aucun chiffre ni qualificatif."""
    if not verifies:
        return None
    competences = ", ".join(verifies[:_SUMMARY_SKILLS])
    anglais = language.split("-")[0].lower() == "en"
    if titre:
        modele = (
            "{titre} — key skills for this role: {c}."
            if anglais
            else ("{titre} — compétences clés pour ce poste : {c}.")
        )
    else:
        modele = (
            "Key skills for this role: {c}." if anglais else "Compétences clés pour ce poste : {c}."
        )
    return modele.format(titre=titre, c=competences)
