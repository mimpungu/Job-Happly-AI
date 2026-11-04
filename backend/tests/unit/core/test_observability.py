"""Logs structurés, masquage, corrélation, limites de débit et mesures (EPIC 018)."""

import json
import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.observability.context import request_id_var
from app.core.observability.logging import JsonFormatter
from app.core.observability.metrics import MetricsRegistry
from app.core.observability.middleware import ObservabilityMiddleware
from app.core.observability.rate_limit import SlidingWindowLimiter
from app.core.observability.redaction import redact


class TestMasquage:
    @pytest.mark.parametrize(
        "texte,interdit",
        [
            ("GET https://api.test/x?key=AIzaSyA1234567890abcdefghij&q=1", "AIzaSyA1234567890"),
            ("connexion postgresql://happly:s3cr3t@127.0.0.1/db", "s3cr3t"),
            ("Authorization: Bearer abcdef1234567890token", "abcdef1234567890token"),
            ("client_secret=topsecretvalue", "topsecretvalue"),
            ("password: hunter2", "hunter2"),
            ("contact camille.dubois@example.com", "camille.dubois@example.com"),
            ("clé sk-abcdefghijklmnopqrstuvwx", "sk-abcdefghijklmnopqrstuvwx"),
        ],
    )
    def test_secrets_et_donnees_personnelles_masques(self, texte: str, interdit: str) -> None:
        masque = redact(texte)

        assert interdit not in masque
        assert "***" in masque

    def test_texte_inoffensif_inchange(self) -> None:
        assert redact("Collecte terminée : 42 offres") == "Collecte terminée : 42 offres"


class TestJournalJson:
    def _ligne(self, **kw: object) -> dict[str, object]:
        enregistrement = logging.LogRecord(
            "happly.test", logging.INFO, __file__, 1, kw.pop("msg", "message"), None, None
        )
        for cle, valeur in kw.items():
            setattr(enregistrement, cle, valeur)
        return json.loads(JsonFormatter().format(enregistrement))  # type: ignore[no-any-return]

    def test_une_ligne_json_avec_les_champs_attendus(self) -> None:
        ligne = self._ligne(route="/api/v1/x", status=200)

        assert ligne["level"] == "INFO"
        assert ligne["logger"] == "happly.test"
        assert ligne["route"] == "/api/v1/x" and ligne["status"] == 200
        assert "ts" in ligne

    def test_le_message_et_les_champs_texte_sont_masques(self) -> None:
        ligne = self._ligne(msg="échec pour a@b.fr", detail="token=abcdef123456")

        assert "a@b.fr" not in json.dumps(ligne)
        assert "abcdef123456" not in json.dumps(ligne)

    def test_identifiant_de_correlation_inclus_quand_il_existe(self) -> None:
        jeton = request_id_var.set("req-123456789")
        try:
            assert self._ligne()["request_id"] == "req-123456789"
        finally:
            request_id_var.reset(jeton)
        assert "request_id" not in self._ligne()

    def test_exception_sans_pile_et_masquee(self) -> None:
        try:
            raise RuntimeError("clé AIzaSyA1234567890abcdefghij refusée")
        except RuntimeError:
            import sys

            enr = logging.LogRecord("x", logging.ERROR, __file__, 1, "boom", None, sys.exc_info())
        ligne = json.loads(JsonFormatter().format(enr))

        assert ligne["exception"].startswith("RuntimeError:")
        assert "AIzaSyA1234567890" not in ligne["exception"]
        assert "Traceback" not in json.dumps(ligne)


class TestLimiteur:
    def test_bloque_au_dela_de_la_limite_puis_libere(self) -> None:
        temps = [0.0]
        limiteur = SlidingWindowLimiter(2, 60, clock=lambda: temps[0])

        assert limiteur.check("a") == (True, 0)
        assert limiteur.check("a") == (True, 0)
        autorise, attente = limiteur.check("a")
        assert not autorise and 1 <= attente <= 61
        assert limiteur.check("b") == (True, 0)  # chaque client a sa propre fenêtre
        temps[0] = 61
        assert limiteur.check("a") == (True, 0)


class TestMesures:
    def test_percentiles_et_erreurs(self) -> None:
        registre = MetricsRegistry()
        for ms in range(1, 101):
            registre.record("/x", "GET", 200, float(ms))
        registre.record("/x", "GET", 500, 1.0)

        route = registre.snapshot()["routes"]["GET /x"]  # type: ignore[index]

        assert route["count"] == 101 and route["errors"] == 1
        assert route["p50_ms"] == 50.0 and route["p95_ms"] == 95.0

    def test_table_des_routes_bornee(self) -> None:
        registre = MetricsRegistry()
        for i in range(400):
            registre.record(f"/r{i}", "GET", 200, 1.0)

        assert len(registre.snapshot()["routes"]) <= 301  # type: ignore[arg-type]


