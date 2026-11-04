"""Contrôle strict des faits (TASK-012-10).

Règle absolue du projet : un document généré ne contient QUE des faits du profil maître.
Le contrôle est structurel : chaque expérience, formation, certification, langue et
réalisation du CV doit retrouver son original, champ par champ. Un texte libre généré
(accroche) ne peut contenir aucun chiffre absent du profil.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from app.modules.document_generation.domain.models import FactCheckResult

if TYPE_CHECKING:
    from app.modules.candidate_profile.domain.profile import ProfileDocument

_NOMBRE = re.compile(r"\d+(?:[.,]\d+)?")


class UnverifiedFactError(ValueError):
    """Exception levée lorsqu'un fait inventé ou non sourcé est détecté."""


def _cle(valeur: str | None) -> str:
    return (valeur or "").casefold().strip()


def verify_facts(
    master_profile: ProfileDocument,
    generated_profile: ProfileDocument,
    *,
    generated_summary: str | None = None,
) -> FactCheckResult:
    """Compare le profil généré au profil maître.

    `generated_summary` : accroche produite par le système (pas celle de l'utilisateur) ;
    ses nombres doivent exister dans le profil maître.
    """
    issues: list[str] = []
    entreprises: list[str] = []
    etablissements: list[str] = []
    competences: list[str] = []

    _verifier_identite(master_profile, generated_profile, issues)
    _verifier_experiences(master_profile, generated_profile, issues, entreprises)
    _verifier_formations(master_profile, generated_profile, issues, etablissements)

    maitre_competences = {_cle(s.name) for s in master_profile.skills}
    for s in generated_profile.skills:
        if _cle(s.name) not in maitre_competences:
            competences.append(s.name)
            issues.append(f"Compétence non vérifiée dans le profil maître : '{s.name}'")

    maitre_certifs = {
        (_cle(c.name), _cle(c.issuer), c.issued_on) for c in master_profile.certifications
    }
    for c in generated_profile.certifications:
        if (_cle(c.name), _cle(c.issuer), c.issued_on) not in maitre_certifs:
            issues.append(f"Certification non vérifiée dans le profil maître : '{c.name}'")

    maitre_langues = {
        (lg.language_code, _cle(lg.level_text), lg.proficiency) for lg in master_profile.languages
    }
    for lg in generated_profile.languages:
        if (lg.language_code, _cle(lg.level_text), lg.proficiency) not in maitre_langues:
            issues.append(
                f"Langue ou niveau non vérifié dans le profil maître : '{lg.language_code}'"
            )

    if generated_summary:
        _verifier_nombres(master_profile, generated_summary, issues)

    return FactCheckResult(
        is_valid=not issues,
        unverified_companies=tuple(entreprises),
        unverified_institutions=tuple(etablissements),
        unverified_skills=tuple(competences),
        issues=tuple(issues),
    )


def _verifier_identite(master: ProfileDocument, genere: ProfileDocument, issues: list[str]) -> None:
    if genere.identity != master.identity:
        issues.append("Identité modifiée par rapport au profil maître.")


def _verifier_experiences(
    master: ProfileDocument, genere: ProfileDocument, issues: list[str], entreprises: list[str]
) -> None:
    originaux = {(_cle(e.company), _cle(e.title)): e for e in master.experiences}
    for exp in genere.experiences:
        original = originaux.get((_cle(exp.company), _cle(exp.title)))
        if original is None:
            entreprises.append(exp.company or "")
            issues.append(
                f"Expérience non vérifiée dans le profil maître : '{exp.title}' "
                f"chez '{exp.company}'"
            )
            continue
        for champ in ("start", "end", "is_current", "location", "description"):
            if getattr(exp, champ) != getattr(original, champ):
                issues.append(
                    f"Champ '{champ}' modifié pour l'expérience '{exp.title}' ('{exp.company}')."
                )
        inventees = [a for a in exp.achievements if a not in original.achievements]
        for realisation in inventees:
            issues.append(
                f"Réalisation absente du profil maître pour '{exp.title}' : '{realisation}'"
            )


def _verifier_formations(
    master: ProfileDocument, genere: ProfileDocument, issues: list[str], etablissements: list[str]
) -> None:
    originaux = {(_cle(e.institution), _cle(e.degree)): e for e in master.educations}
    for edu in genere.educations:
        original = originaux.get((_cle(edu.institution), _cle(edu.degree)))
        if original is None:
            etablissements.append(edu.institution or "")
            issues.append(
                f"Formation non vérifiée dans le profil maître : '{edu.degree}' "
                f"à '{edu.institution}'"
            )
        elif edu != original:
            issues.append(f"Formation modifiée par rapport au profil maître : '{edu.degree}'")


def _verifier_nombres(master: ProfileDocument, texte: str, issues: list[str]) -> None:
    corpus = master.model_dump_json()
    for nombre in dict.fromkeys(_NOMBRE.findall(texte)):
        if nombre not in corpus:
            issues.append(f"Nombre sans source dans le profil maître (accroche) : '{nombre}'")


def assert_facts_verified(
    master_profile: ProfileDocument,
    generated_profile: ProfileDocument,
    *,
    generated_summary: str | None = None,
) -> None:
    """Valide les faits ou lève UnverifiedFactError."""
    result = verify_facts(master_profile, generated_profile, generated_summary=generated_summary)
    if not result.is_valid:
        raise UnverifiedFactError(
            "Le CV généré contient des faits non prouvés : " + "; ".join(result.issues)
        )
