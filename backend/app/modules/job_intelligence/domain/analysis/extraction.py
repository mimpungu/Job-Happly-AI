"""Extraction par règles des éléments d'une offre (aucune IA, rien d'inventé).

Principe commun : n'est restitué que ce qui est **écrit** dans l'annonce. Ce qui n'est pas lisible
reste inconnu (liste vide, `None`) et, si utile au candidat, est signalé comme information
manquante plutôt que deviné.
"""

from __future__ import annotations

import re

from app.modules.job_intelligence.domain.analysis.models import (
    ANALYSIS_VERSION,
    LanguageRequirement,
    MissingInfo,
    Mobility,
    OfferAnalysis,
    VisaPolicy,
)
from app.modules.job_intelligence.domain.analysis.technologies import (
    find_technologies,
    looks_like_skill,
)
from app.modules.job_intelligence.domain.matching.models import OfferFacts
from app.modules.job_intelligence.domain.matching.offer_requirements import (
    _MAX_TITRE,
    _PUCE,
    Importance,
    _titre_normalise,
    _type_de_rubrique,
    extract_requirements,
)
from app.modules.job_intelligence.domain.matching.skills import _termes_de_l_offre
from app.modules.job_intelligence.domain.matching.text import fold

# --- Missions ----------------------------------------------------------------------------------

_RUBRIQUES_MISSIONS = {
    "missions", "vos missions", "mission", "mission principale", "vos responsabilites",
    "responsabilites", "responsibilities", "key responsibilities", "main responsibilities",
    "what you will do", "what you ll do", "what you ll be doing", "your role", "the role",
    "about the role", "role", "le poste", "description du poste", "ce que vous ferez",
    "vos activites", "activites", "day to day", "in this role", "your mission",
}  # fmt: skip
_MAX_MISSIONS = 12
_MAX_LIGNE = 240


def extract_missions(description: str) -> tuple[str, ...]:
    """Lignes de la rubrique « missions » (jusqu'à la rubrique suivante). Vide si absente."""
    missions: list[str] = []
    dedans = False
    for ligne in description.replace("\r\n", "\n").split("\n"):
        brut = ligne.strip()
        if not brut:
            continue
        if _estun_titre(brut):
            dedans = _titre_normalise(brut) in _RUBRIQUES_MISSIONS
            continue
        if dedans:
            contenu = _PUCE.sub("", brut).strip()
            if 3 <= len(contenu) <= _MAX_LIGNE:
                missions.append(contenu)
    return tuple(missions[:_MAX_MISSIONS])


def _estun_titre(brut: str) -> bool:
    if _type_de_rubrique(brut) is not None:
        return True
    return (
        len(brut) <= _MAX_TITRE
        and not _PUCE.match(brut)
        and not brut.endswith((".", ";", ",", "!", "?"))
        and _titre_normalise(brut) in _RUBRIQUES_MISSIONS
    )


# --- Langues -----------------------------------------------------------------------------------

_LANGUES = {
    "fr": ("francais", "french", "francophone"),
    "en": ("anglais", "english", "anglophone"),
    "de": ("allemand", "german", "deutsch"),
    "es": ("espagnol", "spanish", "espanol"),
    "it": ("italien", "italian", "italiano"),
    "pt": ("portugais", "portuguese", "portugues"),
    "nl": ("neerlandais", "dutch", "nederlands", "flamand"),
}  # fmt: skip
_NIVEAUX = (
    "bilingue", "bilingual", "natif", "native", "courant", "fluent", "fluency", "professionnel",
    "professional", "intermediaire", "intermediate", "notions", "basic", "avance", "advanced",
    "operationnel", "working proficiency", "full professional", "langue maternelle",
    "mother tongue", "toeic", "toefl", "ielts", "delf", "dalf",
)  # fmt: skip
_NIVEAU_CECRL = re.compile(r"\b([abc][12])\b", re.IGNORECASE)
_INDICES = (
    "parle", "parler", "maitrise", "ecrit", "oral", "speak", "written", "spoken", "proficien",
    "communicat", "langue", "language", "level", "niveau",
)  # fmt: skip
_OBLIGATOIRE = (
    "requis", "obligatoire", "indispensable", "required", "mandatory", "must", "essential",
    "exige", "imperatif",
)  # fmt: skip
_OPTIONNEL = (
    "souhaite", "un plus", "atout", "apprecie", "nice to have", "preferred", "bonus", "ideal",
)  # fmt: skip


