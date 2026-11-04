"""Connecteur France Travail : réponses fictives, aucun appel réseau, aucun vrai identifiant."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from app.core.domain.value_objects import EmploymentType
from app.modules.job_discovery.domain.connector import (
    AuthenticationFailedError,
    InvalidResponseError,
    NotConfiguredError,
    SourceUnavailableError,
)
from app.modules.job_discovery.domain.criteria import SearchCriteria
from app.modules.job_discovery.infrastructure.france_travail import FranceTravailConnector
from app.modules.job_discovery.infrastructure.http import create_http_client

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "ats" / "france_travail_search.json"
SECRET = "secret-de-test-ne-doit-jamais-fuiter"


class Serveur:
    """Faux serveur France Travail : jeton OAuth2 puis recherche."""

    def __init__(self, *, recherche: httpx.Response | None = None, jeton_status: int = 200) -> None:
        self.requetes: list[httpx.Request] = []
        self.recherche = recherche or httpx.Response(
            200,
            json=json.loads(FIXTURE.read_text(encoding="utf-8")),
            headers={"Content-Range": "offres 0-1/2"},
        )
        self.jeton_status = jeton_status
        self.jetons_emis = 0

    def __call__(self, requete: httpx.Request) -> httpx.Response:
        self.requetes.append(requete)
        if requete.url.path.endswith("/access_token"):
            self.jetons_emis += 1
            if self.jeton_status != 200:
                return httpx.Response(self.jeton_status, text=f"erreur {SECRET}")
            return httpx.Response(200, json={"access_token": "jeton-1", "expires_in": 1499})
        return self.recherche


def _connecteur(
    serveur: Serveur,
    *,
    identifiants: bool = True,
    department: str | None = None,
    horloge: Callable[[], float] | None = None,
) -> FranceTravailConnector:
    kwargs: dict[str, Any] = {} if horloge is None else {"clock": horloge}
    return FranceTravailConnector(
        client=create_http_client(transport=httpx.MockTransport(serveur)),
        client_id=SecretStr("id-test") if identifiants else None,
        client_secret=SecretStr(SECRET) if identifiants else None,
        department=department,
        **kwargs,
    )


async def test_sans_identifiants_la_source_est_non_configuree() -> None:
    serveur = Serveur()
    connecteur = _connecteur(serveur, identifiants=False)
    with pytest.raises(NotConfiguredError, match="HAPPLY_FRANCE_TRAVAIL_CLIENT_ID"):
        await connecteur.search(SearchCriteria(keywords=("x",)))
    assert serveur.requetes == []  # aucun appel réseau sans identifiants


async def test_recherche_normalise_les_offres_et_n_invente_rien() -> None:
    serveur = Serveur()
    connecteur = _connecteur(serveur)

    page = await connecteur.search(SearchCriteria(whole_catalogue=True))

    assert page.total == 2
    premiere = page.offers[0]
    assert premiere.external_id == "190ABCD"
    offre = premiere.offer
    assert offre.title == "Développeur Python H/F"
    assert offre.company_name == "Exemple Banque"
    assert offre.location == "75 - PARIS 09"
    assert offre.country_code is not None and offre.country_code.value == "FR"
    assert offre.employment_type is EmploymentType.PERMANENT
    assert offre.salary_min is None and offre.salary_max is None  # texte libre non interprété
    assert offre.language == "fr"
    sans_entreprise = page.offers[1].offer
    assert sans_entreprise.company_name is None  # absent plutôt qu'inventé
    assert sans_entreprise.employment_type is EmploymentType.TEMPORARY
    assert page.offers[1].offer.application_url == "https://partenaire.example/offre/190EFGH"


async def test_envoie_le_jeton_les_mots_cles_et_le_departement() -> None:
    serveur = Serveur()
    connecteur = _connecteur(serveur, department="75")

    await connecteur.search(SearchCriteria(title="Développeur", company="Exemple Banque"))

    jeton, recherche = serveur.requetes
    assert jeton.method == "POST"
    corps = jeton.content.decode()
    assert "grant_type=client_credentials" in corps and "scope=api_offresdemploiv2" in corps
    assert recherche.headers["Authorization"] == "Bearer jeton-1"
    assert recherche.url.params["motsCles"] == "Développeur Exemple Banque"
    assert recherche.url.params["departement"] == "75"
    assert recherche.url.params["range"] == "0-49"


async def test_le_jeton_est_reutilise_puis_renouvele_a_l_expiration() -> None:
    serveur = Serveur()
    temps = [0.0]
    connecteur = _connecteur(serveur, horloge=lambda: temps[0])
    criteres = SearchCriteria(keywords=("python",))

    await connecteur.search(criteres)
    await connecteur.search(criteres)
    assert serveur.jetons_emis == 1

    temps[0] = 1500.0  # au-delà de expires_in - marge
    await connecteur.search(criteres)
    assert serveur.jetons_emis == 2


async def test_aucun_resultat_204_donne_une_page_vide() -> None:
    connecteur = _connecteur(Serveur(recherche=httpx.Response(204)))

    page = await connecteur.search(SearchCriteria(keywords=("introuvable",)))

    assert page.offers == () and page.total == 0 and page.next_cursor is None


async def test_pagination_par_plage_et_curseur() -> None:
    plein = httpx.Response(
        200,
        json={"resultats": json.loads(FIXTURE.read_text(encoding="utf-8"))["resultats"]},
        headers={"Content-Range": "offres 0-1/5"},
    )
    serveur = Serveur(recherche=plein)
    connecteur = _connecteur(serveur)

    page = await connecteur.search(SearchCriteria(keywords=("python",), page_size=2))

    assert page.next_cursor == "2"
    suivante = await connecteur.search(
        SearchCriteria(keywords=("python",), page_size=2, cursor=page.next_cursor)
    )
    assert serveur.requetes[-1].url.params["range"] == "2-3"
    assert suivante.next_cursor == "4"


async def test_la_pagination_s_arrete_a_la_limite_de_la_source() -> None:
    connecteur = _connecteur(Serveur())

    page = await connecteur.search(SearchCriteria(keywords=("a",), cursor="1150"))

    assert page.offers == ()


async def test_filtre_local_sur_la_ville() -> None:
    page = await _connecteur(Serveur()).search(SearchCriteria(keywords=("python",), city="Paris"))

    assert [o.external_id for o in page.offers] == ["190ABCD"]


@pytest.mark.parametrize("statut", [400, 401, 403])
async def test_identifiants_refuses_sans_fuite_du_secret(statut: int) -> None:
    connecteur = _connecteur(Serveur(jeton_status=statut))

    with pytest.raises(AuthenticationFailedError) as info:
        await connecteur.search(SearchCriteria(keywords=("python",)))

    assert SECRET not in str(info.value) and "id-test" not in str(info.value)


async def test_service_d_authentification_indisponible() -> None:
    with pytest.raises(SourceUnavailableError):
        await _connecteur(Serveur(jeton_status=503)).search(SearchCriteria(keywords=("a",)))


async def test_jeton_refuse_par_l_api_est_oublie() -> None:
    serveur = Serveur(recherche=httpx.Response(401))
    connecteur = _connecteur(serveur)

    with pytest.raises(AuthenticationFailedError):
        await connecteur.search(SearchCriteria(keywords=("a",)))
    with pytest.raises(AuthenticationFailedError):
        await connecteur.search(SearchCriteria(keywords=("a",)))

    assert serveur.jetons_emis == 2  # le jeton révoqué n'est pas réutilisé


async def test_reponse_hors_contrat_est_une_erreur_explicite() -> None:
    connecteur = _connecteur(Serveur(recherche=httpx.Response(200, json={"surprise": 1})))

    with pytest.raises(InvalidResponseError):
        await connecteur.search(SearchCriteria(keywords=("a",)))


async def test_details_d_une_offre_et_offre_disparue() -> None:
    brute = json.loads(FIXTURE.read_text(encoding="utf-8"))["resultats"][0]
    present = await _connecteur(Serveur(recherche=httpx.Response(200, json=brute))).get_details(
        "190ABCD"
    )
    absent = await _connecteur(Serveur(recherche=httpx.Response(204))).get_details("190ZZZZ")

    assert present is not None and present.external_id == "190ABCD"
    assert absent is None
    with pytest.raises(InvalidResponseError):
        await _connecteur(Serveur()).get_details("../etc")


def test_departement_invalide_refuse() -> None:
    with pytest.raises(NotConfiguredError):
        _connecteur(Serveur(), department="75; DROP")
