"""Contrôle des faits et audit éditorial de la lettre (TASK-013-09, 10, 11, 18)."""

from dataclasses import replace
from typing import Any

import pytest

from app.modules.document_generation.domain.cover_letter_audit import (
    audit_letter,
    audit_letter_text,
    find_writing_issues,
    normalize,
    verify_letter_facts,
)
from app.modules.document_generation.domain.cover_letter_generator import (
    generate_cover_letter_content,
)
from app.modules.document_generation.domain.cover_letter_models import (
    CoverLetterAudit,
    CoverLetterContent,
    CoverLetterOptions,
    LetterFacts,
)
from tests.unit.document_generation.cover_letter_samples import (
    AUJOURDHUI,
    contexte_offre,
    profil_alice,
)

PROFIL = profil_alice()
CONTEXTE = contexte_offre()


def _lettre(**options: Any) -> CoverLetterContent:
    return generate_cover_letter_content(
        PROFIL, CONTEXTE, CoverLetterOptions(**options), today=AUJOURDHUI
    )


def _faits(lettre: CoverLetterContent) -> tuple[str, ...]:
    return verify_letter_facts(lettre, PROFIL, CONTEXTE, today=AUJOURDHUI)


def _texte_libre(n: int) -> str:
    return " ".join(f"terme{i}" for i in range(n))


def test_lettre_generee_est_coherente_avec_le_cv() -> None:
    assert _faits(_lettre()) == ()
    assert _faits(_lettre(language="en", country_code="GB")) == ()


def test_chiffre_invente_dans_le_texte_genere_est_detecte() -> None:
    lettre = replace(_lettre(), background_highlight="J'ai dirigé 250 personnes pendant 10 ans.")
    issues = _faits(lettre)

    assert any("250" in i for i in issues)
    assert any("10" in i for i in issues)


def test_chiffres_du_profil_et_de_l_offre_acceptes() -> None:
    lettre = replace(_lettre(), added_value="Latence réduite de 40 %, équipe de 3, depuis 2021.")
    assert _faits(lettre) == ()


def test_texte_de_l_utilisateur_n_est_pas_juge() -> None:
    lettre = _lettre(motivation="Je suis votre blog depuis 15 ans.")
    assert _faits(lettre) == ()


@pytest.mark.parametrize(
    ("modification", "attendu"),
    [
        (LetterFacts(experiences=(("Google", "CTO"),)), "Expérience absente"),
        (LetterFacts(skills=("Rust",)), "Compétence absente"),
        (LetterFacts(achievements=("Levée de fonds de 5 M€",)), "Réalisation absente"),
        (LetterFacts(degrees=("Doctorat",)), "Diplôme absent"),
    ],
)
def test_fait_structurel_invente_est_detecte(modification: LetterFacts, attendu: str) -> None:
    issues = _faits(replace(_lettre(), facts=modification))
    assert any(attendu in i for i in issues)


def test_coordonnees_alterees_detectees() -> None:
    lettre = replace(
        _lettre(),
        candidate_email="autre@example.com",
        candidate_phone="+33 1 23",
        candidate_name="Alice Dupont",
        candidate_city="Lyon",
    )
    issues = _faits(lettre)

    for coordonnee in ("nom", "e-mail", "téléphone", "ville"):
        assert any(f"« {coordonnee} »" in i for i in issues)


def test_audit_d_une_lettre_generee_est_honnete() -> None:
    lettre = _lettre()
    audit = audit_letter(lettre, PROFIL, CONTEXTE, today=AUJOURDHUI, page_count=1)

    assert audit.cv_coherent is True
    assert audit.passed is True
    assert audit.generic_phrases_detected == ()
    assert audit.length_status == "short"
    assert audit.is_length_optimal is False
    assert audit.word_count == lettre.word_count
    assert any("Lettre courte" in i for i in audit.issues)
    assert any("Aucun texte personnel" in i for i in audit.issues)
    assert audit.relevance_score == 30
    assert audit.experience_score == 20
    assert audit.score == (
        audit.relevance_score
        + audit.personalization_score
        + audit.experience_score
        + audit.editorial_score
        + audit.structure_score
    )


def test_apport_personnel_augmente_la_personnalisation_et_la_longueur() -> None:
    sans = audit_letter(_lettre(), PROFIL, CONTEXTE, today=AUJOURDHUI, page_count=1)
    avec = audit_letter(
        _lettre(motivation=_texte_libre(170)), PROFIL, CONTEXTE, today=AUJOURDHUI, page_count=1
    )

    assert avec.personalization_score == sans.personalization_score + 10
    assert avec.length_status == "optimal"
    assert avec.is_length_optimal is True
    assert avec.score > sans.score


def test_lettre_trop_longue_signalee() -> None:
    lettre = replace(_lettre(), added_value=_texte_libre(380))
    audit = audit_letter(lettre, PROFIL, CONTEXTE, today=AUJOURDHUI, page_count=1)
    assert audit.length_status == "long"
    assert any("Lettre longue" in i for i in audit.issues)


def test_depassement_d_une_page_bloque_la_validation() -> None:
    audit = audit_letter(_lettre(), PROFIL, CONTEXTE, today=AUJOURDHUI, page_count=2)

    assert audit.passed is False
    assert any("dépasse une page" in i for i in audit.issues)


@pytest.mark.parametrize(
    "cliche",
    [
        "Je suis extrêmement motivé par ce poste.",
        "Je serais le candidat parfait.",
        "Je mets mes compétences à votre entière disposition.",
        "Fort d'une solide expérience, je postule.",
        "Fort d\u2019une solide expérience, je postule.",  # apostrophe typographique
        "Je me permets de vous adresser ma candidature.",
    ],
)
def test_cliches_du_prompt_maitre_detectes(cliche: str) -> None:
    audit = audit_letter(
        _lettre(motivation=cliche), PROFIL, CONTEXTE, today=AUJOURDHUI, page_count=1
    )

    assert audit.passed is False
    assert audit.generic_phrases_detected
    assert audit.editorial_score < 15


