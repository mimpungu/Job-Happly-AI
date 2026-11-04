"""Correcteur orthographique des lettres (TASK-013-18)."""

from collections.abc import Collection
from typing import ClassVar

from app.modules.document_generation.domain.cover_letter_audit import audit_letter_text
from app.modules.document_generation.domain.spelling import find_spelling_issues
from app.modules.document_generation.infrastructure.spell_checker import PySpellChecker
from tests.unit.document_generation.cover_letter_samples import contexte_offre, profil_alice


class FakeChecker:
    """Dictionnaire minimal : tout mot hors de la liste est « inconnu »."""

    CONNUS: ClassVar[set[str]] = {"bonjour", "equipe", "recrutement", "pour", "votre"}

    def unknown(self, words: Collection[str], language: str) -> set[str]:
        return {w for w in words if w not in self.CONNUS}

    def suggestion(self, word: str, language: str) -> str | None:
        return "recrutement" if word == "recrutemnt" else None


def test_sans_correcteur_aucun_signalement() -> None:
    assert find_spelling_issues("recrutemnt", "fr", None) == []


def test_faute_signalee_avec_suggestion() -> None:
    issues = find_spelling_issues("bonjour pour votre recrutemnt", "fr", FakeChecker())

    assert issues == [
        "Orthographe à vérifier : « recrutemnt » (vous vouliez peut-être « recrutement »)"
    ]


def test_noms_propres_sigles_chiffres_et_mots_courts_ignores() -> None:
    texte = "bonjour Acme NASA 2024 ok pour Zorglub"
    assert find_spelling_issues(texte, "fr", FakeChecker()) == []


def test_termes_du_profil_ignores() -> None:
    assert find_spelling_issues("bonjour kubernetes", "fr", FakeChecker()) != []
    assert (
        find_spelling_issues("bonjour kubernetes", "fr", FakeChecker(), ignore=["Kubernetes"]) == []
    )


def test_pas_de_doublon_et_borne() -> None:
    texte = "zzzaa " * 3 + " ".join(f"mot{chr(97 + i)}xx" for i in range(20))
    issues = find_spelling_issues(texte, "fr", FakeChecker())

    assert len(issues) == 10
    assert sum("zzzaa" in i for i in issues) == 1


class TestDictionnaireReel:
    """Fumée avec le vrai dictionnaire embarqué (hors ligne)."""

    def test_francais_correct_et_faute(self) -> None:
        texte = (
            "Je vous écris pour ma candidature au poste de développeur, avec l'équipe recrutemnt."
        )
        issues = find_spelling_issues(texte, "fr", PySpellChecker())

        assert len(issues) == 1
        assert "recrutemnt" in issues[0]
        assert "recrutement" in issues[0]

    def test_langue_sans_dictionnaire_non_verifiee(self) -> None:
        assert find_spelling_issues("zzzaaa bbbccc", "sv", PySpellChecker()) == []

    def test_variante_regionale_utilise_la_langue_de_base(self) -> None:
        assert find_spelling_issues("recrutemnt", "fr-CA", PySpellChecker()) != []


def test_audit_integre_les_fautes_sans_bloquer() -> None:
    texte = "Bonjour, ma candidature pour votre recrutemnt. Cordialement."
    audit = audit_letter_text(
        texte,
        language="fr",
        profile=profil_alice(),
        context=contexte_offre(),
        today=__import__("datetime").date(2026, 11, 4),
        page_count=1,
        spelling=PySpellChecker(),
    )

    assert any("recrutemnt" in s for s in audit.spelling_issues)
    assert any("recrutemnt" in i for i in audit.issues)
