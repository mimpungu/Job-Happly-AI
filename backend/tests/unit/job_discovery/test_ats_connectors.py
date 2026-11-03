import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.core.domain.value_objects import CountryCode, EmploymentType, RemoteType
from app.modules.job_discovery.domain.connector import (
    AccessDeniedError,
    HealthState,
    InvalidResponseError,
    JobSourceConnector,
    NotConfiguredError,
    SourceUnavailableError,
)
from app.modules.job_discovery.domain.criteria import SearchCriteria
from app.modules.job_discovery.infrastructure.ats.greenhouse import GreenhouseConnector
from app.modules.job_discovery.infrastructure.ats.lever import LeverConnector
from app.modules.job_discovery.infrastructure.http import create_http_client

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "ats"


def _charger(nom: str) -> Any:
    return json.loads((FIXTURES / nom).read_text(encoding="utf-8"))


def _client(reponses: dict[str, httpx.Response] | None = None, *, code: int | None = None):  # type: ignore[no-untyped-def]
    requetes: list[httpx.Request] = []

    def handler(requete: httpx.Request) -> httpx.Response:
        requetes.append(requete)
        if code is not None:
            return httpx.Response(code)
        return (reponses or {}).get(requete.url.path, httpx.Response(404))

    return create_http_client(transport=httpx.MockTransport(handler)), requetes


def _greenhouse(client: httpx.AsyncClient, token: str = "exemplesa") -> GreenhouseConnector:
    return GreenhouseConnector(board_token=token, company_name="Exemple SA", client=client)


def _lever(client: httpx.AsyncClient, token: str = "exemplesa") -> LeverConnector:
    return LeverConnector(company_token=token, company_name="Exemple SA", client=client)


class TestGreenhouse:
    async def _search(self, criteres: SearchCriteria):  # type: ignore[no-untyped-def]
        client, requetes = _client(
            {
                "/v1/boards/exemplesa/jobs": httpx.Response(
                    200, json=_charger("greenhouse_jobs.json")
                )
            }
        )
        async with client:
            return await _greenhouse(client).search(criteres), requetes

    def test_respecte_le_contrat_des_connecteurs(self) -> None:
        assert isinstance(_greenhouse(create_http_client()), JobSourceConnector)

    async def test_normalise_les_offres_et_filtre_par_intitule(self) -> None:
        page, requetes = await self._search(SearchCriteria(title="Data Analyst"))

        assert [o.external_id for o in page.offers] == ["4001", "4003"]
        assert requetes[0].url.params["content"] == "true"
        offre = page.offers[0].offer
        assert offre.title == "Data Analyst"
        assert offre.company_name == "Exemple SA"
        assert offre.location == "Paris, France"
        assert offre.language == "fr"
        assert offre.application_url.startswith("https://job-boards.greenhouse.io/")
        assert page.total == 2

    async def test_la_description_est_du_texte_sans_script(self) -> None:
        page, _ = await self._search(SearchCriteria(title="Data Analyst"))
        description = page.offers[0].offer.description

        assert "SQL" in description
        assert "Qualité des données" in description
        assert "alert" not in description
        assert "<" not in description

    async def test_ne_fabrique_pas_de_date_de_publication(self) -> None:
        page, _ = await self._search(SearchCriteria(title="Data Analyst"))

        assert page.offers[0].offer.published_at is None  # `updated_at` n'est pas une publication
        assert page.offers[0].raw_payload["updated_at"] == "2026-10-30T09:00:00-04:00"

    async def test_conserve_la_donnee_brute_et_une_empreinte_stable(self) -> None:
        a, _ = await self._search(SearchCriteria(title="Data Analyst"))
        b, _ = await self._search(SearchCriteria(title="Data Analyst"))

        assert a.offers[0].raw_payload["id"] == 4001
        assert a.offers[0].offer.content_hash == b.offers[0].offer.content_hash
        assert a.offers[0].offer.content_hash != a.offers[1].offer.content_hash

    async def test_pagine_avec_un_curseur(self) -> None:
        premiere, _ = await self._search(SearchCriteria(keywords=("data",), page_size=1))
        assert len(premiere.offers) == 1
        assert premiere.next_cursor == "1"

        seconde, _ = await self._search(
            SearchCriteria(keywords=("data",), page_size=1, cursor=premiere.next_cursor)
        )
        assert [o.external_id for o in seconde.offers] != [o.external_id for o in premiere.offers]

    async def test_detail_d_une_offre_et_offre_disparue(self) -> None:
        un_job = _charger("greenhouse_jobs.json")["jobs"][0]
        client, _ = _client({"/v1/boards/exemplesa/jobs/4001": httpx.Response(200, json=un_job)})
        async with client:
            connecteur = _greenhouse(client)
            assert (await connecteur.get_details("4001")).external_id == "4001"  # type: ignore[union-attr]
            assert await connecteur.get_details("9999") is None

    async def test_refuse_un_identifiant_non_numerique(self) -> None:
        client, requetes = _client()
        async with client:
            with pytest.raises(InvalidResponseError):
                await _greenhouse(client).get_details("../admin")
        assert requetes == []

    @pytest.mark.parametrize("token", ["", "a/b", "../x", "a b", "x?y=1", "a" * 101, "-debut"])
    def test_refuse_un_jeton_dangereux(self, token: str) -> None:
        with pytest.raises(NotConfiguredError):
            _greenhouse(create_http_client(), token)

    @pytest.mark.parametrize(
        ("code", "erreur"),
        [(404, NotConfiguredError), (403, AccessDeniedError), (503, SourceUnavailableError)],
    )
    async def test_traduit_les_erreurs_http(self, code: int, erreur: type[Exception]) -> None:
        client, _ = _client(code=code)
        async with client:
            with pytest.raises(erreur):
                await _greenhouse(client).search(SearchCriteria(title="Data"))

    async def test_structure_modifiee_est_signalee(self) -> None:
        client, _ = _client({"/v1/boards/exemplesa/jobs": httpx.Response(200, json={"autre": []})})
        async with client:
            with pytest.raises(InvalidResponseError):
                await _greenhouse(client).search(SearchCriteria(title="Data"))

    async def test_offre_sans_titre_est_rejetee_plutot_que_inventee(self) -> None:
        jobs = {"jobs": [{"id": 1, "absolute_url": "https://x.test/1"}]}
        client, _ = _client({"/v1/boards/exemplesa/jobs": httpx.Response(200, json=jobs)})
        async with client:
            with pytest.raises(InvalidResponseError):
                await _greenhouse(client).search(SearchCriteria(title="Data"))

    async def test_sante(self) -> None:
        client, _ = _client({"/v1/boards/exemplesa/jobs": httpx.Response(200, json={"jobs": []})})
        async with client:
            assert (await _greenhouse(client).health_check()).state is HealthState.OK


