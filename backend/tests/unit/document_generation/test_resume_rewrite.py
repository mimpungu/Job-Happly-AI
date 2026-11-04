"""Reformulation IA des réalisations du CV : garde-fou, service, adaptateur (TASK-012-08)."""

import json
import uuid
from collections.abc import Sequence
from typing import Any

import pytest

from app.modules.ai_management.domain.errors import AIDisabledError
from app.modules.ai_management.domain.models import ProviderKind
from app.modules.document_generation.application.ports import (
    RewriteOutcome,
    RewriterUnavailableError,
)
from app.modules.document_generation.domain.enums import RewriteMode
from app.modules.document_generation.domain.fact_checker import (
    UnverifiedFactError,
    assert_facts_verified,
)
from app.modules.document_generation.domain.models import ResumeGenerationOptions
from app.modules.document_generation.domain.resume_rewrite import (
    apply_rewrites,
    is_acceptable_rewrite,
    known_terms,
)
from app.modules.document_generation.infrastructure.ai_rewriter import GatewayResumeRewriter
from tests.unit.document_generation.test_resume_service import (
    DummyCompiler,
    FakeInputs,
    InMemoryRepository,
    InMemoryStorage,
    _profil_valide,
    _service,
)

ORIGINAL = "Migration de 12 services vers FastAPI"


class TestGardeFou:
    def test_reformulation_fidele_acceptee(self) -> None:
        assert is_acceptable_rewrite(
            ORIGINAL, "Migré 12 services vers FastAPI", allowed=known_terms(_profil_valide())
        )

    @pytest.mark.parametrize(
        "candidat",
        [
            "Migration de 40 services vers FastAPI",  # chiffre inventé
            "Migration de 12 services vers Kubernetes",  # techno inventée
            "Migration de 12 services vers FastAPI chez Google",  # entreprise inventée
            "Migration de 12 services vers FastAPI et AWS",  # sigle inventé
            "",
            ORIGINAL,  # identique : rien à faire
            "Migration de 12 services vers FastAPI " + "x" * 400,
            "Migration\nde 12 services vers FastAPI",
        ],
    )
    def test_ajout_de_fait_refuse(self, candidat: str) -> None:
        assert not is_acceptable_rewrite(ORIGINAL, candidat, allowed=known_terms(_profil_valide()))

    def test_competence_du_profil_autorisee(self) -> None:
        assert is_acceptable_rewrite(
            "Revue de code", "Revue de code Python", allowed=known_terms(_profil_valide())
        )

    def test_application_sur_le_profil_est_immuable(self) -> None:
        profil = _profil_valide()
        nouveau = apply_rewrites(profil, {"Revue de code": "Relecture de code"})

        assert nouveau.experiences[0].achievements == (
            "Migration vers FastAPI",
            "Relecture de code",
        )
        assert profil.experiences[0].achievements[1] == "Revue de code"


class TestControleDesFaits:
    def test_une_reformulation_declaree_est_admise(self) -> None:
        maitre = _profil_valide()
        genere = apply_rewrites(maitre, {"Revue de code": "Relecture de code"})

        assert_facts_verified(
            maitre, genere, allowed_rewrites={"Revue de code": "Relecture de code"}
        )

    def test_sans_declaration_une_reformulation_reste_une_invention(self) -> None:
        maitre = _profil_valide()
        genere = apply_rewrites(maitre, {"Revue de code": "Relecture de code"})

        with pytest.raises(UnverifiedFactError):
            assert_facts_verified(maitre, genere)

    def test_une_declaration_ne_couvre_pas_un_autre_texte(self) -> None:
        maitre = _profil_valide()
        genere = apply_rewrites(maitre, {"Revue de code": "Direction de 50 personnes"})

        with pytest.raises(UnverifiedFactError):
            assert_facts_verified(
                maitre, genere, allowed_rewrites={"Revue de code": "Relecture de code"}
            )


class FakeRewriter:
    def __init__(self, proposals: dict[str, str] | None = None, *, erreur: bool = False) -> None:
        self.proposals = proposals or {}
        self.erreur = erreur
        self.appels: list[tuple[Sequence[str], RewriteMode]] = []

    async def rewrite(
        self, *, owner_id: uuid.UUID, achievements: Sequence[str], language: str, mode: RewriteMode
    ) -> RewriteOutcome:
        self.appels.append((tuple(achievements), mode))
        if self.erreur:
            raise RewriterUnavailableError("Plafond atteint.")
        return RewriteOutcome(self.proposals, "fake", "petit", False)


def _service_avec(rewriter: FakeRewriter | None) -> Any:
    service = _service(
        DummyCompiler(), FakeInputs(_profil_valide()), InMemoryRepository(), InMemoryStorage()
    )
    service._rewriter = rewriter
    return service


async def _generer(service: Any, mode: RewriteMode) -> Any:
    _, version, _ = await service.generate_tailored_resume(
        owner_id=uuid.uuid4(), options=ResumeGenerationOptions(rewrite_mode=mode)
    )
    return version


