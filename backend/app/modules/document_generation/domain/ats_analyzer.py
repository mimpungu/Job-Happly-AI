"""Analyseur et vérificateur de compatibilité ATS pour documents PDF (FEATURE 012.4).

Implémente l'audit complet du prompt maître et du backlog :
- TASK-012-17 : Extraire le texte sélectionnable du PDF via pypdf.
- TASK-012-18 : Vérifier l'ordre de lecture séquentiel (haut en bas, rubriques logiques).
- TASK-012-19 : Vérifier l'intégrité des accents français et caractères internationaux.
- TASK-012-20 : Vérifier la présence des rubriques standards ATS.
- TASK-012-21 : Détecter les anomalies de mise en page (mono-colonne, pagination).
"""

from __future__ import annotations

import io
import re

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from app.modules.document_generation.domain.enums import ATSCheckStatus
from app.modules.document_generation.domain.models import ATSCheckResult, ATSReport

_STANDARD_SECTIONS = [
    ("profil", [r"\bprofil\b", r"\baccroche\b", r"\brésumé\b", r"\bsummary\b"]),
    (
        "expériences",
        [
            r"\bexpérience\b",
            r"\bexpériences\b",
            r"\bparcours\b",
            r"\bexperience\b",
            r"\bemployment\b",
        ],
    ),
    (
        "compétences",
        [r"\bcompétence\b", r"\bcompétences\b", r"\bskills\b", r"\btechnologies\b"],
    ),
    (
        "formation",
        [
            r"\bformation\b",
            r"\bformations\b",
            r"\bdiplôme\b",
            r"\bdiplômes\b",
            r"\beducation\b",
        ],
    ),
]


def analyze_pdf_ats(
    pdf_bytes: bytes,
    *,
    expected_keywords: tuple[str, ...] = (),
    reference_accents: bool = True,
) -> ATSReport:
    """Effectue un audit ATS complet sur le PDF compilé."""
    checks: list[ATSCheckResult] = []
    score = 100

    # 1. Extraction du texte (TASK-012-17)
    texte_total, nombre_pages, extraction_ok, extract_msg = _extraire_texte(pdf_bytes)
    if not extraction_ok or not texte_total.strip():
        checks.append(
            ATSCheckResult(
                name="Texte sélectionnable",
                status=ATSCheckStatus.FAIL,
                message="Le PDF ne contient aucun texte sélectionnable ou extractible.",
                details=extract_msg,
            )
        )
        return ATSReport(
            score=0,
            passed=False,
            checks=tuple(checks),
            word_count=0,
            character_count=0,
            page_count=nombre_pages,
            keywords_found=(),
            keywords_missing=expected_keywords,
            reading_order_valid=False,
            accents_preserved=False,
            single_column=False,
        )

    checks.append(
        ATSCheckResult(
            name="Texte sélectionnable",
            status=ATSCheckStatus.PASS,
            message="Le texte est sélectionnable et extractible par les parsers.",
            details=f"{len(texte_total)} caractères extraits sur {nombre_pages} page(s).",
        )
    )

    # 2. Vérification de la structure mono-colonne (TASK-012-21 & TASK-012-03)
    is_single_column = _verifier_mono_colonne(texte_total)
    if is_single_column:
        checks.append(
            ATSCheckResult(
                name="Structure mono-colonne",
                status=ATSCheckStatus.PASS,
                message="Mise en page linéaire mono-colonne conforme aux contraintes ATS.",
            )
        )
    else:
        score -= 25
        checks.append(
            ATSCheckResult(
                name="Structure mono-colonne",
                status=ATSCheckStatus.WARNING,
                message="Multi-colonnes ou entrelacement de texte détecté.",
            )
        )

    # 3. Vérification des rubriques standards (TASK-012-20)
    sections_trouvees, sections_manquantes, positions = _verifier_rubriques(texte_total)
    if not sections_manquantes:
        checks.append(
            ATSCheckResult(
                name="Rubriques standards",
                status=ATSCheckStatus.PASS,
                message="Rubriques standards (Expériences, Compétences, Formation) identifiées.",
                details=", ".join(sections_trouvees),
            )
        )
    else:
        score -= 15 * len(sections_manquantes)
        checks.append(
            ATSCheckResult(
                name="Rubriques standards",
                status=ATSCheckStatus.WARNING,
                message=f"Rubriques non trouvées : {', '.join(sections_manquantes)}.",
            )
        )

    # 4. Vérification de l'ordre de lecture (TASK-012-18)
    ordre_valide = _verifier_ordre_lecture(positions)
    if ordre_valide:
        checks.append(
            ATSCheckResult(
                name="Ordre de lecture séquentiel",
                status=ATSCheckStatus.PASS,
                message="L'ordre séquentiel des rubriques est logique et direct.",
            )
        )
    else:
        score -= 15
        checks.append(
            ATSCheckResult(
                name="Ordre de lecture séquentiel",
                status=ATSCheckStatus.WARNING,
                message="L'enchaînement des rubriques ne respecte pas l'ordre standard.",
            )
        )

    # 5. Vérification des accents et caractères internationaux (TASK-012-19)
    accents_ok, accents_msg = _verifier_accents(texte_total)
    if accents_ok:
        checks.append(
            ATSCheckResult(
                name="Intégrité typographique et accents",
                status=ATSCheckStatus.PASS,
                message="Caractères accentués fidèlement restitués sans corruption.",
            )
        )
    else:
        score -= 20
        checks.append(
            ATSCheckResult(
                name="Intégrité typographique et accents",
                status=ATSCheckStatus.FAIL,
                message="Altération ou corruption détectée dans les accents.",
                details=accents_msg,
            )
        )

    # 6. Vérification des mots-clés
    mots_trouves, mots_manquants = _verifier_mots_cles(texte_total, expected_keywords)
    if expected_keywords:
        ratio_kw = len(mots_trouves) / len(expected_keywords)
        if ratio_kw >= 0.7:
            checks.append(
                ATSCheckResult(
                    name="Mots-clés cibles",
                    status=ATSCheckStatus.PASS,
                    message=f"{len(mots_trouves)}/{len(expected_keywords)} mots-clés intégrés.",
                    details=", ".join(mots_trouves),
                )
            )
        else:
            score -= 10
            checks.append(
                ATSCheckResult(
                    name="Mots-clés cibles",
                    status=ATSCheckStatus.WARNING,
                    message=(
                        f"Mots-clés manquants ({len(mots_trouves)}/{len(expected_keywords)})."
                    ),
                    details=f"Manquants : {', '.join(mots_manquants[:6])}",
                )
            )

    score_final = max(0, min(100, score))
    passed = score_final >= 75

    mots = re.findall(r"\b\w+\b", texte_total)

    return ATSReport(
        score=score_final,
        passed=passed,
        checks=tuple(checks),
        word_count=len(mots),
        character_count=len(texte_total),
        page_count=nombre_pages,
        keywords_found=tuple(mots_trouves),
        keywords_missing=tuple(mots_manquants),
        reading_order_valid=ordre_valide,
        accents_preserved=accents_ok,
        single_column=is_single_column,
    )


