"""Adaptateurs Gemini et Ollama : réponses fictives, aucun réseau, aucune vraie clé."""

import json
from decimal import Decimal

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.modules.ai_management.application.providers import build_providers
from app.modules.ai_management.domain.errors import ProviderFailureError
from app.modules.ai_management.domain.models import FinishReason, ProviderKind
from app.modules.ai_management.infrastructure.gemini import GeminiProvider
from app.modules.ai_management.infrastructure.ollama import NUM_CTX, OllamaProvider
from tests.unit.ai_management.fakes import requete

CLE = "cle-de-test-ne-doit-jamais-fuiter"


def _gemini(handler, *, tier: str = "free", cle: str | None = CLE) -> GeminiProvider:  # type: ignore[no-untyped-def]
    return GeminiProvider(
        api_key=SecretStr(cle) if cle else None,
        tier=tier,
        model_level1="gemini-3.1-flash-lite",
        model_level2="gemini-3-flash-preview",
        transport=httpx.MockTransport(handler),
    )


def _reponse_gemini(texte: str = '{"ok": true}', fin: str = "STOP") -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "candidates": [{"content": {"parts": [{"text": texte}]}, "finishReason": fin}],
            "usageMetadata": {
                "promptTokenCount": 120,
                "candidatesTokenCount": 30,
                "thoughtsTokenCount": 10,
            },
        },
    )


