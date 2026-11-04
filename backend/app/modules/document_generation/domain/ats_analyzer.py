"""Analyseur de compatibilité ATS d'un PDF compilé (FEATURE 012.4).

Chaque contrôle s'appuie sur ce qu'un parseur d'ATS voit réellement : le texte extrait dans
l'ordre du flux du PDF et la position de chaque fragment.

- TASK-012-17 : extraction du texte sélectionnable (pypdf).
- TASK-012-18 : ordre de lecture, d'après l'ordre réel des rubriques dans le flux.
- TASK-012-19 : accents et caractères internationaux (corruption et phrases attendues).
- TASK-012-20 : rubriques standards, reconnues sur des lignes de titre uniquement.
- TASK-012-21 : mise en page (colonnes, marges, pagination, polices, images).

Les seuils géométriques sont des heuristiques documentées : un faux négatif reste possible sur
une mise en page exotique, mais jamais un « conforme » par défaut.
"""

from __future__ import annotations

import io
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from pypdf import PdfReader

from app.modules.document_generation.domain.enums import ATSCheckStatus, LengthTarget
from app.modules.document_generation.domain.models import ATSCheckResult, ATSReport

# Clé de rubrique → intitulés reconnus (comparaison exacte sur une ligne entière).
_SECTION_ALIASES: dict[str, frozenset[str]] = {
    "summary": frozenset(
        {
            "profil",
            "profil professionnel",
            "résumé",
            "à propos",
            "accroche",
            "summary",
            "professional summary",
            "profile",
        }
    ),
    "experience": frozenset(
        {
            "expérience",
            "expériences",
            "expérience professionnelle",
            "expériences professionnelles",
            "parcours professionnel",
            "experience",
            "work experience",
            "professional experience",
            "employment history",
        }
    ),
    "skills": frozenset(
        {
            "compétences",
            "compétences techniques",
            "skills",
            "technical skills",
            "technologies",
        }
    ),
    "education": frozenset(
        {"formation", "formations", "éducation", "diplômes", "education", "education & training"}
    ),
    "certifications": frozenset({"certifications", "certification", "certificats"}),
    "languages": frozenset({"langues", "languages"}),
}
_SECTION_ORDER = tuple(_SECTION_ALIASES)
DEFAULT_EXPECTED_SECTIONS = ("experience", "skills", "education")

_MIN_TEXT_CHARS = 80
_MIN_FONT_SIZE = 8.0
_MARGIN_TOLERANCE = 10.0
_BACKWARD_JUMP = 15.0  # remontée d'au moins une ligne…
_RIGHTWARD_JUMP = 80.0  # …avec un saut à droite : début d'une 2e colonne
_SIDE_BY_SIDE_GAP = 150.0
_SIDE_BY_SIDE_MIN_CHARS = 30
_MOJIBAKE = re.compile(r"Ã[\u0080-\u00bf]|Â[\u00a0-\u00bf]|â€")
_TEX_ACCENT = re.compile(r"\\[\'^\"`~][a-zA-Z]")
_PASS_SCORE = 75

_PENALTY_COLUMNS = 25
_PENALTY_SECTION = 15
_PENALTY_ORDER = 15
_PENALTY_ACCENTS = 20
_PENALTY_LAYOUT = 10
_PENALTY_KEYWORDS = 10
_KEYWORD_THRESHOLD = 0.5


@dataclass(frozen=True)
class _Fragment:
    page: int
    x: float
    y: float
    size: float
    text: str


@dataclass(frozen=True)
class _Extraction:
    text: str
    fragments: tuple[_Fragment, ...]
    page_sizes: tuple[tuple[float, float], ...]
    page_texts: tuple[str, ...]
    image_pages: tuple[int, ...]