def test_cliches_anglais_detectes() -> None:
    audit = audit_letter(
        _lettre(language="en", motivation="I am the perfect candidate and dynamic and motivated."),
        PROFIL,
        CONTEXTE,
        today=AUJOURDHUI,
        page_count=1,
    )
    assert set(audit.generic_phrases_detected) == {
        "perfect candidate",
        "dynamic and motivated",
    }


def test_fait_invente_rend_la_lettre_incoherente() -> None:
    lettre = replace(_lettre(), facts=LetterFacts(experiences=(("Google", "CTO"),)))
    audit = audit_letter(lettre, PROFIL, CONTEXTE, today=AUJOURDHUI, page_count=1)

    assert audit.cv_coherent is False  # avant : toujours True
    assert audit.passed is False


def test_audit_pertinence_intitule_entreprise_et_missions() -> None:
    lettre = replace(
        _lettre(),
        subject="Candidature",
        introduction="Bonjour.",
        added_value="Texte sans rapport.",
        closing_and_call_to_action="Merci de m'écouter lors d'un entretien.",
    )
    audit = audit_letter(lettre, PROFIL, CONTEXTE, today=AUJOURDHUI, page_count=1)

    assert audit.relevance_score < 30
    assert audit.personalization_score < 25
    assert any("intitulé exact du poste" in i for i in audit.issues)
    assert any("nom de l'entreprise" in i for i in audit.issues)


def test_sans_demande_d_entretien() -> None:
    lettre = replace(_lettre(), closing_and_call_to_action="Cordialement.", complimentary_close="")
    audit = audit_letter(lettre, PROFIL, CONTEXTE, today=AUJOURDHUI, page_count=1)
    assert any("demande d'entretien" in i for i in audit.issues)


def test_salutation_non_conforme_a_la_langue() -> None:
    lettre = replace(_lettre(language="en"), salutation="Madame, Monsieur,")
    audit = audit_letter(lettre, PROFIL, CONTEXTE, today=AUJOURDHUI, page_count=1)
    assert any("formule de politesse non conforme" in i for i in audit.issues)


@pytest.mark.parametrize(
    ("texte", "attendu"),
    [
        ("Je postule pour pour ce poste.", "Mot répété"),
        ("Le poste est ouvert. je postule.", "minuscule"),
        ("Python,FastAPI et Docker.", "Espace manquant"),
        ("Voici ma candidature,, merci.", "Ponctuation doublée"),
        ("Une phrase (non fermée.", "Parenthèses"),
        ("Un « guillemet ouvert.", "Guillemets"),
    ],
)
def test_erreurs_d_ecriture_evidentes(texte: str, attendu: str) -> None:
    assert any(attendu in p for p in find_writing_issues(texte))


def test_ecriture_correcte_ne_leve_rien() -> None:
    assert find_writing_issues("Nous nous retrouvons à 9 h. Vous vous êtes déjà présenté.") == []
    assert find_writing_issues("Maîtrise de Node.js, Python et C++ (niveau avancé).") == []


def test_erreurs_d_ecriture_pesent_sur_le_score_editorial() -> None:
    propre = audit_letter(_lettre(), PROFIL, CONTEXTE, today=AUJOURDHUI, page_count=1)
    sale = audit_letter(
        _lettre(motivation="Je postule pour pour ce poste,, avec (soin."),
        PROFIL,
        CONTEXTE,
        today=AUJOURDHUI,
        page_count=1,
    )
    assert sale.spelling_issues
    assert sale.editorial_score < propre.editorial_score


def test_audit_d_un_texte_edite_est_reel_et_non_fabrique() -> None:
    """Avant : toute version éditée recevait un faux score fixe de 85."""
    texte = (
        "Alice Mercier Paris\nObjet : Candidature au poste de Développeur Python Backend\n"
        "Madame, Monsieur,\nJe suis extrêmement motivé par Doctolib. J'exerce chez DataCorp "
        "avec Python et FastAPI depuis 2021 et ai géré 900 clients.\n"
        "Je serais disponible pour un entretien.\nJe vous prie d'agréer, Madame, Monsieur, "
        "l'expression de mes salutations distinguées."
    )
    audit = audit_letter_text(
        texte, language="fr", profile=PROFIL, context=CONTEXTE, today=AUJOURDHUI, page_count=1
    )

    assert audit.score != 85
    assert audit.generic_phrases_detected == ("extrêmement motivé",)
    assert audit.cv_coherent is False  # « 900 » sans source
    assert audit.passed is False
    assert audit.experience_score == 20


def test_audit_d_un_texte_edite_sans_reference_ne_peut_pas_certifier_la_coherence() -> None:
    audit = audit_letter_text(
        "Madame, Monsieur, je postule. Cordialement.",
        language="fr",
        profile=None,
        context=None,
        today=AUJOURDHUI,
        page_count=1,
    )
    assert audit.cv_coherent is False
    assert audit.passed is False
    assert any("Profil validé introuvable" in i for i in audit.issues)


def test_audit_aller_retour_dictionnaire() -> None:
    audit = audit_letter(_lettre(), PROFIL, CONTEXTE, today=AUJOURDHUI, page_count=1)
    assert CoverLetterAudit.from_dict(audit.to_dict()) == audit


def test_normalisation_des_textes() -> None:
    assert normalize("  L\u2019ENTREPRISE\u00a0 ") == "l'entreprise"
