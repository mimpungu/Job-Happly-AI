"""Exigences d'une offre, lues dans son texte par des règles (aucune IA).

Une offre n'est pas structurée : « 3 ans d'expérience », « Bac+5 » ou « Python, Docker » n'existent
que dans la prose. Les règles ci-dessous extraient ce qui est **explicite** et laissent le reste
inconnu. Une exigence qu'on ne sait pas lire n'est jamais comptée comme un manque.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from app.modules.job_intelligence.domain.matching.text import fold


class Importance(StrEnum):
    MANDATORY = "mandatory"
    """Explicitement obligatoire (« requis », « minimum », rubrique « Requirements »…)."""
    EXPECTED = "expected"
    """Dans la rubrique « profil recherché » sans mention d'obligation."""
    OPTIONAL = "optional"
    """Explicitement un plus (« souhaité », « nice to have »…)."""
    MENTIONED = "mentioned"
    """Simple mention hors rubrique d'exigences (missions, description) : ce n'est pas une exigence."""


@dataclass(frozen=True, slots=True)
class RequirementLine:
    text: str
    importance: Importance


@dataclass(frozen=True, slots=True)
class YearsRequirement:
    years: int
    mandatory: bool
    source: str


@dataclass(frozen=True, slots=True)
class EducationRequirement:
    level: int
    """Niveau en années d'études après le baccalauréat (Bac+2 = 2, Master = 5, Doctorat = 8)."""
    mandatory: bool
    source: str


@dataclass(frozen=True, slots=True)
class OfferRequirements:
    lines: tuple[RequirementLine, ...]
    """Lignes des rubriques d'exigences, avec leur importance."""
    body_lines: tuple[str, ...]
    """Autres lignes du texte (missions, présentation…), source de simples mentions."""
    years: YearsRequirement | None
    education: EducationRequirement | None
    has_requirement_section: bool


# --- Rubriques -----------------------------------------------------------------------------

_REQUIS = {
    "competences requises", "requirements", "required", "required skills", "must have",
    "must-have", "prerequis", "pre-requis", "indispensable", "indispensables", "exigences",
    "qualifications", "minimum qualifications", "required qualifications",
    "ce que nous attendons", "competences indispensables", "competences obligatoires",
}  # fmt: skip
_PROFIL = {
    "profil", "profil recherche", "votre profil", "le profil", "profil du candidat", "vous avez",
    "vous etes", "vous maitrisez", "competences", "competences techniques", "your profile",
    "what you bring", "who you are", "about you", "skills", "technical skills",
    "what we are looking for", "what were looking for", "experience requise", "ce que vous apportez",
    "vos competences", "profil et competences", "competences et qualites", "experience",
}  # fmt: skip
_OPTIONNEL = {
    "atouts", "un plus", "plus", "nice to have", "nice-to-have", "bonus", "appreciees",
    "apprecie", "souhaites", "souhaite", "souhaitees", "preferred", "preferred qualifications",
    "desirable", "asset", "assets", "competences appreciees", "idealement", "serait un plus",
}  # fmt: skip
_AUTRES = {
    "missions", "vos missions", "mission", "responsabilites", "responsibilities",
    "what you will do", "what you ll do", "your role", "le poste", "poste", "description du poste",
    "a propos", "about us", "about", "l entreprise", "notre entreprise", "company", "avantages",
    "benefits", "what we offer", "nous offrons", "notre offre", "ce que nous offrons", "pourquoi nous rejoindre",
    "processus de recrutement", "recruitment process", "contexte", "context", "environnement",
    "remuneration", "salaire", "salary", "lieu", "location", "contrat", "type de contrat",
    "description", "notre equipe", "l equipe", "equipe", "culture", "diversite", "equal opportunity",
}  # fmt: skip

_MAX_TITRE = 60
_PUCE = re.compile(r"^\s*[•▪●◦*\-–—]\s+")
_DECORATION = re.compile(r"^[\s#*_=\-–—•:|~]+|[\s#*_=\-–—•:|~]+$")

_MARQUEURS_OBLIGATOIRE = (
    "obligatoire", "requis", "requise", "requises", "indispensable", "imperatif", "must have",
    "must-have", "required", "mandatory", "essential", "exige", "exigee", "exiges", "minimum",
    "au moins", "at least",
)  # fmt: skip
_MARQUEURS_OPTIONNEL = (
    "souhaite", "souhaitee", "souhaites", "souhaitees", "idealement", "ideally", "un plus",
    "a plus", "appreciee", "apprecie", "appreciees", "appreciable", "atout", "nice to have",
    "nice-to-have", "bonus", "preferred", "desirable", "de preference", "serait un plus",
    "is a plus", "would be a plus",
)  # fmt: skip


def _titre_normalise(ligne: str) -> str:
    texte = fold(ligne).replace("’", " ").replace("'", " ")
    texte = _DECORATION.sub("", texte)
    return re.sub(r"\s+", " ", texte)


def _type_de_rubrique(ligne: str) -> Importance | str | None:
    """`Importance` pour une rubrique d'exigences, `"autre"` pour une rubrique sans exigences,
    `None` si la ligne n'est pas un titre."""
    brut = ligne.strip()
    if not brut or len(brut) > _MAX_TITRE or _PUCE.match(brut) or brut.endswith((".", ";", ",")):
        return None
    titre = _titre_normalise(brut)
    if titre in _REQUIS:
        return Importance.MANDATORY
    if titre in _OPTIONNEL:
        return Importance.OPTIONAL
    if titre in _PROFIL:
        return Importance.EXPECTED
    if titre in _AUTRES:
        return "autre"
    return None