def analyze_pdf_ats(
    pdf_bytes: bytes,
    *,
    expected_keywords: tuple[str, ...] = (),
    expected_phrases: tuple[str, ...] = (),
    expected_sections: tuple[str, ...] = DEFAULT_EXPECTED_SECTIONS,
    length_target: LengthTarget | None = None,
) -> ATSReport:
    """Audite un PDF comme le ferait un parseur ATS.

    `expected_keywords` : termes de l'offre à retrouver. `expected_phrases` : textes du profil
    (nom, entreprises…) qui doivent ressortir intacts, accents compris. `expected_sections` :
    rubriques que le contenu du CV impose (clés de `_SECTION_ALIASES`).
    """
    extraction, erreur = _extraire(pdf_bytes)
    if extraction is None or not extraction.text.strip():
        return _rapport_illisible(erreur, expected_keywords)

    texte = extraction.text
    nb_pages = len(extraction.page_sizes)
    checks: list[ATSCheckResult] = [
        ATSCheckResult(
            "Texte sélectionnable",
            ATSCheckStatus.PASS,
            "Le texte est sélectionnable et extractible par les parseurs.",
            f"{len(texte)} caractères extraits sur {nb_pages} page(s).",
        )
    ]
    score = 100

    # Mono-colonne (TASK-012-03 / 012-21)
    raison_colonnes = _detecter_colonnes(extraction.fragments)
    single_column = raison_colonnes is None
    if single_column:
        checks.append(
            ATSCheckResult(
                "Structure mono-colonne",
                ATSCheckStatus.PASS,
                "Flux de lecture linéaire, de haut en bas, sans colonne parallèle.",
            )
        )
    else:
        score -= _PENALTY_COLUMNS
        checks.append(
            ATSCheckResult(
                "Structure mono-colonne",
                ATSCheckStatus.FAIL,
                "Plusieurs colonnes détectées : un ATS risque de mélanger les rubriques.",
                raison_colonnes,
            )
        )

    # Rubriques (TASK-012-20)
    sequence = _detecter_rubriques(texte)
    trouvees = [cle for cle, _ in sequence]
    manquantes = [s for s in expected_sections if s not in trouvees]
    if not manquantes:
        checks.append(
            ATSCheckResult(
                "Rubriques standards",
                ATSCheckStatus.PASS,
                "Toutes les rubriques attendues sont identifiées.",
                ", ".join(trouvees),
            )
        )
    else:
        score -= _PENALTY_SECTION * len(manquantes)
        checks.append(
            ATSCheckResult(
                "Rubriques standards",
                ATSCheckStatus.WARNING,
                f"Rubriques attendues non identifiées : {', '.join(manquantes)}.",
                f"Trouvées : {', '.join(trouvees) or 'aucune'}",
            )
        )

    # Ordre de lecture (TASK-012-18)
    ordre_valide = _ordre_valide(trouvees)
    if ordre_valide:
        checks.append(
            ATSCheckResult(
                "Ordre de lecture séquentiel",
                ATSCheckStatus.PASS,
                "Les rubriques s'enchaînent dans l'ordre standard.",
                " → ".join(trouvees),
            )
        )
    else:
        score -= _PENALTY_ORDER
        checks.append(
            ATSCheckResult(
                "Ordre de lecture séquentiel",
                ATSCheckStatus.WARNING,
                "Les rubriques ne suivent pas l'ordre standard.",
                " → ".join(trouvees),
            )
        )

    # Accents et caractères internationaux (TASK-012-19)
    accents_ok, detail_accents = _verifier_accents(texte, expected_phrases)
    if accents_ok:
        checks.append(
            ATSCheckResult(
                "Intégrité typographique et accents",
                ATSCheckStatus.PASS,
                "Caractères accentués restitués sans corruption.",
            )
        )
    else:
        score -= _PENALTY_ACCENTS
        checks.append(
            ATSCheckResult(
                "Intégrité typographique et accents",
                ATSCheckStatus.FAIL,
                "Altération ou perte de caractères détectée dans le texte extrait.",
                detail_accents,
            )
        )

    # Mise en page (TASK-012-21)
    for verification in _verifier_mise_en_page(extraction, length_target):
        checks.append(verification)
        score -= _PENALTY_LAYOUT * (2 if verification.status is ATSCheckStatus.FAIL else 1)
    if not any(c.name.startswith("Mise en page") for c in checks):
        checks.append(
            ATSCheckResult(
                "Mise en page",
                ATSCheckStatus.PASS,
                "Marges, pagination et tailles de police conformes.",
            )
        )

    # Mots-clés de l'offre
    trouves, absents = _verifier_mots_cles(texte, expected_keywords)
    if expected_keywords:
        ratio = len(trouves) / len(expected_keywords)
        statut = ATSCheckStatus.PASS if ratio >= _KEYWORD_THRESHOLD else ATSCheckStatus.WARNING
        if statut is ATSCheckStatus.WARNING:
            score -= _PENALTY_KEYWORDS
        checks.append(
            ATSCheckResult(
                "Mots-clés de l'offre",
                statut,
                f"{len(trouves)}/{len(expected_keywords)} termes de l'offre présents.",
                f"Absents du CV : {', '.join(absents[:8])}" if absents else None,
            )
        )

    score_final = max(0, min(100, score))
    aucun_echec = all(c.status is not ATSCheckStatus.FAIL for c in checks)
    return ATSReport(
        score=score_final,
        passed=score_final >= _PASS_SCORE and aucun_echec,
        checks=tuple(checks),
        word_count=len(re.findall(r"\w+", texte)),
        character_count=len(texte),
        page_count=nb_pages,
        keywords_found=tuple(trouves),
        keywords_missing=tuple(absents),
        reading_order_valid=ordre_valide,
        accents_preserved=accents_ok,
        single_column=single_column,
    )