def _contient_mot(plie: str, mot: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(mot)}(?![a-z0-9])", plie) is not None


def extract_languages(description: str) -> tuple[LanguageRequirement, ...]:
    """Exigences de langue. Une langue citée sans indice de niveau ni de maîtrise est ignorée
    (« Paris, France », « équipe anglophone » ne sont pas des exigences)."""
    trouvees: dict[str, LanguageRequirement] = {}
    for ligne in description.replace("\r\n", "\n").split("\n"):
        brut = _PUCE.sub("", ligne.strip())
        if not brut or len(brut) > 400:
            continue
        plie = fold(brut)
        for code, noms in _LANGUES.items():
            nom = next((n for n in noms if _contient_mot(plie, n)), None)
            if nom is None:
                continue
            niveau = next((n for n in _NIVEAUX if _contient_mot(plie, n)), None)
            cecrl = _NIVEAU_CECRL.search(brut)
            if niveau is None and cecrl is None and not any(i in plie for i in _INDICES):
                continue
            libelle = cecrl.group(1).upper() if cecrl else niveau
            facultatif = any(m in plie for m in _OPTIONNEL)
            obligatoire = not facultatif and (
                any(m in plie for m in _OBLIGATOIRE) or niveau is not None or cecrl is not None
            )
            existant = trouvees.get(code)
            if existant is None or (obligatoire and not existant.mandatory):
                trouvees[code] = LanguageRequirement(code, libelle, obligatoire, brut[:200])
    return tuple(trouvees.values())


# --- Mobilité, visa, déplacements -------------------------------------------------------------

_SANS_SPONSORING = re.compile(
    r"(no visa sponsorship|not (able|in a position) to sponsor|unable to (offer )?(visa )?sponsor"
    r"|cannot (offer )?(visa )?sponsor|do(es)? not (offer|provide) (visa )?sponsorship"
    r"|sans (prise en charge|sponsoring) (du )?visa|pas de sponsoring|visa sponsorship (is )?not"
    r"|not (offer|provide)\w* (visa|work permit)|will not sponsor)"
)
_SPONSORING = re.compile(
    r"(visa sponsorship (is )?(available|provided|offered|possible)|we (can |will |do )?sponsor"
    r"|sponsor(s|ing)? (your )?(a )?(work )?visa|visa support|work permit (support|assistance)"
    r"|prise en charge (du|des frais de) (visa|permis)|sponsoring (de )?visa"
    r"|aide (a|pour) l'obtention (du|d'un) (visa|permis))"
)
_AUTORISATION = re.compile(
    r"(authori[sz]ed to work|right to work|legally (able|entitled|authori[sz]ed) to work"
    r"|work authori[sz]ation|autorisation de travail(er)?|permis de travail"
    r"|autorise a travailler|eligible to work)"
)
_RELOCATION = re.compile(
    r"(relocation (package|assistance|support|bonus|allowance)|help with relocation"
    r"|assistance (a|au) (la )?(relocalisation|demenagement)|aide (a|au) (la )?(relocalisation|"
    r"demenagement|mobilite)|prime de (relocalisation|demenagement)|we (can )?(help|support) you "
    r"(to )?relocate|relocation (is )?(offered|provided|available))"
)
_DEPLACEMENTS = re.compile(
    r"((travel|deplacements?|voyages?)[^.\n]{0,40}?(\d{1,3} ?%|occasionnels?|ponctuels?|"
    r"frequents?|reguliers?|occasional|frequent|regular|rare|limited|minimal|international)"
    r"|(\d{1,3} ?%|occasional|frequent|regular)[^.\n]{0,25}?(travel|deplacements?))"
)


