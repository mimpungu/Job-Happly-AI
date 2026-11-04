"""Découverte d'un job board à partir du nom d'une entreprise (réseau simulé)."""

from collections.abc import Callable

import httpx
import pytest

from app.modules.job_discovery.domain.target_company import AtsKind
from app.modules.job_discovery.infrastructure.ats.discovery import (
    discover_boards,
    slug_candidates,
)
from app.modules.job_discovery.infrastructure.http import create_http_client


@pytest.mark.parametrize(
    ("nom", "attendu"),
    [
        ("Stripe", ["stripe"]),
        ("Acme Inc.", ["acme"]),
        ("Société Générale", ["societegenerale", "societe-generale"]),
        ("  Data  Dog  ", ["datadog", "data-dog"]),
        ("!!!", []),
    ],
)
def test_candidats_de_jeton(nom: str, attendu: list[str]) -> None:
    assert slug_candidates(nom) == attendu


def test_une_forme_juridique_seule_reste_un_candidat() -> None:
    assert slug_candidates("SA") == ["sa"]


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return create_http_client(transport=httpx.MockTransport(handler))


async def test_trouve_un_board_greenhouse_et_un_board_lever() -> None:
    def handler(requete: httpx.Request) -> httpx.Response:
        chemin = requete.url.path
        if requete.url.host == "boards-api.greenhouse.io" and chemin == "/v1/boards/acme":
            return httpx.Response(200, json={"name": "Acme Corp"})
        if requete.url.host == "boards-api.greenhouse.io" and chemin == "/v1/boards/acme/jobs":
            return httpx.Response(200, json={"jobs": [{"id": 1}, {"id": 2}]})
        if requete.url.host == "api.lever.co" and chemin == "/v0/postings/acme":
            return httpx.Response(200, json=[{"id": "a"}])
        return httpx.Response(404, json={"ok": False})

    async with _client(handler) as client:
        boards = await discover_boards("Acme", client)

    assert [(b.ats_kind, b.token, b.offer_count) for b in boards] == [
        (AtsKind.GREENHOUSE, "acme", 2),
        (AtsKind.LEVER, "acme", 1),
    ]
    assert boards[0].board_name == "Acme Corp"
    assert boards[0].careers_url == "https://boards.greenhouse.io/acme"


async def test_aucun_board_donne_une_liste_vide() -> None:
    async with _client(lambda _: httpx.Response(404)) as client:
        assert await discover_boards("Inconnue", client) == []


async def test_une_source_en_panne_est_ignoree_sans_masquer_les_autres() -> None:
    def handler(requete: httpx.Request) -> httpx.Response:
        if requete.url.host == "boards-api.greenhouse.io":
            return httpx.Response(503)
        if requete.url.host == "api.lever.co":
            return httpx.Response(200, json=[])
        return httpx.Response(404)

    async with _client(handler) as client:
        boards = await discover_boards("Acme", client)

    assert [(b.ats_kind, b.offer_count) for b in boards] == [(AtsKind.LEVER, 0)]


async def test_refuse_une_structure_inattendue() -> None:
    async with _client(lambda _: httpx.Response(200, json={"surprise": True})) as client:
        assert await discover_boards("Acme", client) == []


async def test_trouve_un_board_ashby_et_un_compte_workable() -> None:
    def handler(requete: httpx.Request) -> httpx.Response:
        chemin = requete.url.path
        if requete.url.host == "api.ashbyhq.com" and chemin == "/posting-api/job-board/acme":
            jobs = [{"id": "a"}, {"id": "b", "isListed": False}]
            return httpx.Response(200, json={"apiVersion": "1", "jobs": jobs})
        if requete.url.host == "apply.workable.com" and chemin == "/api/v1/widget/accounts/acme":
            return httpx.Response(200, json={"name": "Acme Corp", "jobs": [{}, {}, {}]})
        return httpx.Response(404)

    async with _client(handler) as client:
        boards = await discover_boards("Acme", client)

    assert [(b.ats_kind, b.token, b.offer_count, b.board_name) for b in boards] == [
        (AtsKind.ASHBY, "acme", 1, None),  # l'offre non listée n'est pas comptée
        (AtsKind.WORKABLE, "acme", 3, "Acme Corp"),
    ]
    assert boards[0].careers_url == "https://jobs.ashbyhq.com/acme"
    assert boards[1].careers_url == "https://apply.workable.com/acme"
