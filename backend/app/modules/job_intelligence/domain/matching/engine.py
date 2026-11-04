"""Calcul du score de correspondance : critères, pondération, fiabilité et explications."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from decimal import Decimal

from app.modules.job_intelligence.domain.matching.criteria import (
    evaluate_contract,
    evaluate_education,
    evaluate_experience,
    evaluate_freshness,
    evaluate_location,
    evaluate_remote,
    evaluate_salary,
    evaluate_title,
)
from app.modules.job_intelligence.domain.matching.models import (
    CRITERION_LABELS,
    Criterion,
    CriterionResult,
    MatchItem,
    MatchKind,
    MatchResult,
    OfferFacts,
    ProfileFacts,
    Reliability,
    Status,
    Weights,
)
from app.modules.job_intelligence.domain.matching.offer_requirements import (
    Importance,
    extract_requirements,
)
from app.modules.job_intelligence.domain.matching.skills import SkillAnalysis, evaluate_skills
from app.modules.job_intelligence.domain.matching.weights import DEFAULT_WEIGHTS, weights_version

SEUIL_FIABILITE_ELEVEE = Decimal("0.7")
SEUIL_FIABILITE_MOYENNE = Decimal("0.4")
CENT = Decimal(100)


def _kind_pour_score(score: Decimal) -> MatchKind:
    if score >= 1:
        return MatchKind.PRESENT
    return MatchKind.PARTIAL if score > 0 else MatchKind.ABSENT


def _evaluate_mandatory(
    competences: SkillAnalysis,
    experience: CriterionResult,
    formation: CriterionResult,
    exigences_annees_obligatoire: bool,
    exigences_formation_obligatoire: bool,
    poids: Decimal,
) -> CriterionResult:
    """Exigences que l'offre déclare **explicitement** obligatoires (compétences, années, diplôme)."""
    items: list[MatchItem] = []
    scores: list[Decimal] = []
    for t in competences.terms:
        if t.importance is Importance.MANDATORY:
            scores.append(
                {MatchKind.PRESENT: Decimal(1), MatchKind.PARTIAL: Decimal("0.5")}.get(
                    t.kind, Decimal(0)
                )
            )
            items.append(MatchItem(t.kind, t.label, "Compétence obligatoire"))
    for resultat, obligatoire, libelle in (
        (experience, exigences_annees_obligatoire, "Expérience minimale"),
        (formation, exigences_formation_obligatoire, "Niveau d'études"),
    ):
        if obligatoire and resultat.status is Status.EVALUATED and resultat.score is not None:
            scores.append(resultat.score)
            items.append(MatchItem(_kind_pour_score(resultat.score), libelle, resultat.explanation))
    if not scores:
        return CriterionResult(
            Criterion.MANDATORY,
            Status.MISSING_DATA,
            poids,
            None,
            "L'offre ne marque aucune exigence comme obligatoire, ou elles ne sont pas évaluables.",
        )
    score = sum(scores, Decimal(0)) / len(scores)
    manquantes = sum(1 for i in items if i.kind is MatchKind.ABSENT)
    partielles = sum(1 for i in items if i.kind is MatchKind.PARTIAL)
    explication = f"{len(items)} exigence(s) obligatoire(s) repérée(s) : {len(items) - manquantes - partielles} satisfaite(s), {partielles} partielle(s), {manquantes} non satisfaite(s)."
    return CriterionResult(
        Criterion.MANDATORY, Status.EVALUATED, poids, score, explication, items=tuple(items)
    )


def _fiabilite(couverture: Decimal) -> Reliability:
    if couverture >= SEUIL_FIABILITE_ELEVEE:
        return Reliability.HIGH
    return Reliability.MEDIUM if couverture >= SEUIL_FIABILITE_MOYENNE else Reliability.LOW


def _noms(criteres: list[CriterionResult]) -> str:
    return ", ".join(CRITERION_LABELS[c.criterion].lower() for c in criteres)


