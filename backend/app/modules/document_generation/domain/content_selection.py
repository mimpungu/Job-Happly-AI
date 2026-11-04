"""Sélection déterministe et adaptation du contenu pour un CV ciblé sur une offre.

Respecte les tâches :
- TASK-012-06 : Construire le contexte de génération.
- TASK-012-07 : Sélectionner les expériences pertinentes.
- TASK-012-08 : Adapter les formulations et prioriser les réalisations.
- TASK-012-09 : Intégrer les mots-clés vérifiés sans bourrage.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.candidate_profile.domain.profile import (
        ExperienceDoc,
        ProfileDocument,
        SkillDoc,
    )


@dataclass(frozen=True)
class GenerationContext:
    """Contexte complet combinant profil candidat et offre cible."""

    profile: ProfileDocument
    offer_title: str | None = None
    offer_company: str | None = None
    offer_description: str | None = None
    required_skills: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()


@dataclass(frozen=True)
class AdaptedContent:
    """Contenu filtré et adapté pour le CV ciblé."""

    adapted_profile: ProfileDocument
    target_title: str
    adapted_summary: str | None
    highlight_skills: tuple[str, ...]
    matched_keywords: tuple[str, ...]
    missing_keywords: tuple[str, ...]


def build_generation_context(
    profile: ProfileDocument,
    *,
    offer_title: str | None = None,
    offer_company: str | None = None,
    offer_description: str | None = None,
    required_skills: tuple[str, ...] = (),
    keywords: tuple[str, ...] = (),
) -> GenerationContext:
    """Construit le contexte de génération à partir du profil et de l'offre (TASK-012-06)."""
    return GenerationContext(
        profile=profile,
        offer_title=offer_title,
        offer_company=offer_company,
        offer_description=offer_description,
        required_skills=required_skills,
        keywords=keywords,
    )


def adapt_resume_content(
    context: GenerationContext,
    *,
    max_experiences: int | None = None,
    custom_title: str | None = None,
) -> AdaptedContent:
    """Sélectionne les expériences pertinentes et intègre les mots-clés vérifiés."""
    profile = context.profile

    termes_offre = _extraire_termes_offre(context)

    mots_candidat = {s.name.casefold(): s.name for s in profile.skills}
    mots_verifies: list[str] = []
    mots_manquants: list[str] = []

    for terme in termes_offre:
        terme_bas = terme.casefold()
        if terme_bas in mots_candidat:
            mots_verifies.append(mots_candidat[terme_bas])
        else:
            mots_manquants.append(terme)

    titre_cible = (
        custom_title or context.offer_title or profile.identity.headline or "Professionnel"
    )

    experiences_triees = _scorer_et_trier_experiences(
        profile.experiences, termes_offre=termes_offre, max_exp=max_experiences
    )

    skills_reorganisees = _reorganiser_competences(profile.skills, mots_verifies=mots_verifies)

    accroche = _adapter_accroche(profile, titre_cible=titre_cible, mots_verifies=mots_verifies)

    profil_adapte = profile.model_copy(
        update={
            "experiences": tuple(experiences_triees),
            "skills": tuple(skills_reorganisees),
        }
    )

    return AdaptedContent(
        adapted_profile=profil_adapte,
        target_title=titre_cible,
        adapted_summary=accroche,
        highlight_skills=tuple(mots_verifies),
        matched_keywords=tuple(mots_verifies),
        missing_keywords=tuple(mots_manquants),
    )


def _extraire_termes_offre(ctx: GenerationContext) -> list[str]:
    termes: list[str] = []
    for s in ctx.required_skills:
        if s and s.strip():
            termes.append(s.strip())
    for kw in ctx.keywords:
        if kw and kw.strip() and kw not in termes:
            termes.append(kw.strip())

    if ctx.offer_description and not termes:
        mots = re.findall(r"\b[A-Za-zÀ-ÿ0-9+#.-]{3,}\b", ctx.offer_description)
        stopwords = {"les", "des", "pour", "avec", "dans", "nous", "vous"}
        frequence: dict[str, int] = {}
        for m in mots:
            m_low = m.casefold()
            if len(m_low) >= 3 and m_low not in stopwords:
                frequence[m] = frequence.get(m, 0) + 1
        termes = [m for m, _ in sorted(frequence.items(), key=lambda kv: kv[1], reverse=True)[:15]]

    return list(dict.fromkeys(termes))


def _scorer_et_trier_experiences(
    experiences: tuple[ExperienceDoc, ...],
    *,
    termes_offre: list[str],
    max_exp: int | None,
) -> list[ExperienceDoc]:
    """Score et ordonne les expériences selon leur adéquation avec l'offre."""
    if not experiences:
        return []

    scores: list[tuple[float, int, ExperienceDoc]] = []
    termes_lower = [t.casefold() for t in termes_offre]

    for index, exp in enumerate(experiences):
        score = 0.0

        if exp.is_current:
            score += 5.0
        elif exp.start:
            score += max(0.0, (exp.start.year - 2015) * 0.5)

        titre = (exp.title or "").casefold()
        for t in termes_lower:
            if t in titre:
                score += 4.0

        texte_complet = (exp.description or "") + " " + " ".join(exp.achievements)
        texte_lower = texte_complet.casefold()
        for t in termes_lower:
            if t in texte_lower:
                score += 2.0

        scores.append((score, index, exp))

    scores.sort(key=lambda item: (-item[0], item[1]))

    selectionnees = [item[2] for item in scores]
    if max_exp is not None and max_exp > 0:
        selectionnees = selectionnees[:max_exp]

    return selectionnees


def _reorganiser_competences(
    skills: tuple[SkillDoc, ...], *, mots_verifies: list[str]
) -> list[SkillDoc]:
    """Place les compétences requises vérifiées au début de leur catégorie."""
    mots_set = {m.casefold() for m in mots_verifies}

    prioritaires: list[SkillDoc] = []
    autres: list[SkillDoc] = []

    for s in skills:
        if s.name.casefold() in mots_set:
            prioritaires.append(s)
        else:
            autres.append(s)

    return prioritaires + autres


def _adapter_accroche(
    profile: ProfileDocument, *, titre_cible: str, mots_verifies: list[str]
) -> str | None:
    """Adapte ou synthétise l'accroche professionnelle."""
    if profile.summary:
        return profile.summary

    annees_exp = len(profile.experiences) * 2
    annees_str = f"avec plus de {annees_exp} ans d'expérience" if annees_exp >= 3 else "passionné"

    mots_str = (
        ", ".join(mots_verifies[:4])
        if mots_verifies
        else "le développement et l'ingénierie logicielle"
    )

    return (
        f"{titre_cible} {annees_str}, spécialisé dans {mots_str}. "
        "Rigoureux et orienté résultats, apportant une valeur concrète dès la prise de poste."
    )