def read_pdf_text(pdf_bytes: bytes) -> tuple[str, int] | None:
    """Texte extrait et nombre de pages d'un PDF, ou None s'il est illisible."""
    extraction, _ = _extraire(pdf_bytes)
    if extraction is None:
        return None
    return extraction.text, len(extraction.page_sizes)


def _rapport_illisible(erreur: str, expected_keywords: tuple[str, ...]) -> ATSReport:
    return ATSReport(
        score=0,
        passed=False,
        checks=(
            ATSCheckResult(
                "Texte sélectionnable",
                ATSCheckStatus.FAIL,
                "Le PDF ne contient aucun texte sélectionnable ou extractible.",
                erreur,
            ),
        ),
        word_count=0,
        character_count=0,
        page_count=0,
        keywords_found=(),
        keywords_missing=expected_keywords,
        reading_order_valid=False,
        accents_preserved=False,
        single_column=False,
    )


def _extraire(pdf_bytes: bytes) -> tuple[_Extraction | None, str]:
    """Texte complet, fragments positionnés, tailles de page et images (pypdf)."""
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes), strict=False)
        if reader.is_encrypted:
            return None, "PDF chiffré ou protégé."
        if not reader.pages:
            return None, "Aucune page dans le document."

        fragments: list[_Fragment] = []
        textes: list[str] = []
        tailles: list[tuple[float, float]] = []
        pages_images: list[int] = []
        for numero, page in enumerate(reader.pages):
            tailles.append((float(page.mediabox.width), float(page.mediabox.height)))
            textes.append(page.extract_text(visitor_text=_collecteur(numero, fragments)) or "")
            if len(page.images) > 0:
                pages_images.append(numero)
    except Exception as err:
        return None, f"{type(err).__name__}: {err}"
    return _Extraction(
        "\n".join(textes), tuple(fragments), tuple(tailles), tuple(textes), tuple(pages_images)
    ), "OK"


def _collecteur(page: int, sortie: list[_Fragment]) -> Any:
    def visiter(text: str, cm: list[float], tm: list[float], _font: Any, size: float) -> None:
        if not text.strip():
            return
        x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
        y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
        taille = size * abs(tm[3] if tm[3] else 1.0) * abs(cm[3] if cm[3] else 1.0)
        sortie.append(_Fragment(page, x, y, taille, text.strip()))

    return visiter


def _detecter_colonnes(fragments: tuple[_Fragment, ...]) -> str | None:
    """Raison d'un soupçon de multi-colonnes, ou None.

    Deux signaux : le flux remonte d'au moins une ligne en sautant à droite (fin de la 1re
    colonne, début de la 2e) ; ou deux longs fragments partagent la même ligne, très espacés
    (tableau ou minipages côte à côte). Une date alignée à droite (`\\hfill`) est courte.
    """
    precedent: _Fragment | None = None
    lignes: dict[tuple[int, int], list[_Fragment]] = {}
    for fragment in fragments:
        if (
            precedent is not None
            and precedent.page == fragment.page
            and fragment.y - precedent.y >= _BACKWARD_JUMP
            and fragment.x - precedent.x >= _RIGHTWARD_JUMP
        ):
            return f"Le flux de lecture remonte en page {fragment.page + 1} (2e colonne probable)."
        precedent = fragment
        if len(fragment.text) >= _SIDE_BY_SIDE_MIN_CHARS:
            lignes.setdefault((fragment.page, round(fragment.y)), []).append(fragment)

    for (page, _), groupe in lignes.items():
        abscisses = sorted(f.x for f in groupe)
        if len(abscisses) >= 2 and abscisses[-1] - abscisses[0] >= _SIDE_BY_SIDE_GAP:
            return f"Deux blocs de texte côte à côte sur une même ligne en page {page + 1}."
    return None


def _normaliser_ligne(ligne: str) -> str:
    return re.sub(r"\s+", " ", ligne).strip().rstrip(":").casefold()


def _detecter_rubriques(texte: str) -> list[tuple[str, int]]:
    """Rubriques reconnues, dans l'ordre d'apparition (une ligne entière = un intitulé)."""
    vues: set[str] = set()
    sequence: list[tuple[str, int]] = []
    for numero, ligne in enumerate(texte.splitlines()):
        normalisee = _normaliser_ligne(ligne)
        for cle, alias in _SECTION_ALIASES.items():
            if normalisee in alias and cle not in vues:
                vues.add(cle)
                sequence.append((cle, numero))
    return sequence


