"""Génération factuelle de la lettre (TASK-013-01 à 08, 013-16, 013-18)."""

from datetime import date
from typing import Any

import pytest

from app.modules.candidate_profile.domain.profile import (
    DocDate,
    EducationDoc,
    ExperienceDoc,
    Identity,
    ProfileDocument,
    SkillDoc,
)
from app.modules.document_generation.domain.cover_letter_conventions import (
    conventions_for,
    format_letter_date,
)
from app.modules.document_generation.domain.cover_letter_generator import (
    extract_company_offer_context,
    generate_cover_letter_content,
)
from app.modules.document_generation.domain.cover_letter_models import (
    CompanyOfferContext,
    CoverLetterContent,
    CoverLetterOptions,
    IncompleteProfileError,
    count_words,
)
from tests.unit.document_generation.cover_letter_samples import (
    AUJOURDHUI,
    DESCRIPTION_OFFRE,
    contexte_offre,
    profil_alice,
)


def _lettre(
    profil: ProfileDocument | None = None,
    ctx: CompanyOfferContext | None = None,
    **options: Any,
) -> CoverLetterContent:
    return generate_cover_letter_content(
        profil or profil_alice(),
        ctx or contexte_offre(),
        CoverLetterOptions(**options),
        today=AUJOURDHUI,
    )


def test_extraction_contexte_offre_sans_rien_deduire() -> None:
    ctx = contexte_offre()

    assert ctx.company_name == "Doctolib"
    assert ctx.responsibilities == (
        "Concevoir des API FastAPI robustes",
        "Écrire des requêtes SQL sur PostgreSQL",
        "Participer aux revues de code",
    )
    assert ctx.required_skills == ("Python", "FastAPI", "Rust")
    assert ctx.offer_text == DESCRIPTION_OFFRE


def test_entreprise_absente_ou_vide_reste_inconnue() -> None:
    for nom in (None, "", "   "):
        ctx = extract_company_offer_context(
            job_title="Dev", company_name=nom, offer_description="Texte."
        )
        assert ctx.company_name is None  # plus de « l'entreprise » inventé comme nom


def test_lettre_fr_en_quatre_parties_factuelles() -> None:
    lettre = _lettre()

    assert lettre.subject == "Candidature au poste de Développeur Python Backend"
    assert lettre.salutation == "Madame, Monsieur,"
    assert "Développeur Python Backend chez Doctolib (Paris)" in lettre.introduction
    assert "Concevoir" not in lettre.introduction  # verbe abaissé : « notamment concevoir »
    assert "notamment concevoir des API FastAPI robustes et écrire des requêtes" in (
        lettre.introduction
    )
    assert lettre.background_highlight.startswith(
        "Depuis 2021, j'exerce comme Lead Tech Python chez DataCorp."
    )
    assert "J'y mobilise notamment Python et FastAPI." in lettre.background_highlight
    assert "Parmi mes réalisations : Latence réduite de 40 % ; Migration vers PostgreSQL." in (
        lettre.background_highlight
    )
    assert "Plusieurs compétences demandées par l'offre figurent dans mon profil" in (
        lettre.added_value
    )
    assert "entretien" in lettre.closing_and_call_to_action
    assert all(lettre.body_paragraphs())


def test_aucun_fait_invente_regression_de_l_ancien_generateur() -> None:
    """L'ancienne lettre affirmait « solides compétences », « rigueur éprouvée », « France »…"""
    texte = _lettre().full_text() + _lettre(language="en").full_text()

    for invente in (
        "Fort de",
        "solide",
        "rigueur éprouvée",
        "résultats mesurables",
        "pluridisciplinaires",
        "Ingénieur",
        "France",
        "proven",
        "robust, maintainable",
    ):
        assert invente not in texte
    chiffres = {c for c in texte if c.isdigit()}
    assert chiffres <= set("2021403600332026418")  # profil, offre, date


def test_competence_absente_du_profil_jamais_citee() -> None:
    lettre = _lettre()
    assert "Rust" not in lettre.full_text()  # demandée par l'offre, absente du profil