def _importance_de_ligne(texte: str, defaut: Importance) -> Importance:
    """Les marqueurs explicites de la ligne l'emportent sur la rubrique qui la contient."""
    plie = fold(texte)
    if any(m in plie for m in _MARQUEURS_OPTIONNEL):
        return Importance.OPTIONAL
    if any(m in plie for m in _MARQUEURS_OBLIGATOIRE):
        return Importance.MANDATORY
    return defaut


# --- Années d'expérience et formation -----------------------------------------------------------

_ANNEES = re.compile(
    r"(?P<a>\d{1,2})\s*(?:\+|\s*(?:a|à|-|–|to)\s*(?P<b>\d{1,2}))?\s*"
    r"(?:ans?|ann[ée]es?|years?|yrs?)\s*(?:\+\s*)?(?:d['’]\s*|de\s+|of\s+|en\s+|in\s+)?"
    r"(?:exp[ée]rience|experience)",
    re.IGNORECASE,
)
_EXPERIENCE_DE = re.compile(
    r"exp[ée]rience\s*(?:de|d['’]|of|:)?\s*(?:minimum\s*|min\.?\s*|au moins\s*|at least\s*)?"
    r"(?P<a>\d{1,2})\s*(?:\+|\s*(?:a|à|-|–|to)\s*(?P<b>\d{1,2}))?\s*(?:ans?|ann[ée]es?|years?|yrs?)",
    re.IGNORECASE,
)
_SANS_EXPERIENCE = re.compile(
    r"d[ée]butant(?:e)?s?\s+accept[ée]|sans\s+exp[ée]rience|no\s+experience\s+(?:required|needed)|"
    r"entry[- ]level|premi[èe]re\s+exp[ée]rience\s+accept",
    re.IGNORECASE,
)
MAX_ANNEES = 40

_NIVEAUX: tuple[tuple[re.Pattern[str], int], ...] = (
    (re.compile(r"doctorat|\bph\.?d\b|\bthèse\b|bac\s*\+\s*8", re.IGNORECASE), 8),
    (re.compile(r"bac\s*\+\s*5|\bmaster\b|\bm2\b|\bmsc\b|\bmba\b|ing[ée]nieur|engineer(?:ing)? degree|"
                r"master'?s degree|ma[iî]trise\b|mast[èe]re", re.IGNORECASE), 5),
    (re.compile(r"bac\s*\+\s*4|\bm1\b", re.IGNORECASE), 4),
    (re.compile(r"bac\s*\+\s*3|licence|bachelor|\bbsc\b|\bbut\b|undergraduate degree|bachelor'?s degree",
                re.IGNORECASE), 3),
    (re.compile(r"bac\s*\+\s*2|\bbts\b|\bdut\b|\bdeug\b|associate degree", re.IGNORECASE), 2),
    (re.compile(r"bac\s*\+\s*1", re.IGNORECASE), 1),
)  # fmt: skip


def extraire_annees(texte: str) -> YearsRequirement | None:
    """Années d'expérience exigées : le plus petit minimum explicite du texte."""
    candidats: list[YearsRequirement] = []
    for ligne in texte.split("\n"):
        if _SANS_EXPERIENCE.search(ligne):
            candidats.append(YearsRequirement(0, False, ligne.strip()[:200]))
            continue
        for motif in (_ANNEES, _EXPERIENCE_DE):
            m = motif.search(ligne)
            if m:
                annees = int(m.group("a"))
                if 0 <= annees <= MAX_ANNEES:
                    obligatoire = (
                        _importance_de_ligne(ligne, Importance.EXPECTED) is Importance.MANDATORY
                    )
                    candidats.append(YearsRequirement(annees, obligatoire, ligne.strip()[:200]))
                break
    return min(candidats, key=lambda c: c.years) if candidats else None


def niveau_d_etudes(texte: str) -> int | None:
    """Niveau (années après le bac) le plus élevé cité dans `texte`, ou `None`."""
    niveaux = [niveau for motif, niveau in _NIVEAUX if motif.search(texte)]
    return max(niveaux) if niveaux else None


def extraire_formation(texte: str) -> EducationRequirement | None:
    """Niveau d'études exigé : le plus bas niveau cité (« Bac+3 à Bac+5 » exige Bac+3)."""
    candidats: list[EducationRequirement] = []
    for ligne in texte.split("\n"):
        niveaux = [niveau for motif, niveau in _NIVEAUX if motif.search(ligne)]
        if niveaux:
            obligatoire = _importance_de_ligne(ligne, Importance.EXPECTED) is Importance.MANDATORY
            candidats.append(EducationRequirement(min(niveaux), obligatoire, ligne.strip()[:200]))
    return min(candidats, key=lambda c: c.level) if candidats else None


# --- Extraction globale ---------------------------------------------------------------------------


def extract_requirements(description: str) -> OfferRequirements:
    texte = description.replace("\r\n", "\n").replace("\r", "\n")
    lignes: list[RequirementLine] = []
    autres: list[str] = []
    rubrique: Importance | str | None = None
    trouvee = False

    for ligne in texte.split("\n"):
        brut = ligne.strip()
        if not brut:
            continue
        titre = _type_de_rubrique(brut)
        if titre is not None:
            rubrique = titre
            trouvee = trouvee or isinstance(titre, Importance)
            continue
        contenu = _PUCE.sub("", brut).strip()
        if isinstance(rubrique, Importance):
            lignes.append(RequirementLine(contenu, _importance_de_ligne(contenu, rubrique)))
        else:
            autres.append(contenu)

    return OfferRequirements(
        lines=tuple(lignes),
        body_lines=tuple(autres),
        years=extraire_annees(texte),
        education=extraire_formation(texte),
        has_requirement_section=trouvee,
    )
