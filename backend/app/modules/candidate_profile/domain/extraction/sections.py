"""Découpage d'un CV en sections à partir de ses titres (français et anglais)."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum

from app.modules.candidate_profile.domain.extraction.names import ressemble_a_un_nom
from app.modules.candidate_profile.domain.text_columns import COLUMN_BREAK, SOFT_WRAP


class SectionKind(StrEnum):
    SUMMARY = "summary"
    EXPERIENCE = "experience"
    EDUCATION = "education"
    SKILLS = "skills"
    LANGUAGES = "languages"
    CERTIFICATIONS = "certifications"
    IGNORED = "ignored"
    """Section reconnue mais sans objet pour le profil (loisirs, références…) : elle sert de
    frontière pour ne pas absorber son contenu dans la section précédente."""


_TITRES: dict[SectionKind, tuple[str, ...]] = {
    SectionKind.SUMMARY: (
        "profil", "profile", "resume", "summary", "about", "about me", "a propos",
        "professional summary", "profil professionnel", "objectif", "objectif professionnel",
        "presentation",
    ),
    SectionKind.EXPERIENCE: (
        "experience", "experiences", "experience professionnelle", "experiences professionnelles",
        "parcours professionnel", "work experience", "professional experience",
        "employment history", "work history", "career", "emplois", "historique professionnel",
    ),
    SectionKind.EDUCATION: (
        "formation", "formations", "education", "etudes", "parcours academique", "diplomes",
        "academic background", "formation academique", "cursus", "scolarite",
    ),
    SectionKind.SKILLS: (
        "competences", "competences techniques", "competences cles", "skills", "technical skills",
        "key skills", "core skills", "technologies", "outils", "outils et technologies",
        "savoir-faire", "expertise", "hard skills", "soft skills", "atouts", "qualites",
        "points forts", "strengths",
    ),
    SectionKind.LANGUAGES: ("langues", "languages", "competences linguistiques", "langue"),
    SectionKind.CERTIFICATIONS: (
        "certifications", "certification", "certificats", "certificates",
        "licences et certifications",
        "licenses", "licenses and certifications", "formations complementaires",
    ),
    SectionKind.IGNORED: (
        "centres d'interet", "centres d interet", "interets", "interests", "loisirs", "hobbies",
        "projets", "projects", "references", "publications", "benevolat", "volunteering",
        "associations", "informations complementaires", "additional information", "divers",
        "vie associative", "engagements", "awards", "distinctions",
    ),
}  # fmt: skip

_INDEX: dict[str, SectionKind] = {
    titre: kind for kind, titres in _TITRES.items() for titre in titres
}
_DECORATION = re.compile(r"^[\s#*_=\-–—•:|~]+|[\s#*_=\-–—•:|~]+$")
MAX_TITLE_LENGTH = 50


def _normaliser(ligne: str) -> str:
    sans_accents = "".join(
        c for c in unicodedata.normalize("NFD", ligne) if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"\s+", " ", _DECORATION.sub("", sans_accents.lower().replace("’", "'")))


def section_kind(ligne: str) -> SectionKind | None:
    """Type de section si la ligne est un titre, sinon `None`.

    Seules les lignes courtes sont candidates : une phrase qui contient « formation » n'est
    pas un titre. « Compétences & Langues » est lu comme le premier titre reconnu.
    """
    brut = ligne.strip()
    if not brut or len(brut) > MAX_TITLE_LENGTH or brut.startswith("- "):
        return None
    texte = _normaliser(brut)
    if texte in _INDEX:
        return _INDEX[texte]
    for separateur in (" et ", " & ", " / ", " and "):
        if separateur in texte:
            premier, _, second = texte.partition(separateur)
            if premier in _INDEX and second in _INDEX:
                return _INDEX[premier]
    return None


@dataclass(frozen=True, slots=True)
class Section:
    kind: SectionKind
    title: str
    lines: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SplitDocument:
    preamble: tuple[str, ...]
    """Lignes avant le premier titre : en général l'identité et les coordonnées."""
    sections: tuple[Section, ...]
    column_heads: tuple[tuple[str, ...], ...] = ()
    """Texte sans titre en tête d'une colonne suivante, quand il commence par un nom : le nom
    et l'introduction d'un CV à colonne latérale, à ne pas confondre avec la dernière section."""

    def lines_of(self, kind: SectionKind) -> tuple[str, ...]:
        """Lignes de toutes les sections de ce type (un titre peut apparaître deux fois)."""
        return tuple(ligne for s in self.sections if s.kind is kind for ligne in s.lines)


def split_sections(texte: str) -> SplitDocument:
    preambule: list[str] = []
    sections: list[tuple[SectionKind, str, list[str]]] = []
    tetes: list[list[str]] = []
    # Texte lu après une frontière de colonne, avant le prochain titre ; `precedent` est la
    # section (ou le préambule, `None`) à laquelle il se rattache s'il n'ouvre pas la colonne.
    tete: list[str] | None = None
    precedent: int | None = None

    def clore_tete() -> None:
        nonlocal tete
        if tete is None:
            return
        premiere = next((ligne for ligne in tete if ligne.strip()), None)
        if premiere is not None and ressemble_a_un_nom(premiere):
            tetes.append(tete)
        else:  # rien n'indique une introduction : c'est la suite de la section précédente
            (preambule if precedent is None else sections[precedent][2]).extend(tete)
        tete = None

    for ligne in texte.split("\n"):
        if ligne.strip() == COLUMN_BREAK:
            clore_tete()
            tete = []
            precedent = len(sections) - 1 if sections else None
            continue
        kind = section_kind(ligne)
        if kind is not None:
            clore_tete()
            sections.append((kind, ligne.strip(), []))
        elif tete is not None:
            tete.append(ligne)
        elif sections:
            sections[-1][2].append(ligne)
        else:
            preambule.append(ligne)
    clore_tete()
    # Le marqueur de coupure n'a de sens que pour les compétences : ailleurs il serait du bruit.
    return SplitDocument(
        _sans_marqueur(preambule),
        tuple(
            Section(k, t, tuple(lignes) if k is SectionKind.SKILLS else _sans_marqueur(lignes))
            for k, t, lignes in sections
        ),
        tuple(_sans_marqueur(t) for t in tetes),
    )


def _sans_marqueur(lignes: list[str]) -> tuple[str, ...]:
    return tuple(ligne.replace(SOFT_WRAP, "") for ligne in lignes)
