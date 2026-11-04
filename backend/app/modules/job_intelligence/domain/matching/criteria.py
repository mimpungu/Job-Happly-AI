"""Critères du score : chacun renvoie un `CriterionResult` évalué, ou « données manquantes »."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app.modules.job_intelligence.domain.matching.models import (
    Criterion,
    CriterionResult,
    ExperiencePeriod,
    MatchItem,
    MatchKind,
    OfferFacts,
    ProfileFacts,
    Status,
    YearMonth,
)
from app.modules.job_intelligence.domain.matching.offer_requirements import (
    EducationRequirement,
    YearsRequirement,
    niveau_d_etudes,
)
from app.modules.job_intelligence.domain.matching.text import fold, words

D = Decimal
UN = D(1)
ZERO = D(0)


def _manquant(critere: Criterion, poids: Decimal, raison: str) -> CriterionResult:
    return CriterionResult(critere, Status.MISSING_DATA, poids, None, raison)


def _kind(score: Decimal) -> MatchKind:
    if score >= UN:
        return MatchKind.PRESENT
    return MatchKind.PARTIAL if score > ZERO else MatchKind.ABSENT


def _borne(valeur: Decimal) -> Decimal:
    return max(ZERO, min(UN, valeur))


# --- Métier ------------------------------------------------------------------------------------

_CANON = {
    "developpeur": "developer", "developpeuse": "developer", "dev": "developer",
    "ingenieur": "engineer", "ingenieure": "engineer", "analyste": "analyst",
    "consultante": "consultant", "directrice": "director", "directeur": "director",
    "comptable": "accountant", "stagiaire": "intern", "alternant": "apprentice",
    "alternante": "apprentice", "responsable": "manager", "gestionnaire": "manager",
    "chargee": "charge", "charge": "charge", "scientifique": "scientist", "chef": "head",
}  # fmt: skip
_MOTS_VIDES = {
    "h", "f", "m", "w", "d", "x", "de", "du", "la", "le", "les", "des", "en", "et", "l", "a",
    "an", "the", "of", "for", "and", "au", "aux", "un", "une", "pour", "chez", "cdi", "cdd",
}  # fmt: skip


def _mots_du_titre(titre: str) -> set[str]:
    return {_CANON.get(m, m) for m in words(titre) if m not in _MOTS_VIDES}


def evaluate_title(profil: ProfileFacts, offre: OfferFacts, poids: Decimal) -> CriterionResult:
    titres = tuple(dict.fromkeys(t.strip() for t in profil.titles if t.strip()))
    if not titres:
        return _manquant(
            Criterion.JOB_TITLE,
            poids,
            "Aucun intitulé de poste dans votre profil ni dans vos préférences (métiers recherchés).",
        )
    cibles = _mots_du_titre(offre.title)
    if not cibles:
        return _manquant(Criterion.JOB_TITLE, poids, "L'intitulé de l'offre est inexploitable.")

    meilleur, retenu = ZERO, None
    for titre in titres:
        mots = _mots_du_titre(titre)
        if not mots:
            continue
        # Coefficient de recouvrement : « Data Analyst » est entièrement contenu dans
        # « Senior Data Analyst » sans que les mots en plus ne fassent baisser la note.
        recouvrement = D(len(cibles & mots)) / D(min(len(cibles), len(mots)))
        if recouvrement > meilleur:
            meilleur, retenu = recouvrement, titre
    if meilleur >= UN:
        score = UN
    elif meilleur >= D("0.5"):
        score = meilleur
    else:
        score = meilleur / 2  # un seul mot en commun ne fait pas un métier
    kind = _kind(score)
    detail = (
        f"Correspond à « {retenu} » dans votre profil"
        if retenu and meilleur > 0
        else "Aucun intitulé de votre profil ne ressemble à celui de l'offre"
    )
    explication = {
        MatchKind.PRESENT: f"L'intitulé « {offre.title} » correspond à un métier de votre profil.",
        MatchKind.PARTIAL: f"L'intitulé « {offre.title} » ressemble partiellement à votre profil.",
        MatchKind.ABSENT: f"L'intitulé « {offre.title} » ne ressemble à aucun métier de votre profil.",
    }[kind]
    return CriterionResult(
        Criterion.JOB_TITLE,
        Status.EVALUATED,
        poids,
        score,
        explication,
        items=(MatchItem(kind, offre.title, detail),),
    )


# --- Expérience --------------------------------------------------------------------------------


def _mois(date: YearMonth, *, plus_tot: bool) -> int:
    """Index de mois ; un mois inconnu est borné à janvier (plus tôt) ou décembre (plus tard)."""
    if date.month is not None:
        return date.year * 12 + date.month - 1
    return date.year * 12 + (0 if plus_tot else 11)


def _union(intervalles: list[tuple[int, int]]) -> int:
    total, fin_courante = 0, None
    debut_courant = 0
    for debut, fin in sorted(intervalles):
        if fin < debut:
            continue
        if fin_courante is None or debut > fin_courante + 1:
            if fin_courante is not None:
                total += fin_courante - debut_courant + 1
            debut_courant, fin_courante = debut, fin
        else:
            fin_courante = max(fin_courante, fin)
    if fin_courante is not None:
        total += fin_courante - debut_courant + 1
    return total


def experience_months(
    periodes: tuple[ExperiencePeriod, ...], maintenant: datetime
) -> tuple[int, int, int]:
    """(minimum, maximum, périodes ignorées) en mois, chevauchements comptés une seule fois.

    Une date partielle n'est jamais devinée : l'année seule donne une fourchette. Une période
    sans début, ou terminée sans date de fin, est ignorée et signalée.
    """
    actuel = maintenant.year * 12 + maintenant.month - 1
    bas: list[tuple[int, int]] = []
    haut: list[tuple[int, int]] = []
    ignorees = 0
    for p in periodes:
        if p.start is None or (p.end is None and not p.is_current):
            ignorees += 1
            continue
        if p.is_current or p.end is None:
            fin_bas = fin_haut = actuel
        else:
            fin_bas, fin_haut = _mois(p.end, plus_tot=True), _mois(p.end, plus_tot=False)
        bas.append((_mois(p.start, plus_tot=False), min(fin_bas, actuel)))
        haut.append((_mois(p.start, plus_tot=True), min(fin_haut, actuel)))
    return _union(bas), _union(haut), ignorees


def _annees(mois: int) -> str:
    return f"{mois / 12:.1f}".replace(".", ",")


def evaluate_experience(
    profil: ProfileFacts,
    exigence: YearsRequirement | None,
    maintenant: datetime,
    poids: Decimal,
) -> CriterionResult:
    if exigence is None:
        return _manquant(
            Criterion.EXPERIENCE, poids, "L'offre ne précise pas d'années d'expérience."
        )
    if exigence.years == 0:
        return CriterionResult(
            Criterion.EXPERIENCE,
            Status.EVALUATED,
            poids,
            UN,
            "L'offre accepte les débutants.",
            items=(MatchItem(MatchKind.PRESENT, "Débutant accepté"),),
        )
    if not profil.experience_periods:
        return _manquant(
            Criterion.EXPERIENCE,
            poids,
            "Votre profil ne contient aucune expérience professionnelle.",
        )
    bas, haut, ignorees = experience_months(profil.experience_periods, maintenant)
    requis = exigence.years * 12
    libelle = f"{exigence.years} an(s) d'expérience"
    fourchette = _annees(bas) if bas == haut else f"entre {_annees(bas)} et {_annees(haut)}"
    note = (
        f" {ignorees} expérience(s) sans dates exploitables ne sont pas comptées."
        if ignorees
        else ""
    )

    incertain = False
    if bas >= requis:
        score, kind = UN, MatchKind.PRESENT
        phrase = f"Votre profil totalise {fourchette} an(s) : l'exigence ({exigence.years} an(s)) est satisfaite."
    elif haut >= requis:
        # Selon le mois réel des dates, l'exigence est atteinte ou non : on ne tranche pas.
        incertain = True
        score, kind = D("0.9"), MatchKind.PARTIAL
        phrase = (
            f"Votre profil totalise {fourchette} an(s) pour {exigence.years} an(s) demandé(s) : "
            "les dates partielles ne permettent pas de trancher, précisez les mois."
        )
    else:
        score = _borne(D((bas + haut) // 2) / D(requis))
        kind = _kind(score)
        phrase = f"Votre profil totalise {fourchette} an(s) pour {exigence.years} an(s) demandé(s)."
    return CriterionResult(
        Criterion.EXPERIENCE,
        Status.EVALUATED,
        poids,
        score,
        phrase + note,
        items=(MatchItem(kind, libelle, phrase),),
        uncertain=incertain,
    )


# --- Formation ---------------------------------------------------------------------------------

_NOMS_NIVEAU = {1: "Bac+1", 2: "Bac+2", 3: "Bac+3", 4: "Bac+4", 5: "Bac+5", 8: "Doctorat"}


def _nom_niveau(niveau: int) -> str:
    return _NOMS_NIVEAU.get(niveau, f"Bac+{niveau}")


def evaluate_education(
    profil: ProfileFacts, exigence: EducationRequirement | None, poids: Decimal
) -> CriterionResult:
    if exigence is None:
        return _manquant(Criterion.EDUCATION, poids, "L'offre ne précise pas de niveau d'études.")
    niveaux = [n for d in profil.degrees if (n := niveau_d_etudes(d)) is not None]
    if not niveaux:
        raison = (
            "Votre profil ne contient aucune formation."
            if not profil.degrees
            else "Le niveau de vos diplômes n'est pas reconnaissable automatiquement."
        )
        return _manquant(Criterion.EDUCATION, poids, raison)
    atteint = max(niveaux)
    if atteint >= exigence.level:
        score, kind = UN, MatchKind.PRESENT
        phrase = f"Votre diplôme le plus élevé ({_nom_niveau(atteint)}) couvre le niveau demandé ({_nom_niveau(exigence.level)})."
    else:
        score = _borne(D(atteint) / D(exigence.level))
        kind = _kind(score)
        phrase = f"Niveau demandé : {_nom_niveau(exigence.level)} ; votre diplôme le plus élevé reconnu : {_nom_niveau(atteint)}."
    return CriterionResult(
        Criterion.EDUCATION,
        Status.EVALUATED,
        poids,
        score,
        phrase,
        items=(MatchItem(kind, _nom_niveau(exigence.level), phrase),),
    )


# --- Conditions : localisation, contrat, télétravail, salaire ------------------------------------


def evaluate_location(profil: ProfileFacts, offre: OfferFacts, poids: Decimal) -> CriterionResult:
    if not profil.cities and not profil.country_codes:
        return _manquant(
            Criterion.LOCATION, poids, "Vos préférences ne précisent ni ville ni pays souhaités."
        )
    if offre.remote_type == "remote":
        return CriterionResult(
            Criterion.LOCATION,
            Status.EVALUATED,
            poids,
            UN,
            "Poste en télétravail complet : le lieu compte peu.",
            items=(MatchItem(MatchKind.PRESENT, "Télétravail complet"),),
        )
    if offre.location is None and offre.country_code is None:
        return _manquant(Criterion.LOCATION, poids, "L'offre ne précise pas son lieu.")

    lieu = fold(offre.location or "")
    ville = next((c for c in profil.cities if fold(c) in lieu and fold(c)), None)
    pays_ok = bool(offre.country_code and offre.country_code in profil.country_codes)
    lieu_affiche = offre.location or offre.country_code or "lieu inconnu"

    if profil.cities:
        if ville:
            score, phrase = (
                UN,
                f"Le lieu ({lieu_affiche}) correspond à votre ville souhaitée : {ville}.",
            )
        elif pays_ok:
            score = D("0.4")
            phrase = f"Le lieu ({lieu_affiche}) est dans un pays souhaité mais pas dans une de vos villes."
        else:
            score, phrase = (
                ZERO,
                f"Le lieu ({lieu_affiche}) ne correspond ni à vos villes ni à vos pays souhaités.",
            )
    elif pays_ok:
        score, phrase = (
            UN,
            f"Le pays de l'offre ({offre.country_code}) fait partie de vos pays souhaités.",
        )
    elif offre.country_code is None:
        return _manquant(Criterion.LOCATION, poids, "L'offre ne précise pas son pays.")
    else:
        score, phrase = (
            ZERO,
            f"Le pays de l'offre ({offre.country_code}) n'est pas dans vos pays souhaités.",
        )
    return CriterionResult(
        Criterion.LOCATION,
        Status.EVALUATED,
        poids,
        score,
        phrase,
        items=(MatchItem(_kind(score), lieu_affiche, phrase),),
    )


_CONTRATS = {
    "permanent": "CDI", "fixed_term": "CDD", "freelance": "Freelance", "internship": "Stage",
    "apprenticeship": "Alternance", "part_time": "Temps partiel", "temporary": "Intérim",
    "other": "Autre",
}  # fmt: skip


def evaluate_contract(profil: ProfileFacts, offre: OfferFacts, poids: Decimal) -> CriterionResult:
    if not profil.employment_types:
        return _manquant(
            Criterion.CONTRACT, poids, "Vos préférences ne précisent aucun type de contrat."
        )
    if offre.employment_type is None:
        return _manquant(Criterion.CONTRACT, poids, "L'offre ne précise pas son type de contrat.")
    nom = _CONTRATS.get(offre.employment_type, offre.employment_type)
    ok = offre.employment_type in profil.employment_types
    phrase = (
        f"Le contrat proposé ({nom}) fait partie de vos préférences."
        if ok
        else f"Le contrat proposé ({nom}) n'est pas dans vos préférences."
    )
    score = UN if ok else ZERO
    return CriterionResult(
        Criterion.CONTRACT,
        Status.EVALUATED,
        poids,
        score,
        phrase,
        items=(MatchItem(_kind(score), nom, phrase),),
    )


_TELETRAVAIL = {"on_site": "Sur site", "hybrid": "Hybride", "remote": "Télétravail"}
_PROCHES = {
    ("hybrid", "remote"),
    ("remote", "hybrid"),
    ("hybrid", "on_site"),
    ("on_site", "hybrid"),
}


def evaluate_remote(profil: ProfileFacts, offre: OfferFacts, poids: Decimal) -> CriterionResult:
    if not profil.remote_types:
        return _manquant(
            Criterion.REMOTE, poids, "Vos préférences ne précisent pas de mode de travail."
        )
    if offre.remote_type is None:
        return _manquant(Criterion.REMOTE, poids, "L'offre ne précise pas le télétravail.")
    nom = _TELETRAVAIL.get(offre.remote_type, offre.remote_type)
    if offre.remote_type in profil.remote_types:
        score, phrase = UN, f"Le mode de travail ({nom}) fait partie de vos préférences."
    elif any((offre.remote_type, souhaite) in _PROCHES for souhaite in profil.remote_types):
        score, phrase = D("0.5"), f"Le mode de travail ({nom}) est proche de vos préférences."
    else:
        score, phrase = ZERO, f"Le mode de travail ({nom}) ne correspond pas à vos préférences."
    return CriterionResult(
        Criterion.REMOTE,
        Status.EVALUATED,
        poids,
        score,
        phrase,
        items=(MatchItem(_kind(score), nom, phrase),),
    )


def evaluate_salary(profil: ProfileFacts, offre: OfferFacts, poids: Decimal) -> CriterionResult:
    if profil.salary_min is None or not profil.salary_currency:
        return _manquant(
            Criterion.SALARY, poids, "Vos préférences ne précisent pas de salaire souhaité."
        )
    if offre.salary_min is None and offre.salary_max is None:
        return _manquant(Criterion.SALARY, poids, "L'offre ne précise pas de salaire.")
    if offre.salary_currency != profil.salary_currency:
        # Aucune conversion : un taux de change inventé fausserait la comparaison.
        return _manquant(
            Criterion.SALARY,
            poids,
            f"Devises différentes ({offre.salary_currency} / {profil.salary_currency}) : aucune conversion n'est appliquée.",
        )
    sommet = offre.salary_max if offre.salary_max is not None else offre.salary_min
    assert sommet is not None  # noqa: S101  (au moins une borne est connue)
    souhaite = profil.salary_min
    devise = profil.salary_currency
    borne_basse_seule = offre.salary_max is None
    if sommet >= souhaite:
        score = UN
        phrase = f"Le salaire proposé ({sommet:,.0f} {devise}) atteint votre minimum ({souhaite:,.0f} {devise})."
        incertain = False
    else:
        score = _borne(sommet / souhaite)
        incertain = borne_basse_seule
        phrase = (
            f"Le salaire proposé ({sommet:,.0f} {devise}) est sous votre minimum ({souhaite:,.0f} {devise})."
            + (" L'offre n'indique que le bas de la fourchette." if incertain else "")
        )
    phrase = phrase.replace(",", " ")
    return CriterionResult(
        Criterion.SALARY,
        Status.EVALUATED,
        poids,
        score,
        phrase,
        items=(MatchItem(_kind(score), f"{sommet:,.0f} {devise}".replace(",", " "), phrase),),
        uncertain=incertain,
    )


def evaluate_freshness(offre: OfferFacts, maintenant: datetime, poids: Decimal) -> CriterionResult:
    if offre.published_at is None:
        return _manquant(
            Criterion.FRESHNESS, poids, "La date de publication de l'offre est inconnue."
        )
    jours = max(0, (maintenant - offre.published_at).days)
    if jours <= 7:
        score = UN
    elif jours <= 30:
        score = UN - D(jours - 7) * D("0.5") / D(23)
    elif jours <= 90:
        score = D("0.5") - D(jours - 30) * D("0.4") / D(60)
    elif jours <= 180:
        score = D("0.1")
    else:
        score = ZERO
    phrase = f"Annonce publiée il y a {jours} jour(s)."
    return CriterionResult(
        Criterion.FRESHNESS,
        Status.EVALUATED,
        poids,
        score,
        phrase,
        items=(MatchItem(_kind(score), f"{jours} jour(s)", phrase),),
    )
