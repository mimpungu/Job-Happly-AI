"""Génération niveau 0 (sans IA) de la préparation d'entretien (TASK-016-01 à 016-06).

Tout ce qui est présenté comme un fait vient du profil validé ou de l'offre ; les questions sont
des modèles adaptés au poste. Ce qui ne peut pas être connu (résultat chiffré, motivation
personnelle) est marqué « à compléter », jamais inventé.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.modules.interview_preparation.domain.enums import QuestionCategory
from app.modules.interview_preparation.domain.models import (
    AnswerOutline,
    Highlight,
    OfferFacts,
    PreparationContent,
    Question,
)
from app.modules.interview_preparation.domain.text import mentions, norm

if TYPE_CHECKING:
    from app.modules.candidate_profile.domain.profile import ExperienceDoc, ProfileDocument

_MAX_SKILL_QUESTIONS = 6
_MAX_GAP_QUESTIONS = 3
_MAX_HIGHLIGHTS = 3


@dataclass(frozen=True)
class _Gabarits:
    hr: tuple[tuple[str, str], ...]
    behavioral: tuple[tuple[str, str], ...]
    skill: str
    gap: str
    recruiter: tuple[str, ...]
    recruiter_skill: str
    pitch_intro: str
    pitch_now: str
    pitch_skills: str
    pitch_fit: str
    pitch_motivation: str
    period_since: str
    to_complete_result: str
    to_complete_outcome: str


_FR = _Gabarits(
    hr=(
        ("Présentez-vous en quelques minutes.", "Ouverture classique de tout entretien."),
        (
            "Pourquoi ce poste de {title}{chez} vous intéresse-t-il ?",
            "Le recruteur teste votre motivation et votre connaissance de l'offre.",
        ),
        ("Quelles sont vos principales forces et points à améliorer ?", "Question d'auto-analyse."),
        (
            "Pourquoi quittez-vous (ou avez-vous quitté) votre poste actuel ?",
            "Cohérence du parcours.",
        ),
        ("Quelles sont vos prétentions salariales ?", "À préparer avant l'entretien."),
        ("Quand seriez-vous disponible ?", "Logistique de recrutement."),
        ("Où vous voyez-vous dans cinq ans ?", "Projection et alignement avec le poste."),
    ),
    behavioral=(
        (
            "Racontez une situation où vous avez résolu un conflit dans une équipe.",
            "Question comportementale : à structurer en Situation, Action, Résultat.",
        ),
        (
            "Décrivez un échec et ce que vous en avez appris.",
            "Évalue la prise de recul et la capacité d'apprentissage.",
        ),
        (
            "Parlez d'une réalisation dont vous êtes particulièrement fier.",
            "Permet de mettre en avant une réussite réelle de votre parcours.",
        ),
        (
            "Comment gérez-vous une échéance serrée ou une forte pression ?",
            "Évalue l'organisation et la gestion des priorités.",
        ),
    ),
    skill="Décrivez un cas concret où vous avez utilisé {skill}.",
    gap=(
        "L'offre demande {skill}, qui ne figure pas dans votre profil : "
        "comment l'aborderiez-vous ou l'apprendriez-vous ?"
    ),
    recruiter=(
        "Comment se déroule l'intégration pendant les premiers mois ?",
        "Comment l'équipe est-elle organisée et avec qui travaillerai-je au quotidien ?",
        "Quelles sont les prochaines étapes du processus de recrutement et leur calendrier ?",
        "Quels sont les principaux défis du poste dans les six premiers mois ?",
        "Quelles évolutions ce poste permet-il ?",
    ),
    recruiter_skill="Comment {skill} est-il utilisé dans l'équipe aujourd'hui ?",
    pitch_intro="Je m'appelle {name}.",
    pitch_now="J'occupe le poste de {title}{chez}{depuis}.",
    pitch_skills="Je travaille notamment avec {skills}.",
    pitch_fit="Votre offre de {title}{chez} correspond à mon parcours.",
    pitch_motivation="[À compléter : ce qui vous motive personnellement dans ce poste.]",
    period_since=" depuis {year}",
    to_complete_result="Résultat réel de cette réalisation (chiffre ou effet observé).",
    to_complete_outcome="Ce que cela a changé pour l'équipe ou l'entreprise.",
)

_EN = _Gabarits(
    hr=(
        ("Tell me about yourself.", "Standard opening of any interview."),
        (
            "Why are you interested in this {title} role{at}?",
            "Tests your motivation and how well you know the offer.",
        ),
        ("What are your main strengths and areas to improve?", "Self-assessment question."),
        ("Why are you leaving (or why did you leave) your current role?", "Career coherence."),
        ("What are your salary expectations?", "Prepare this before the interview."),
        ("When could you start?", "Hiring logistics."),
        ("Where do you see yourself in five years?", "Projection and fit with the role."),
    ),
    behavioral=(
        (
            "Tell me about a time you resolved a conflict within a team.",
            "Behavioral question: structure it as Situation, Action, Result.",
        ),
        (
            "Describe a failure and what you learned from it.",
            "Assesses perspective and ability to learn.",
        ),
        (
            "Tell me about an achievement you are particularly proud of.",
            "Lets you showcase a real success from your career.",
        ),
        (
            "How do you handle tight deadlines or high pressure?",
            "Assesses organisation and prioritisation.",
        ),
    ),
    skill="Describe a concrete case where you used {skill}.",
    gap=(
        "The offer asks for {skill}, which is not in your profile: "
        "how would you approach or learn it?"
    ),
    recruiter=(
        "How does onboarding work during the first months?",
        "How is the team organised and who will I work with day to day?",
        "What are the next steps of the hiring process and their timeline?",
        "What are the main challenges of the role in the first six months?",
        "What career growth does this role offer?",
    ),
    recruiter_skill="How is {skill} used in the team today?",
    pitch_intro="My name is {name}.",
    pitch_now="I currently work as {title}{at}{since}.",
    pitch_skills="I mainly work with {skills}.",
    pitch_fit="Your {title} role{at} matches my background.",
    pitch_motivation="[To complete: what personally motivates you in this role.]",
    period_since=" since {year}",
    to_complete_result="Actual outcome of this achievement (figure or observed effect).",
    to_complete_outcome="What it changed for the team or the company.",
)


def _gabarits(language: str) -> _Gabarits:
    return _EN if language.lower().startswith("en") else _FR


def _chez(language: str, company: str | None) -> tuple[str, str]:
    """Complément « chez X » (clé `chez` en français, `at` en anglais)."""
    if not company:
        return "", ""
    return f" chez {company}", f" at {company}"


def _label(exp: ExperienceDoc) -> str:
    titre = exp.title or "Poste"
    return f"{titre} — {exp.company}" if exp.company else titre


def _periode(exp: ExperienceDoc) -> str | None:
    debut = exp.start.label() if exp.start else None
    if exp.is_current and debut:
        return f"{debut} - aujourd'hui"
    fin = exp.end.label() if exp.end else None
    if debut and fin:
        return f"{debut} - {fin}"
    return debut


def _termes(offer: OfferFacts) -> list[str]:
    return list(dict.fromkeys(t.strip() for t in offer.required_skills if t.strip()))


def _termes_de_l_experience(exp: ExperienceDoc, termes: list[str]) -> tuple[str, ...]:
    texte = " ".join([exp.title or "", exp.description or "", *exp.achievements])
    return tuple(t for t in termes if mentions(texte, t))


def rank_highlights(
    profile: ProfileDocument, offer: OfferFacts
) -> list[tuple[ExperienceDoc, tuple[str, ...]]]:
    """Expériences les plus proches de l'offre ; sans recoupement, les plus récentes."""
    termes = _termes(offer)
    notees = [(exp, _termes_de_l_experience(exp, termes)) for exp in profile.experiences]
    # tri stable : à égalité de recoupement, l'ordre du profil (le plus récent d'abord) reste
    return sorted(notees, key=lambda paire: -len(paire[1]))[:_MAX_HIGHLIGHTS]