def extract_mobility(description: str) -> Mobility:
    visa: VisaPolicy | None = None
    relocation = False
    voyage: str | None = None
    preuves: list[str] = []
    for ligne in description.replace("\r\n", "\n").split("\n"):
        brut = _PUCE.sub("", ligne.strip())
        if not brut:
            continue
        plie = fold(brut).replace("\u2019", "'")
        ajoute = False
        # Un refus explicite l'emporte : « no visa sponsorship » contient aussi « sponsorship ».
        if _SANS_SPONSORING.search(plie):
            visa, ajoute = VisaPolicy.NO_SPONSORSHIP, True
        elif _SPONSORING.search(plie) and visa is not VisaPolicy.NO_SPONSORSHIP:
            visa, ajoute = VisaPolicy.SPONSORSHIP_OFFERED, True
        elif _AUTORISATION.search(plie) and visa is None:
            visa, ajoute = VisaPolicy.WORK_AUTHORIZATION_REQUIRED, True
        if _RELOCATION.search(plie):
            relocation, ajoute = True, True
        trouve = _DEPLACEMENTS.search(plie)
        if trouve and voyage is None:
            voyage, ajoute = brut[:160], True
        if ajoute:
            preuves.append(brut[:200])
    return Mobility(visa, relocation, voyage, tuple(dict.fromkeys(preuves))[:6])


# --- Résumé extractif --------------------------------------------------------------------------

_PHRASES = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-ÖØ-Ý0-9])")
_MAX_RESUME = 380


def extractive_summary(description: str) -> str | None:
    """Premières phrases informatives de l'annonce, telles quelles (jamais reformulées)."""
    candidates: list[str] = []
    for ligne in description.replace("\r\n", "\n").split("\n"):
        brut = ligne.strip()
        if len(brut) < 60 or _type_de_rubrique(brut) is not None:
            continue
        candidates.extend(p.strip() for p in _PHRASES.split(_PUCE.sub("", brut)) if len(p) >= 40)
        if sum(len(c) for c in candidates) >= _MAX_RESUME:
            break
    if not candidates:
        return None
    resume = ""
    for phrase in candidates:
        if resume and len(resume) + len(phrase) + 1 > _MAX_RESUME:
            break
        resume = f"{resume} {phrase}".strip()
    return resume[: _MAX_RESUME + 80] or None


# --- Assemblage --------------------------------------------------------------------------------


def analyze_offer(offre: OfferFacts) -> OfferAnalysis:
    exigences = extract_requirements(offre.description)
    termes, _ = _termes_de_l_offre(exigences, {}, ())
    par_importance: dict[Importance, list[str]] = {i: [] for i in Importance}
    for libelle, importance in termes.values():
        if looks_like_skill(libelle):
            par_importance[importance].append(libelle)
    # Technologies : tout ce qui est cité dans l'annonce (missions comprises) parmi un vocabulaire
    # connu. Une mention hors rubrique d'exigences n'est pas pour autant une exigence.
    technologies = find_technologies(offre.description)
    missions = extract_missions(offre.description)
    langues = extract_languages(offre.description)

    manquant: list[MissingInfo] = []
    if offre.salary_min is None and offre.salary_max is None:
        manquant.append(MissingInfo.SALARY)
    if not (offre.location or offre.country_code):
        manquant.append(MissingInfo.LOCATION)
    if offre.employment_type is None:
        manquant.append(MissingInfo.EMPLOYMENT_TYPE)
    if offre.remote_type is None:
        manquant.append(MissingInfo.REMOTE)
    if exigences.years is None:
        manquant.append(MissingInfo.EXPERIENCE)
    if not exigences.has_requirement_section:
        manquant.append(MissingInfo.REQUIREMENTS)
    if not missions:
        manquant.append(MissingInfo.MISSIONS)
    if not langues:
        manquant.append(MissingInfo.LANGUAGES)

    return OfferAnalysis(
        version=ANALYSIS_VERSION,
        missions=missions,
        mandatory_skills=tuple(sorted(par_importance[Importance.MANDATORY], key=str.casefold)),
        expected_skills=tuple(sorted(par_importance[Importance.EXPECTED], key=str.casefold)),
        desired_skills=tuple(sorted(par_importance[Importance.OPTIONAL], key=str.casefold)),
        technologies=tuple(technologies[:60]),
        years_experience=exigences.years.years if exigences.years else None,
        years_mandatory=exigences.years.mandatory if exigences.years else None,
        languages=langues,
        mobility=extract_mobility(offre.description),
        missing=tuple(manquant),
        summary=extractive_summary(offre.description),
    )