def _ordre_valide(trouvees: list[str]) -> bool:
    rangs = [_SECTION_ORDER.index(cle) for cle in trouvees]
    return rangs == sorted(rangs)


def _normaliser_comparaison(texte: str) -> str:
    propre = unicodedata.normalize("NFC", texte)
    for source, cible in (
        ("\u2019", "'"),
        ("\u2018", "'"),
        ("\u2013", "-"),
        ("\u2014", "-"),
        ("\u00ad", ""),
    ):
        propre = propre.replace(source, cible)
    return re.sub(r"\s+", " ", propre).strip().casefold()


def _verifier_accents(texte: str, phrases: tuple[str, ...]) -> tuple[bool, str | None]:
    problemes: list[str] = []
    if "\ufffd" in texte:
        problemes.append("caractère de remplacement Unicode (U+FFFD)")
    if "(cid:" in texte:
        problemes.append("glyphes sans correspondance Unicode ((cid:…))")
    if _MOJIBAKE.search(texte):
        problemes.append("séquences de double encodage (Ã©, â€…)")
    if _TEX_ACCENT.search(texte):
        problemes.append("commandes d'accents TeX non composées")

    cible = _normaliser_comparaison(texte)
    manquantes = [p for p in phrases if p.strip() and _normaliser_comparaison(p) not in cible]
    if manquantes:
        problemes.append("textes du profil absents ou altérés : " + " | ".join(manquantes[:5]))
    return (not problemes), ("; ".join(problemes) or None)


def _verifier_mise_en_page(
    extraction: _Extraction, length_target: LengthTarget | None
) -> list[ATSCheckResult]:
    resultats: list[ATSCheckResult] = []
    nb_pages = len(extraction.page_sizes)

    if length_target is LengthTarget.ONE_PAGE and nb_pages > 1:
        resultats.append(
            ATSCheckResult(
                "Mise en page : longueur",
                ATSCheckStatus.WARNING,
                f"Une page demandée, {nb_pages} obtenues : réduisez le contenu.",
            )
        )
    elif nb_pages > 2:
        resultats.append(
            ATSCheckResult(
                "Mise en page : longueur",
                ATSCheckStatus.WARNING,
                f"{nb_pages} pages : au-delà de 2 pages, un CV est rarement lu en entier.",
            )
        )

    pages_vides = [i + 1 for i, t in enumerate(extraction.page_texts) if len(t.strip()) < 5]
    if pages_vides:
        resultats.append(
            ATSCheckResult(
                "Mise en page : pages vides",
                ATSCheckStatus.FAIL,
                f"Page(s) sans texte : {', '.join(map(str, pages_vides))}.",
            )
        )
    elif nb_pages > 1 and len(extraction.page_texts[-1].strip()) < _MIN_TEXT_CHARS:
        resultats.append(
            ATSCheckResult(
                "Mise en page : dernière page",
                ATSCheckStatus.WARNING,
                "Quelques lignes seulement sur la dernière page : resserrez la mise en page.",
            )
        )

    hors_marges = {
        f.page + 1
        for f in extraction.fragments
        if f.x < _MARGIN_TOLERANCE or f.x > extraction.page_sizes[f.page][0] - _MARGIN_TOLERANCE
    }
    if hors_marges:
        resultats.append(
            ATSCheckResult(
                "Mise en page : marges",
                ATSCheckStatus.WARNING,
                "Texte au ras du bord de page (risque de coupure) : page(s) "
                + ", ".join(map(str, sorted(hors_marges)))
                + ".",
            )
        )

    petits = [f for f in extraction.fragments if f.size < _MIN_FONT_SIZE]
    if petits:
        resultats.append(
            ATSCheckResult(
                "Mise en page : police",
                ATSCheckStatus.WARNING,
                f"Police inférieure à {_MIN_FONT_SIZE:g} pt détectée (lisibilité réduite).",
            )
        )

    if extraction.image_pages:
        resultats.append(
            ATSCheckResult(
                "Mise en page : images",
                ATSCheckStatus.WARNING,
                "Images détectées : elles ne sont pas lues par les ATS.",
            )
        )
    return resultats


def _verifier_mots_cles(texte: str, mots_cles: tuple[str, ...]) -> tuple[list[str], list[str]]:
    cible = _normaliser_comparaison(texte)
    trouves: list[str] = []
    absents: list[str] = []
    for mot in dict.fromkeys(mots_cles):
        motif = rf"(?<![\w+#]){re.escape(_normaliser_comparaison(mot))}(?![\w+#])"
        (trouves if re.search(motif, cible) else absents).append(mot)
    return trouves, absents