def build_preparation(
    profile: ProfileDocument, offer: OfferFacts, *, language: str = "fr"
) -> PreparationContent:
    g = _gabarits(language)
    chez_fr, chez_en = _chez(language, offer.company)
    chez = chez_en if language.lower().startswith("en") else chez_fr
    termes = _termes(offer)
    if not termes:
        # Offre non analysée : on ne retient que les compétences du profil que le texte cite
        # réellement (jamais une compétence devinée).
        texte_offre = f"{offer.title} {offer.description}"
        termes = [s.name for s in profile.skills if mentions(texte_offre, s.name)]
    possedees = {norm(s.name): s.name for s in profile.skills}
    couvertes = tuple(
        t
        for t in termes
        if norm(t) in possedees or any(mentions(s.name, t) for s in profile.skills)
    )
    manquantes = tuple(t for t in termes if t not in couvertes)

    warnings: list[str] = []
    if not offer.description.strip():
        warnings.append("L'offre n'a pas de description : les questions restent génériques.")
    if not offer.required_skills:
        if termes:
            warnings.append(
                "Offre non analysée : les questions techniques se limitent aux compétences de "
                "votre profil citées dans l'offre. Lancez l'analyse pour les affiner."
            )
        else:
            warnings.append(
                "Aucune compétence détectée dans l'offre : lancez l'analyse de l'offre pour "
                "cibler les questions techniques."
            )
    if not profile.experiences:
        warnings.append(
            "Le profil ne contient aucune expérience : les trames de réponse sont vides."
        )

    questions = _questions(g, offer, chez, couvertes, manquantes)
    classement = rank_highlights(profile, offer)
    highlights = tuple(
        Highlight(
            experience_label=_label(exp),
            matched_terms=trouves,
            achievements=exp.achievements[:3],
        )
        for exp, trouves in classement
    )
    pitch, pitch_a_completer = _pitch(g, profile, offer, chez, couvertes, language)
    return PreparationContent(
        questions=questions,
        pitch=pitch,
        pitch_to_complete=pitch_a_completer,
        highlights=highlights,
        answers=_answers(g, questions, classement),
        recruiter_questions=_recruiter(g, couvertes),
        skills_matched=couvertes,
        skills_to_prepare=manquantes,
        warnings=tuple(warnings),
    )