class TestGemini:
    async def test_envoie_la_cle_en_en_tete_et_jamais_dans_l_url(self) -> None:
        vues: list[httpx.Request] = []

        def handler(r: httpx.Request) -> httpx.Response:
            vues.append(r)
            return _reponse_gemini()

        await _gemini(handler).generate(requete(), "gemini-3.1-flash-lite")

        envoyee = vues[0]
        assert envoyee.headers["x-goog-api-key"] == CLE
        assert CLE not in str(envoyee.url)
        assert str(envoyee.url).endswith("/models/gemini-3.1-flash-lite:generateContent")
        corps = json.loads(envoyee.content)
        assert corps["generationConfig"]["responseMimeType"] == "application/json"
        assert corps["generationConfig"]["maxOutputTokens"] == 300
        # Sans cela, ces modèles dépensent tout le budget de tokens en réflexion (constaté en réel).
        assert corps["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "minimal"}
        # Instructions et donnée sont séparées ; la donnée est marquée comme telle.
        assert "Résume l'offre" in corps["systemInstruction"]["parts"][0]["text"]
        assert "DONNÉE" in corps["contents"][0]["parts"][0]["text"]

    async def test_les_tokens_de_reflexion_sont_comptes_comme_de_la_sortie(self) -> None:
        resultat = await _gemini(lambda r: _reponse_gemini()).generate(
            requete(), "gemini-3.1-flash-lite"
        )

        assert (resultat.input_tokens, resultat.output_tokens) == (120, 40)
        assert resultat.finish is FinishReason.COMPLETE

    async def test_reponse_coupee_est_signalee(self) -> None:
        resultat = await _gemini(lambda r: _reponse_gemini("{", "MAX_TOKENS")).generate(
            requete(), "gemini-3.1-flash-lite"
        )

        assert resultat.finish is FinishReason.TRUNCATED

    @pytest.mark.parametrize(
        ("statut", "fragment"),
        [(401, "clé"), (403, "clé"), (429, "Quota"), (503, "indisponible"), (400, "refusé")],
    )
    async def test_erreurs_traduites_sans_relayer_le_corps_ni_la_cle(
        self, statut: int, fragment: str
    ) -> None:
        provider = _gemini(lambda r: httpx.Response(statut, text=f"détail {CLE}"))

        with pytest.raises(ProviderFailureError) as info:
            await provider.generate(requete(), "gemini-3.1-flash-lite")

        assert fragment in str(info.value) and CLE not in str(info.value)

    async def test_reponse_hors_contrat_ou_sans_texte(self) -> None:
        with pytest.raises(ProviderFailureError, match="illisible"):
            await _gemini(lambda r: httpx.Response(200, json={"surprise": 1})).generate(
                requete(), "gemini-3.1-flash-lite"
            )
        vide = httpx.Response(
            200,
            json={
                "candidates": [{"finishReason": "SAFETY"}],
                "usageMetadata": {"promptTokenCount": 5},
            },
        )
        with pytest.raises(ProviderFailureError, match="aucun texte"):
            await _gemini(lambda r: vide).generate(requete(), "gemini-3.1-flash-lite")

    async def test_sans_cle_aucune_requete_n_est_envoyee(self) -> None:
        vues: list[httpx.Request] = []

        def handler(r: httpx.Request) -> httpx.Response:
            vues.append(r)
            return _reponse_gemini()

        provider = _gemini(handler, cle=None)

        assert not provider.supports(requete())
        with pytest.raises(ProviderFailureError, match="HAPPLY_GEMINI_API_KEY"):
            await provider.generate(requete(), "gemini-3.1-flash-lite")
        assert vues == []

    def test_palier_gratuit_cout_nul_et_contenus_reutilisables(self) -> None:
        gratuit = _gemini(lambda r: _reponse_gemini(), tier="free")

        assert gratuit.uses_data_for_training is True
        assert gratuit.kind is ProviderKind.API
        assert all(t.input_per_million == 0 for t in gratuit.pricing.values())

    def test_palier_payant_tarifs_publies_en_dollars(self) -> None:
        payant = _gemini(lambda r: _reponse_gemini(), tier="paid")

        tarif = payant.pricing["gemini-3.1-flash-lite"]
        assert payant.uses_data_for_training is False
        assert (tarif.input_per_million, tarif.output_per_million, tarif.currency) == (
            Decimal("0.25"),
            Decimal("1.50"),
            "USD",
        )

    def test_le_modele_retire_aux_nouveaux_comptes_n_a_plus_de_tarif(self) -> None:
        # Régression : gemini-2.5-flash-lite répond 404 « no longer available to new users ».
        provider = GeminiProvider(
            api_key=SecretStr(CLE),
            tier="paid",
            model_level1="gemini-2.5-flash-lite",
            model_level2="gemini-3-flash-preview",
        )

        assert "gemini-2.5-flash-lite" not in provider.pricing

    def test_un_modele_sans_tarif_connu_n_est_pas_facture_a_un_prix_invente(self) -> None:
        provider = GeminiProvider(
            api_key=SecretStr(CLE),
            tier="paid",
            model_level1="modele-inconnu",
            model_level2="gemini-3-flash-preview",
        )

        assert "modele-inconnu" not in provider.pricing  # le routage l'écarte


class TestOllama:
    def _provider(self, handler) -> OllamaProvider:  # type: ignore[no-untyped-def]
        return OllamaProvider(
            base_url="http://127.0.0.1:11434",
            model_level1="gemma4:e4b",
            model_level2="gemma4:12b",
            transport=httpx.MockTransport(handler),
        )

    async def test_appelle_le_chat_local_avec_schema_et_contexte(self) -> None:
        vues: list[httpx.Request] = []

        def handler(r: httpx.Request) -> httpx.Response:
            vues.append(r)
            return httpx.Response(
                200,
                json={
                    "message": {"content": '{"ok": true}'},
                    "done_reason": "stop",
                    "prompt_eval_count": 90,
                    "eval_count": 20,
                },
            )

        resultat = await self._provider(handler).generate(requete(), "gemma4:e4b")

        corps = json.loads(vues[0].content)
        assert vues[0].url.host == "127.0.0.1" and vues[0].url.path == "/api/chat"
        assert "format" not in corps  # 501 sur ce runtime : le schéma est dans la consigne
        assert corps["think"] is False
        assert '{"type": "object"}' in corps["messages"][0]["content"]
        assert corps["options"]["num_ctx"] == NUM_CTX
        assert corps["options"]["temperature"] == 0 and corps["stream"] is False
        assert (resultat.input_tokens, resultat.output_tokens) == (90, 20)

    async def test_retire_les_balises_markdown_autour_du_json(self) -> None:
        entoure = httpx.Response(
            200, json={"message": {"content": '```json\n{"ok": true}\n```'}, "done_reason": "stop"}
        )

        resultat = await self._provider(lambda r: entoure).generate(requete(), "gemma4:e4b")

        assert json.loads(resultat.text) == {"ok": True}

    async def test_modele_absent_donne_la_commande_pour_l_installer(self) -> None:
        provider = self._provider(lambda r: httpx.Response(404, json={"error": "not found"}))

        with pytest.raises(ProviderFailureError, match="ollama pull gemma4:12b"):
            await provider.generate(requete(), "gemma4:12b")

    async def test_ollama_eteint_est_une_erreur_explicite(self) -> None:
        def handler(r: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("refused")

        with pytest.raises(ProviderFailureError, match="ollama serve"):
            await self._provider(handler).generate(requete(), "gemma4:e4b")

    async def test_reponse_coupee_par_la_limite_de_tokens(self) -> None:
        provider = self._provider(
            lambda r: httpx.Response(
                200, json={"message": {"content": "{"}, "done_reason": "length"}
            )
        )

        assert (await provider.generate(requete(), "gemma4:e4b")).finish is FinishReason.TRUNCATED

    def test_gratuit_local_et_refuse_ce_qui_depasse_la_fenetre_de_contexte(self) -> None:
        provider = self._provider(lambda r: httpx.Response(200))

        assert provider.kind is ProviderKind.LOCAL and not provider.uses_data_for_training
        assert provider.pricing["gemma4:e4b"].input_per_million == 0
        assert provider.supports(requete())
        assert not provider.supports(requete("é" * 40_000))  # tronqué en silence sinon


class TestConfiguration:
    def test_aucun_fournisseur_sans_cle_ni_ollama(self) -> None:
        assert build_providers(Settings(_env_file=None)) == []

    def test_fournisseurs_selon_la_configuration(self) -> None:
        reglages = Settings(_env_file=None, gemini_api_key=SecretStr(CLE), ollama_enabled=True)

        noms = [p.name for p in build_providers(reglages)]

        assert noms == ["ollama", "gemini"]  # le local d'abord

    def test_un_ollama_distant_est_refuse(self) -> None:
        with pytest.raises(ValueError, match="boucle locale"):
            Settings(_env_file=None, ollama_url="http://192.168.1.20:11434")

    def test_la_cle_n_apparait_pas_dans_la_representation(self) -> None:
        reglages = Settings(_env_file=None, gemini_api_key=SecretStr(CLE))

        assert CLE not in repr(reglages) and CLE not in str(reglages)


class TestVariablesVides:
    def test_une_variable_vide_vaut_non_configure(self) -> None:
        reglages = Settings(_env_file=None, gemini_api_key="  ")

        assert reglages.gemini_api_key is None
        assert build_providers(reglages) == []

    def test_l_hote_docker_est_accepte_pour_ollama(self) -> None:
        reglages = Settings(_env_file=None, ollama_url="http://host.docker.internal:11434")

        assert reglages.ollama_url.endswith(":11434")