def test_formulations_neutres_en_genre() -> None:
    texte = _lettre().full_text()
    for genre in ("ravi", "heureux", "attentif", "motivé", "Forte"):
        assert genre not in texte


def test_realisations_pertinentes_en_tete() -> None:
    profil = profil_alice()
    experience = profil.experiences[0].model_copy(
        update={"achievements": ("Organisation d'ateliers", "Migration vers FastAPI", "Revue")}
    )
    profil = profil.model_copy(update={"experiences": (experience, profil.experiences[1])})
    lettre = _lettre(profil)

    assert "Parmi mes réalisations : Migration vers FastAPI ; Organisation d'ateliers." in (
        lettre.background_highlight
    )


def test_seconde_experience_citee_seulement_si_pertinente() -> None:
    assert "De 2018 à 2021, j'ai exercé comme Développeuse Backend chez WebAgency." in (
        _lettre().background_highlight
    )

    sans_rapport = ExperienceDoc(
        title="Barista", company="Café", start=DocDate(year=2010), end=DocDate(year=2012)
    )
    profil = profil_alice().model_copy(
        update={"experiences": (profil_alice().experiences[0], sans_rapport)}
    )
    assert "Barista" not in _lettre(profil).background_highlight


def test_faits_utilises_traces_pour_le_controle() -> None:
    lettre = _lettre()

    assert ("DataCorp", "Lead Tech Python") in lettre.facts.experiences
    assert set(lettre.facts.skills) == {"Python", "FastAPI"}
    assert "Latence réduite de 40 %" in lettre.facts.achievements


def test_textes_de_l_utilisateur_inseres_tels_quels_et_marques() -> None:
    lettre = _lettre(
        custom_opening="Votre produit change le quotidien de 12 000 soignants.",
        motivation="J'ai suivi votre blog technique depuis 5 ans.",
    )

    assert lettre.introduction == "Votre produit change le quotidien de 12 000 soignants."
    assert "J'ai suivi votre blog technique depuis 5 ans." in lettre.added_value
    assert lettre.user_written == (
        "Votre produit change le quotidien de 12 000 soignants.",
        "J'ai suivi votre blog technique depuis 5 ans.",
    )


def test_destinataire_nomme_n_invente_pas_de_civilite() -> None:
    lettre = _lettre(recipient_name="Claire Martin", recipient_department="Recrutement")

    assert lettre.salutation == "Madame, Monsieur,"  # genre inconnu
    assert lettre.recipient_name == "Claire Martin"
    assert lettre.recipient_department == "Recrutement"


def test_sans_ville_pas_de_lieu_invente() -> None:
    profil = profil_alice().model_copy(
        update={"identity": profil_alice().identity.model_copy(update={"city": None})}
    )
    lettre = _lettre(profil)

    assert lettre.candidate_city is None
    assert lettre.date_and_location == "Le 4 novembre 2026"


def test_coordonnees_exactes() -> None:
    lettre = _lettre()
    assert (lettre.candidate_name, lettre.candidate_city) == ("Alice Mercier", "Paris")
    assert lettre.candidate_email == "alice.mercier@example.com"
    assert lettre.candidate_phone == "+33 6 00 00 00 00"
    assert lettre.signature == "Alice Mercier"
    assert lettre.date_and_location == "Paris, le 4 novembre 2026"


def test_lettre_anglaise_etats_unis_par_defaut() -> None:
    lettre = _lettre(language="en")

    assert lettre.subject == "Application for the position of Développeur Python Backend"
    assert lettre.salutation == "Dear Hiring Manager,"
    assert lettre.complimentary_close == "Sincerely,"
    assert lettre.date_and_location == "Paris, November 4, 2026"
    assert lettre.background_highlight.startswith(
        "Since 2021, I work as Lead Tech Python at DataCorp."
    )
    assert "Among my achievements: Latence réduite de 40 %; Migration vers PostgreSQL." in (
        lettre.background_highlight
    )
    assert "interview" in lettre.closing_and_call_to_action