def _questions(
    g: _Gabarits,
    offer: OfferFacts,
    chez: str,
    couvertes: tuple[str, ...],
    manquantes: tuple[str, ...],
) -> tuple[Question, ...]:
    questions: list[Question] = []
    for texte, raison in g.hr:
        questions.append(
            Question(
                id=f"hr-{len([q for q in questions if q.category is QuestionCategory.HR]) + 1}",
                category=QuestionCategory.HR,
                text=texte.format(title=offer.title, chez=chez, at=chez),
                rationale=raison,
            )
        )
    for texte, raison in g.behavioral:
        rang = len([q for q in questions if q.category is QuestionCategory.BEHAVIORAL]) + 1
        questions.append(
            Question(
                id=f"behavioral-{rang}",
                category=QuestionCategory.BEHAVIORAL,
                text=texte,
                rationale=raison,
            )
        )
    for rang, skill in enumerate(couvertes[:_MAX_SKILL_QUESTIONS], start=1):
        questions.append(
            Question(
                id=f"technical-{rang}",
                category=QuestionCategory.TECHNICAL,
                text=g.skill.format(skill=skill),
                rationale="Compétence demandée par l'offre et présente dans votre profil.",
                skill=skill,
            )
        )
    debut = len(couvertes[:_MAX_SKILL_QUESTIONS])
    for rang, skill in enumerate(manquantes[:_MAX_GAP_QUESTIONS], start=debut + 1):
        questions.append(
            Question(
                id=f"technical-{rang}",
                category=QuestionCategory.TECHNICAL,
                text=g.gap.format(skill=skill),
                rationale="Compétence demandée par l'offre mais absente de votre profil.",
                skill=skill,
                skill_gap=True,
            )
        )
    return tuple(questions)