class TestService:
    async def test_par_defaut_aucun_appel(self) -> None:
        rewriter = FakeRewriter({"Revue de code": "Relecture de code"})

        version = await _generer(_service_avec(rewriter), RewriteMode.NONE)

        assert rewriter.appels == []
        assert "ai_rewrite" not in version.ats_report["generation"]
        assert "Revue de code" in version.latex_source

    async def test_reformulation_appliquee_et_tracee(self) -> None:
        rewriter = FakeRewriter({"Revue de code": "Relecture de code"})

        version = await _generer(_service_avec(rewriter), RewriteMode.LOCAL)

        meta = version.ats_report["generation"]["ai_rewrite"]
        assert (meta["status"], meta["rewritten"], meta["rejected"]) == ("applied", 1, 0)
        assert meta["provider"] == "fake"
        assert "Relecture de code" in version.latex_source
        assert rewriter.appels[0][1] is RewriteMode.LOCAL

    async def test_proposition_inventee_ecartee_texte_d_origine_conserve(self) -> None:
        rewriter = FakeRewriter(
            {
                "Revue de code": "Revue de code de 300 projets",
                "Migration vers FastAPI": "Migration FastAPI",
            }
        )

        version = await _generer(_service_avec(rewriter), RewriteMode.AI)

        meta = version.ats_report["generation"]["ai_rewrite"]
        assert (meta["status"], meta["rewritten"], meta["rejected"]) == ("partial", 1, 1)
        assert "300" not in version.latex_source
        assert "Revue de code" in version.latex_source

    async def test_ia_indisponible_la_generation_continue_et_le_dit(self) -> None:
        version = await _generer(_service_avec(FakeRewriter(erreur=True)), RewriteMode.AI)

        meta = version.ats_report["generation"]["ai_rewrite"]
        assert meta["status"] == "unavailable"
        assert meta["reason"] == "Plafond atteint."
        assert "Revue de code" in version.latex_source

    async def test_sans_adaptateur_le_refus_est_explicite(self) -> None:
        version = await _generer(_service_avec(None), RewriteMode.AI)

        assert version.ats_report["generation"]["ai_rewrite"]["status"] == "unavailable"


class FakeGateway:
    def __init__(self, value: Any = None, *, erreur: Exception | None = None) -> None:
        self.value = value
        self.erreur = erreur
        self.requetes: list[Any] = []

    async def run(self, *, owner_id: uuid.UUID, request: Any, validate: Any) -> Any:
        self.requetes.append(request)
        if self.erreur:
            raise self.erreur
        from decimal import Decimal

        from app.modules.ai_management.application.gateway import AIResult

        return AIResult(validate(self.value), "p", "m", False, Decimal(0), 1, 1)


class TestAdaptateur:
    async def test_requete_marquee_donnees_personnelles_et_indexation(self) -> None:
        gateway = FakeGateway(
            {"rewrites": [{"index": 1, "text": "Relecture"}, {"index": 9, "text": "x"}]}
        )

        sortie = await GatewayResumeRewriter(gateway).rewrite(  # type: ignore[arg-type]
            owner_id=uuid.uuid4(), achievements=["A", "B"], language="fr", mode=RewriteMode.AI
        )

        requete = gateway.requetes[0]
        assert requete.contains_personal_data is True
        assert requete.allowed_kinds is None
        assert json.loads(requete.content)["achievements"] == {"0": "A", "1": "B"}
        assert sortie.proposals == {"B": "Relecture"}  # index hors bornes ignoré

    async def test_les_realisations_sont_regroupees_par_lots_bornes(self) -> None:
        gateway = FakeGateway({"rewrites": [{"index": 0, "text": "Reformulé"}]})
        realisations = [f"Réalisation {i}" for i in range(60)]

        sortie = await GatewayResumeRewriter(gateway).rewrite(  # type: ignore[arg-type]
            owner_id=uuid.uuid4(), achievements=realisations, language="fr", mode=RewriteMode.AI
        )

        # 60 réalisations : 3 requêtes (25 + 25 + 10), jamais une par réalisation.
        tailles = [len(json.loads(r.content)["achievements"]) for r in gateway.requetes]
        assert tailles == [25, 25, 10]
        # La sortie maximale de chaque lot reste dans la limite : jamais de réponse tronquée.
        assert all(r.max_output_tokens <= 4000 for r in gateway.requetes)
        # Les index sont locaux à chaque lot : l'index 0 désigne la première réalisation du lot.
        assert sortie.proposals == {
            "Réalisation 0": "Reformulé",
            "Réalisation 25": "Reformulé",
            "Réalisation 50": "Reformulé",
        }

    async def test_un_seul_appel_tant_que_le_lot_tient(self) -> None:
        gateway = FakeGateway({"rewrites": []})

        await GatewayResumeRewriter(gateway).rewrite(  # type: ignore[arg-type]
            owner_id=uuid.uuid4(),
            achievements=[f"R{i}" for i in range(25)],
            language="fr",
            mode=RewriteMode.AI,
        )

        assert len(gateway.requetes) == 1

    async def test_mode_local_restreint_aux_modeles_locaux(self) -> None:
        gateway = FakeGateway({"rewrites": []})

        await GatewayResumeRewriter(gateway).rewrite(  # type: ignore[arg-type]
            owner_id=uuid.uuid4(), achievements=["A"], language="fr", mode=RewriteMode.LOCAL
        )

        assert gateway.requetes[0].allowed_kinds == frozenset({ProviderKind.LOCAL})

    async def test_erreur_ia_devient_indisponibilite(self) -> None:
        gateway = FakeGateway(erreur=AIDisabledError("L'IA est désactivée."))

        with pytest.raises(RewriterUnavailableError, match="désactivée"):
            await GatewayResumeRewriter(gateway).rewrite(  # type: ignore[arg-type]
                owner_id=uuid.uuid4(), achievements=["A"], language="fr", mode=RewriteMode.AI
            )

    @pytest.mark.parametrize(
        "brut", [{}, {"rewrites": "x"}, {"rewrites": [{"index": "0", "text": "a"}]}]
    )
    async def test_sortie_mal_formee_refusee_par_la_validation(self, brut: Any) -> None:
        with pytest.raises(ValueError):
            await FakeGateway(brut).run(
                owner_id=uuid.uuid4(),
                request=None,
                validate=__import__(
                    "app.modules.document_generation.infrastructure.ai_rewriter",
                    fromlist=["_valider"],
                )._valider,
            )
