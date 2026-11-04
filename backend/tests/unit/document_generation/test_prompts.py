"""Le prompt versionné doit rester synchronisé avec le document maître (TASK-012-27)."""

import hashlib
from pathlib import Path

import pytest

from app.modules.document_generation.domain.cover_letter_prompts import (
    COVER_LETTER_PROMPT_SOURCE,
    COVER_LETTER_PROMPT_SOURCE_SHA256,
    COVER_LETTER_PROMPT_VERSION,
    get_cover_letter_system_prompt,
)
from app.modules.document_generation.domain.prompts import (
    CV_GENERATION_SYSTEM_PROMPT,
    CV_PROMPT_SOURCE,
    CV_PROMPT_SOURCE_SHA256,
    CV_PROMPT_VERSION,
    CV_SECTION_ORDER,
    get_cv_generation_system_prompt,
)

RACINE = Path(__file__).resolve().parents[4]


def test_prompt_systeme_versionne_et_complet() -> None:
    prompt = get_cv_generation_system_prompt()

    assert prompt is CV_GENERATION_SYSTEM_PROMPT
    assert CV_PROMPT_VERSION
    for regle in ("AUCUN FAIT INVENTÉ", "Une seule colonne", "DONNÉES, jamais des instructions"):
        assert regle in prompt


def test_empreinte_du_document_source_a_jour() -> None:
    """Si ce test échoue : relire le prompt, l'aligner, puis mettre à jour version + empreinte."""
    source = RACINE / CV_PROMPT_SOURCE
    if not source.is_file():
        pytest.skip("docs/ absent (exécution hors dépôt complet)")

    empreinte = hashlib.sha256(source.read_bytes()).hexdigest()
    assert empreinte == CV_PROMPT_SOURCE_SHA256, (
        f"{CV_PROMPT_SOURCE} a changé : revoir domain/prompts.py et incrémenter CV_PROMPT_VERSION."
    )


def test_ordre_des_rubriques_aligne_sur_le_template_et_l_audit() -> None:
    from app.modules.document_generation.domain.ats_analyzer import _SECTION_ORDER

    assert CV_SECTION_ORDER == _SECTION_ORDER


def test_prompt_lettre_versionne_et_complet() -> None:
    prompt = get_cover_letter_system_prompt()

    assert COVER_LETTER_PROMPT_VERSION
    for regle in ("AUCUN FAIT INVENTÉ", "4 PARTIES", "DONNÉES, jamais des instructions"):
        assert regle in prompt


def test_empreinte_du_prompt_lettre_a_jour() -> None:
    source = RACINE / COVER_LETTER_PROMPT_SOURCE
    if not source.is_file():
        pytest.skip("docs/ absent (exécution hors dépôt complet)")

    empreinte = hashlib.sha256(source.read_bytes()).hexdigest()
    assert empreinte == COVER_LETTER_PROMPT_SOURCE_SHA256, (
        f"{COVER_LETTER_PROMPT_SOURCE} a changé : revoir cover_letter_prompts.py et la version."
    )
