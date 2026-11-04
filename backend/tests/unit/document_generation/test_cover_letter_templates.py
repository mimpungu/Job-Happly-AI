"""Tests unitaires du template LaTeX de lettre de motivation (TASK-013-12)."""

from app.modules.document_generation.domain.cover_letter_models import CoverLetterContent
from app.modules.document_generation.domain.cover_letter_templates import (
    render_latex_cover_letter,
)


def _content_exemple_fr() -> CoverLetterContent:
    return CoverLetterContent(
        candidate_name="Sarah Connor",
        candidate_address="Lyon, France",
        candidate_email="sarah@example.com",
        candidate_phone="+33 6 98 76 54 32",
        recipient_company="Cyberdyne Systems France",
        recipient_department="Direction Technique",
        date_and_location="Lyon, le 4 novembre 2026",
        subject="Candidature au poste de Lead Architecte Systèmes",
        salutation="Madame, Monsieur,",
        introduction="Votre recherche d'un profil de Lead Architecte a retenu toute mon attention.",
        background_highlight=(
            "Au cours de mes précédentes responsabilités, j'ai piloté des architectures critiques."
        ),
        added_value="Rejoindre Cyberdyne représente l'opportunité d'apporter une rigueur éprouvée.",
        closing_and_call_to_action=(
            "Je serais ravie d'échanger avec vous lors d'un prochain entretien."
        ),
        complimentary_close="Je vous prie d'agréer mes salutations distinguées.",
        signature="Sarah Connor",
        word_count=280,
    )


def test_render_latex_cover_letter_structure() -> None:
    content = _content_exemple_fr()
    tex = render_latex_cover_letter(content)

    assert r"\documentclass[11pt,a4paper]{article}" in tex
    assert "Sarah Connor" in tex
    assert "Cyberdyne Systems France" in tex
    assert "Candidature au poste de Lead Architecte" in tex
    assert "Madame, Monsieur," in tex
    assert "architectures critiques" in tex
    assert r"\begin{minipage}" in tex  # Utilisé proprement pour les deux blocs d'adresses d'en-tête
    assert "Lyon, le 4 novembre 2026" in tex


def test_render_latex_cover_letter_accents_et_echappement() -> None:
    content = _content_exemple_fr()
    tex = render_latex_cover_letter(content)

    assert r"\usepackage[utf8]{inputenc}" in tex
    assert r"\usepackage[T1]{fontenc}" in tex
    assert "salutations distinguées" in tex