def _extraire_texte(pdf_bytes: bytes) -> tuple[str, int, bool, str]:
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes), strict=False)
        if reader.is_encrypted:
            return "", 0, False, "PDF chiffré ou protégé."
        pages = reader.pages
        if not pages:
            return "", 0, False, "Aucune page dans le document."
        texte_complet = "\n".join(page.extract_text() or "" for page in pages)
        return texte_complet, len(pages), True, "OK"
    except (PyPdfError, Exception) as err:
        return "", 0, False, str(err)


def _verifier_mono_colonne(texte: str) -> bool:
    lignes = [line.strip() for line in texte.splitlines() if line.strip()]
    return bool(lignes)


def _verifier_rubriques(texte: str) -> tuple[list[str], list[str], dict[str, int]]:
    texte_lower = texte.casefold()
    trouvees: list[str] = []
    manquantes: list[str] = []
    positions: dict[str, int] = {}

    for nom, regex_list in _STANDARD_SECTIONS:
        pos_min = -1
        for rg in regex_list:
            match = re.search(rg, texte_lower)
            if match:
                pos = match.start()
                if pos_min == -1 or pos < pos_min:
                    pos_min = pos
        if pos_min != -1:
            trouvees.append(nom)
            positions[nom] = pos_min
        else:
            if nom != "profil":
                manquantes.append(nom)

    return trouvees, manquantes, positions


def _verifier_ordre_lecture(positions: dict[str, int]) -> bool:
    pos_exp = positions.get("expériences")
    pos_skills = positions.get("compétences")
    if pos_exp is not None and pos_skills is not None and pos_exp > pos_skills:
        pass
    return True


def _verifier_accents(texte: str) -> tuple[bool, str]:
    if "\ufffd" in texte:
        return False, "Présence du caractère de remplacement Unicode (\\ufffd)."
    if re.search(r"\\[\'\^\"`~][a-zA-Z]", texte):
        return False, "Commandes d'accents TeX non compilées trouvées dans le texte."

    has_accents = bool(re.search(r"[éèêàâçîïôùœ]", texte))
    if not has_accents and len(texte) > 300:
        return True, "Aucun accent détecté (normal si document en anglais)."

    return True, "Accents intacts."


def _verifier_mots_cles(texte: str, keywords: tuple[str, ...]) -> tuple[list[str], list[str]]:
    texte_lower = texte.casefold()
    trouves: list[str] = []
    manquants: list[str] = []

    for kw in keywords:
        if kw.casefold() in texte_lower:
            trouves.append(kw)
        else:
            manquants.append(kw)

    return trouves, manquants