def test_lettre_anglaise_style_britannique() -> None:
    lettre = _lettre(language="en", country_code="gb")

    assert lettre.salutation == "Dear Sir or Madam,"
    assert lettre.complimentary_close == "Yours faithfully,"
    assert lettre.date_and_location == "Paris, 4 November 2026"


def test_conventions_par_pays() -> None:
    assert (
        conventions_for(language="en", country_code="GB", recipient_name="Ms Smith").salutation
        == "Dear Ms Smith,"
    )
    assert (
        conventions_for(
            language="en", country_code="GB", recipient_name="Ms Smith"
        ).complimentary_close
        == "Yours sincerely,"
    )
    assert (
        conventions_for(
            language="en", country_code="US", recipient_name="Ms Smith"
        ).complimentary_close
        == "Sincerely,"
    )
    francais = conventions_for(language="fr", country_code="CA", recipient_name=None)
    assert "salutations distinguées" in francais.complimentary_close
    assert francais.labels.subject_label == "Objet"


def test_format_de_date() -> None:
    jour = date(2026, 3, 1)
    assert format_letter_date(jour, language="fr", country_code=None, city="Lyon") == (
        "Lyon, le 1 mars 2026"
    )
    assert format_letter_date(jour, language="en", country_code="IE", city=None) == "1 March 2026"


def test_langue_non_geree_refusee_au_lieu_de_basculer_en_francais() -> None:
    """Avant : « de » produisait une lettre française étiquetée allemande."""
    with pytest.raises(ValueError, match="language"):
        CoverLetterOptions(language="de")
    with pytest.raises(ValueError, match="country_code"):
        CoverLetterOptions(country_code="FRA")


def test_profil_sans_nom_refuse() -> None:
    profil = profil_alice().model_copy(update={"identity": Identity(city="Paris")})
    with pytest.raises(IncompleteProfileError, match="nom"):
        _lettre(profil)


def test_profil_vide_refuse() -> None:
    profil = ProfileDocument(identity=Identity(first_name="Alice", last_name="Mercier"))
    with pytest.raises(IncompleteProfileError):
        _lettre(profil)


def test_sans_experience_la_formation_puis_les_competences() -> None:
    avec_formation = ProfileDocument(
        identity=Identity(first_name="Alice", last_name="Mercier"),
        educations=(EducationDoc(degree="Master Informatique", institution="Université de Lyon"),),
    )
    lettre = _lettre(avec_formation)
    assert "Mon parcours de formation comprend Master Informatique (Université de Lyon)." in (
        lettre.background_highlight
    )
    assert lettre.facts.degrees == ("Master Informatique",)

    seulement_competences = ProfileDocument(
        identity=Identity(first_name="Alice", last_name="Mercier"),
        skills=(SkillDoc(name="Python"), SkillDoc(name="Docker")),
    )
    assert (
        "compétences suivantes : Python et Docker."
        in _lettre(seulement_competences).background_highlight
    )


def test_sans_competence_commune_aucune_affirmation_d_adequation() -> None:
    profil = ProfileDocument(
        identity=Identity(first_name="Alice", last_name="Mercier"),
        experiences=(ExperienceDoc(title="Boulangère", company="Fournil", is_current=True),),
        skills=(SkillDoc(name="Pâtisserie"),),
    )
    lettre = _lettre(profil)

    assert "figurent dans mon profil" not in lettre.added_value
    assert "rejoignent mon parcours" not in lettre.introduction
    assert "Un échange me permettrait de comprendre les besoins de Doctolib" in lettre.added_value


def test_entreprise_inconnue_formulations_sans_nom() -> None:
    lettre = _lettre(ctx=contexte_offre(company_name=None, company_location=None))

    assert lettre.recipient_company is None
    assert " chez " not in lettre.introduction
    assert "Doctolib" not in lettre.full_text()


def test_la_lettre_sans_apport_personnel_est_courte_donc_signalee_ailleurs() -> None:
    """Honnêteté : sans texte de l'utilisateur, on ne remplit pas pour atteindre 250 mots."""
    assert count_words(_lettre().body_text()) < 250