def compute_match(
    profil: ProfileFacts,
    offre: OfferFacts,
    maintenant: datetime,
    poids: Weights = DEFAULT_WEIGHTS,
) -> MatchResult:
    """Score déterministe : mêmes entrées, même date de référence, mêmes poids = même résultat.

    Seuls les critères évalués entrent dans la moyenne pondérée ; ceux dont les données manquent
    en sortent et leur poids est redistribué. La `coverage` dit quelle part du poids total a pu
    être évaluée : un score sur 30 % des critères n'a pas la solidité d'un score sur 90 %.
    """
    exigences = extract_requirements(offre.description)
    competences = evaluate_skills(profil, exigences, poids.get(Criterion.SKILLS))
    experience = evaluate_experience(
        profil, exigences.years, maintenant, poids.get(Criterion.EXPERIENCE)
    )
    formation = evaluate_education(profil, exigences.education, poids.get(Criterion.EDUCATION))

    tous = {
        Criterion.JOB_TITLE: evaluate_title(profil, offre, poids.get(Criterion.JOB_TITLE)),
        Criterion.SKILLS: competences.result,
        Criterion.EXPERIENCE: experience,
        Criterion.EDUCATION: formation,
        Criterion.LOCATION: evaluate_location(profil, offre, poids.get(Criterion.LOCATION)),
        Criterion.CONTRACT: evaluate_contract(profil, offre, poids.get(Criterion.CONTRACT)),
        Criterion.SALARY: evaluate_salary(profil, offre, poids.get(Criterion.SALARY)),
        Criterion.REMOTE: evaluate_remote(profil, offre, poids.get(Criterion.REMOTE)),
        Criterion.FRESHNESS: evaluate_freshness(offre, maintenant, poids.get(Criterion.FRESHNESS)),
        Criterion.MANDATORY: _evaluate_mandatory(
            competences,
            experience,
            formation,
            bool(exigences.years and exigences.years.mandatory),
            bool(exigences.education and exigences.education.mandatory),
            poids.get(Criterion.MANDATORY),
        ),
    }
    # Un critère pondéré à 0 est désactivé : il n'apparaît pas et ne pèse pas.
    actifs = [r for c, r in tous.items() if poids.get(c) > 0]
    evalues = [r for r in actifs if r.status is Status.EVALUATED and r.score is not None]
    manquants = [r for r in actifs if r.status is Status.MISSING_DATA]
    poids_total = sum((r.weight for r in actifs), Decimal(0))
    poids_evalue = sum((r.weight for r in evalues), Decimal(0))
    couverture = poids_evalue / poids_total if poids_total else Decimal(0)

    if not evalues:
        return MatchResult(
            score=None,
            coverage=Decimal(0),
            reliability=Reliability.LOW,
            weights_version=weights_version(poids),
            criteria=tuple(actifs),
            summary="Score non calculable : aucune donnée du profil ne peut être comparée à cette offre.",
        )

    score = (
        CENT * sum((r.weight * (r.score or Decimal(0)) for r in evalues), Decimal(0)) / poids_evalue
    )
    fiabilite = _fiabilite(couverture)

    forts = [r for r in evalues if (r.score or 0) >= Decimal("0.75")]
    faibles = [r for r in evalues if (r.score or 0) < Decimal("0.5")]
    morceaux = [
        f"Score {score:.0f}/100 — fiabilité {'élevée' if fiabilite is Reliability.HIGH else 'moyenne' if fiabilite is Reliability.MEDIUM else 'faible'} "
        f"({len(evalues)} critère(s) évalué(s) sur {len(actifs)})."
    ]
    if forts:
        morceaux.append(f"Points forts : {_noms(forts)}.")
    if faibles:
        morceaux.append(f"Points d'attention : {_noms(faibles)}.")
    if manquants:
        morceaux.append(f"Données manquantes (non comptées) : {_noms(manquants)}.")

    items = [replace(i, criterion=r.criterion) for r in evalues for i in r.items]
    return MatchResult(
        score=score.quantize(Decimal("0.01")),
        coverage=couverture.quantize(Decimal("0.01")),
        reliability=fiabilite,
        weights_version=weights_version(poids),
        criteria=tuple(actifs),
        matches=tuple(i for i in items if i.kind in (MatchKind.PRESENT, MatchKind.PARTIAL)),
        gaps=tuple(i for i in items if i.kind in (MatchKind.ABSENT, MatchKind.UNVERIFIABLE)),
        summary=" ".join(morceaux),
    )