def _pitch(
    g: _Gabarits,
    profile: ProfileDocument,
    offer: OfferFacts,
    chez: str,
    couvertes: tuple[str, ...],
    language: str,
) -> tuple[str, tuple[str, ...]]:
    identite = profile.identity
    nom = " ".join(p for p in (identite.first_name, identite.last_name) if p)
    phrases: list[str] = []
    a_completer: list[str] = []
    if nom:
        phrases.append(g.pitch_intro.format(name=nom))
    recente = profile.experiences[0] if profile.experiences else None
    if recente is not None and recente.title:
        societe = f" chez {recente.company}" if recente.company else ""
        if language.lower().startswith("en"):
            societe = f" at {recente.company}" if recente.company else ""
        depuis = ""
        if recente.is_current and recente.start:
            depuis = g.period_since.format(year=recente.start.year)
        phrases.append(
            g.pitch_now.format(
                title=recente.title, chez=societe, at=societe, since=depuis, depuis=depuis
            )
        )
    elif identite.headline:
        phrases.append(identite.headline.rstrip(".") + ".")
    if couvertes:
        phrases.append(g.pitch_skills.format(skills=", ".join(couvertes[:5])))
    phrases.append(g.pitch_fit.format(title=offer.title, chez=chez, at=chez))
    phrases.append(g.pitch_motivation)
    a_completer.append(g.pitch_motivation)
    return " ".join(phrases), tuple(a_completer)


def _answers(
    g: _Gabarits,
    questions: tuple[Question, ...],
    classement: list[tuple[ExperienceDoc, tuple[str, ...]]],
) -> tuple[AnswerOutline, ...]:
    """Trames STAR : comportementales et techniques, chacune adossée à une expérience réelle."""
    if not classement:
        return ()
    ciblees = [
        q
        for q in questions
        if q.category is QuestionCategory.BEHAVIORAL
        or (q.category is QuestionCategory.TECHNICAL and not q.skill_gap)
    ]
    trames: list[AnswerOutline] = []
    for rang, question in enumerate(ciblees):
        exp = _experience_pour(question, classement) or classement[rang % len(classement)][0]
        periode = _periode(exp)
        situation = _label(exp) + (f" ({periode})" if periode else "")
        actions = exp.achievements[:2] or ((exp.description,) if exp.description else ())
        manque = [g.to_complete_result]
        if not actions:
            manque.insert(0, "Vos actions concrètes dans ce poste.")
        trames.append(
            AnswerOutline(
                question_id=question.id,
                experience_label=_label(exp),
                situation=situation,
                actions=tuple(actions),
                result=None,
                to_complete=tuple(manque),
            )
        )
    return tuple(trames)


def _experience_pour(
    question: Question, classement: list[tuple[ExperienceDoc, tuple[str, ...]]]
) -> ExperienceDoc | None:
    """Pour une question technique, l'expérience qui mentionne réellement la compétence."""
    if question.skill is None:
        return None
    for exp, _ in classement:
        texte = " ".join([exp.title or "", exp.description or "", *exp.achievements])
        if mentions(texte, question.skill):
            return exp
    return None


def _recruiter(g: _Gabarits, couvertes: tuple[str, ...]) -> tuple[str, ...]:
    questions = list(g.recruiter)
    if couvertes:
        questions.insert(2, g.recruiter_skill.format(skill=couvertes[0]))
    return tuple(questions)