def _app(
    *, limite: int = 100, couteuse: int = 100, corps_max: int = 1000
) -> tuple[TestClient, MetricsRegistry]:
    registre = MetricsRegistry()
    app = FastAPI()
    app.add_middleware(
        ObservabilityMiddleware,
        metrics=registre,
        limiter=SlidingWindowLimiter(limite),
        expensive_limiter=SlidingWindowLimiter(couteuse),
        max_body_bytes=corps_max,
    )

    @app.get("/api/v1/items/{item_id}")
    async def lire(item_id: str) -> dict[str, str]:
        return {"id": item_id}

    @app.post("/api/v1/ai/run")
    async def ia() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/api/v1/other")
    async def autre(payload: dict[str, object]) -> dict[str, bool]:
        return {"ok": True}

    return TestClient(app), registre


class TestMiddleware:
    def test_identifiant_genere_et_renvoye(self) -> None:
        client, _ = _app()

        reponse = client.get("/api/v1/items/1")

        assert len(reponse.headers["x-request-id"]) == 32

    def test_identifiant_valide_repris_invalide_remplace(self) -> None:
        client, _ = _app()

        repris = client.get("/api/v1/items/1", headers={"X-Request-ID": "abc-123456"})
        remplace = client.get("/api/v1/items/1", headers={"X-Request-ID": "x\ninjection"})

        assert repris.headers["x-request-id"] == "abc-123456"
        assert remplace.headers["x-request-id"] != "x\ninjection"

    def test_en_tetes_de_securite(self) -> None:
        client, _ = _app()

        h = client.get("/api/v1/items/1").headers

        assert h["x-content-type-options"] == "nosniff"
        assert h["x-frame-options"] == "DENY"
        assert h["referrer-policy"] == "no-referrer"
        assert "default-src 'none'" in h["content-security-policy"]
        assert h["cache-control"] == "no-store"

    def test_corps_trop_gros_refuse_en_413_normalise(self) -> None:
        client, _ = _app(corps_max=100)

        reponse = client.post("/api/v1/other", json={"x": "a" * 500})

        assert reponse.status_code == 413
        assert reponse.json()["error"]["code"] == "payload_too_large"
        assert reponse.headers["x-content-type-options"] == "nosniff"

    def test_limite_generale_429_avec_retry_after(self) -> None:
        client, registre = _app(limite=3)

        statuts = [client.get("/api/v1/items/1").status_code for _ in range(5)]

        assert statuts == [200, 200, 200, 429, 429]
        refus = client.get("/api/v1/items/1")
        assert refus.json()["error"]["code"] == "rate_limited"
        assert int(refus.headers["retry-after"]) >= 1
        assert registre.snapshot()["rate_limited"] == 3

    def test_limite_basse_sur_les_routes_couteuses_en_ecriture_seulement(self) -> None:
        client, _ = _app(couteuse=2)

        assert [client.post("/api/v1/ai/run").status_code for _ in range(3)] == [200, 200, 429]
        assert client.get("/api/v1/items/1").status_code == 200  # lecture non concernée

    def test_mesure_par_modele_de_route_sans_donnee_de_l_url(self) -> None:
        client, registre = _app()
        client.get("/api/v1/items/42?email=a@b.fr")
        client.get("/api/v1/items/43")

        routes: dict[str, dict[str, float]] = registre.snapshot()["routes"]  # type: ignore[assignment]

        assert list(routes) == ["GET /api/v1/items/{item_id}"]
        assert routes["GET /api/v1/items/{item_id}"]["count"] == 2

    def test_journal_d_acces_sans_query_ni_corps(self, caplog: pytest.LogCaptureFixture) -> None:
        client, _ = _app()
        with caplog.at_level(logging.INFO, logger="happly.http"):
            client.get("/api/v1/items/42?email=secret@b.fr")

        enregistrement = next(r for r in caplog.records if r.name == "happly.http")
        assert enregistrement.route == "/api/v1/items/{item_id}"  # type: ignore[attr-defined]
        assert enregistrement.status == 200  # type: ignore[attr-defined]
        assert "secret@b.fr" not in json.dumps(enregistrement.__dict__, default=str)