class TestLever:
    async def _search(self, criteres: SearchCriteria):  # type: ignore[no-untyped-def]
        client, requetes = _client(
            {"/v0/postings/exemplesa": httpx.Response(200, json=_charger("lever_postings.json"))}
        )
        async with client:
            return await _lever(client).search(criteres), requetes

    async def test_normalise_pays_teletravail_salaire_et_date(self) -> None:
        page, requetes = await self._search(SearchCriteria(title="Data Analyst"))

        assert requetes[0].url.params["mode"] == "json"
        offre = page.offers[0].offer
        assert offre.country_code == CountryCode("CA")
        assert offre.remote_type is RemoteType.HYBRID
        assert str(offre.salary_min) == "60000"
        assert str(offre.salary_max) == "80000"
        assert offre.salary_currency == "CAD"
        assert offre.published_at is not None
        assert offre.application_url.endswith("/apply")
        assert offre.canonical_url is not None
        assert "Construire des rapports" in offre.description

    async def test_un_libelle_de_contrat_ambigu_reste_inconnu(self) -> None:
        page, _ = await self._search(SearchCriteria(title="Data"))
        data_analyst, stagiaire = page.offers

        assert data_analyst.offer.employment_type is None  # « Full-time » ne dit pas CDI/CDD
        assert stagiaire.offer.employment_type is EmploymentType.INTERNSHIP

    async def test_un_salaire_horaire_ou_un_pays_invalide_ne_sont_pas_retenus(self) -> None:
        page, _ = await self._search(SearchCriteria(title="Data"))
        stagiaire = page.offers[1].offer

        assert stagiaire.salary_min is None
        assert stagiaire.salary_currency is None
        assert stagiaire.country_code is None
        assert stagiaire.published_at is None  # absent de la source : pas de date inventée

    async def test_repli_sur_l_url_publique_sans_applyurl(self) -> None:
        page, _ = await self._search(SearchCriteria(title="Stagiaire"))

        assert page.offers[0].offer.application_url == page.offers[0].offer.canonical_url

    async def test_filtre_par_mots_cles(self) -> None:
        page, _ = await self._search(SearchCriteria(keywords=("sql",)))

        assert [o.external_id for o in page.offers] == ["aaaaaaaa-0000-0000-0000-000000000001"]

    async def test_instance_europeenne(self) -> None:
        client, requetes = _client({"/v0/postings/exemplesa": httpx.Response(200, json=[])})
        async with client:
            connecteur = LeverConnector(
                company_token="exemplesa", company_name="Exemple SA", client=client, region="eu"
            )
            await connecteur.search(SearchCriteria(title="Data"))

        assert requetes[0].url.host == "api.eu.lever.co"

    async def test_structure_modifiee_est_signalee(self) -> None:
        client, _ = _client({"/v0/postings/exemplesa": httpx.Response(200, json={"erreur": "x"})})
        async with client:
            with pytest.raises(InvalidResponseError):
                await _lever(client).search(SearchCriteria(title="Data"))

    async def test_detail_et_offre_disparue(self) -> None:
        offre = _charger("lever_postings.json")[0]
        chemin = f"/v0/postings/exemplesa/{offre['id']}"
        client, _ = _client({chemin: httpx.Response(200, json=offre)})
        async with client:
            connecteur = _lever(client)
            assert (await connecteur.get_details(offre["id"])) is not None
            assert await connecteur.get_details("bbbbbbbb-0000") is None
            with pytest.raises(InvalidResponseError):
                await connecteur.get_details("../x")

    @pytest.mark.parametrize("token", ["", "a/b", "..", "x y", "x%2f"])
    def test_refuse_un_jeton_dangereux(self, token: str) -> None:
        with pytest.raises(NotConfiguredError):
            _lever(create_http_client(), token)
