"""Connecteur de l'API officielle « Offres d'emploi v2 » de France Travail.

Source officielle avec compte développeur (OAuth2 « client credentials »).

ÉTAT (2026-11-04) : France Travail a retiré cette API de son portail le temps d'analyser ses
conditions de réutilisation (usages automatisés massifs). Sans accès accordé sur demande, ce
connecteur ne peut pas fonctionner ; il ne doit jamais servir à contourner ce retrait.

À VALIDER avec de vrais identifiants : ce connecteur a été écrit d'après la connaissance de l'API
(la documentation du portail est une application JavaScript non lisible automatiquement) et testé
uniquement sur des réponses fictives de même forme. Aucun appel authentifié réel n'a encore eu
lieu ; voir docs/DATA_SOURCES.md.

Garanties :
- les identifiants ne sont lus que depuis la configuration (SecretStr) et n'apparaissent dans
  aucun message d'erreur ni journal ;
- jeton mis en cache jusqu'à son expiration, jamais écrit sur disque ;
- le salaire (texte libre côté source) n'est pas interprété : absent plutôt qu'inventé ;
- aucune candidature n'est jamais envoyée.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import httpx
from pydantic import SecretStr

from app.core.domain.value_objects import CountryCode, EmploymentType
from app.modules.job_discovery.domain.connector import (
    AuthenticationFailedError,
    ConnectorCapabilities,
    ConnectorOffer,
    HealthState,
    HealthStatus,
    InvalidResponseError,
    NotConfiguredError,
    SearchPage,
    SourceTimeoutError,
    SourceUnavailableError,
)
from app.modules.job_discovery.domain.criteria import SearchCriteria
from app.modules.job_discovery.domain.enums import SourceKind
from app.modules.job_discovery.domain.filtering import matches_criteria
from app.modules.job_discovery.domain.offers import NormalizedOffer
from app.modules.job_discovery.domain.text import content_hash
from app.modules.job_discovery.infrastructure.ats.common import (
    expect_dict,
    expect_list,
    text_or_none,
)
from app.modules.job_discovery.infrastructure.http import fetch, raise_for_status

TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token"  # noqa: S105 - URL publique, pas un secret
API_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres"
SCOPE = "api_offresdemploiv2 o2dsoffre"
DETAIL_URL = "https://candidat.francetravail.fr/offres/recherche/detail"

MAX_PAGE_SIZE = 150  # plafond de la source par requête
MAX_OFFSET = 1149  # la source n'expose pas au-delà de 1150 résultats par recherche
_MARGE_JETON = 30.0  # secondes : on renouvelle un peu avant l'expiration
_MAX_MOTS_CLES = 200

_CONTRATS = {
    "CDI": EmploymentType.PERMANENT,
    "CDD": EmploymentType.FIXED_TERM,
    "MIS": EmploymentType.TEMPORARY,  # mission d'intérim
    "SAI": EmploymentType.TEMPORARY,  # contrat saisonnier
    "LIB": EmploymentType.FREELANCE,
    "FRA": EmploymentType.OTHER,
    "DIN": EmploymentType.OTHER,
}
_CONTENT_RANGE = re.compile(r"/(\d+)\s*$")
_DEPARTEMENT = re.compile(r"^(?:\d{2}|2[AB]|97\d)$")


class FranceTravailConnector:
    kind = SourceKind.OFFICIAL_API
    key = "france_travail"
    name = "France Travail (API officielle)"

    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        client_id: SecretStr | None,
        client_secret: SecretStr | None,
        department: str | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if department is not None and not _DEPARTEMENT.fullmatch(department):
            raise NotConfiguredError("Département invalide.", source_key=self.key)
        self._client = client
        self._id = client_id
        self._secret = client_secret
        self._department = department
        self._clock = clock
        self._token: str | None = None
        self._expires_at = 0.0

    def get_capabilities(self) -> ConnectorCapabilities:
        return ConnectorCapabilities(
            countries=frozenset({"FR"}),
            supports_keywords=True,
            supports_location=True,
            supports_published_since=False,
            requires_credentials=True,
            max_page_size=MAX_PAGE_SIZE,
            # Prudent : bien en deçà du quota annoncé par la source.
            requests_per_second=2.0,
        )

    # ------------------------------------------------------------------ recherche

    async def search(self, criteria: SearchCriteria) -> SearchPage:
        debut = _decoder_curseur(criteria.cursor, self.key)
        taille = min(criteria.page_size, MAX_PAGE_SIZE)
        fin = min(debut + taille - 1, MAX_OFFSET)
        if debut > MAX_OFFSET:
            return SearchPage(offers=(), retrieved_at=datetime.now(UTC))

        reponse = await self._get(
            f"{API_URL}/search", params=self._parametres(criteria, debut, fin)
        )
        if reponse.status_code == 204:  # aucun résultat : un état normal, pas une erreur
            return SearchPage(offers=(), total=0, retrieved_at=datetime.now(UTC))
        corps = expect_dict(_json(reponse, self.key), source_key=self.key, contexte="réponse")
        brutes = expect_list(corps.get("resultats"), source_key=self.key, contexte="resultats")
        offres = [
            self._to_connector_offer(expect_dict(b, source_key=self.key, contexte="offre"))
            for b in brutes
        ]
        # La source filtre par mots-clés ; ville, entreprise… sont affinés localement.
        retenues = tuple(o for o in offres if matches_criteria(o.offer, criteria))
        total = _total(reponse)
        suite = fin + 1
        encore = len(brutes) >= (fin - debut + 1) and suite <= MAX_OFFSET
        if total is not None:
            encore = encore and suite < total
        return SearchPage(
            offers=retenues,
            next_cursor=str(suite) if encore else None,
            total=total,
            retrieved_at=datetime.now(UTC),
            warnings=("Résultats partiels renvoyés par la source (206).",)
            if reponse.status_code == 206
            else (),
        )

    async def get_details(self, external_id: str) -> ConnectorOffer | None:
        if not re.fullmatch(r"[A-Za-z0-9]{1,20}", external_id):
            raise InvalidResponseError("Identifiant d'offre invalide.", source_key=self.key)
        reponse = await self._get(f"{API_URL}/{quote(external_id)}", not_found_ok=True)
        if reponse.status_code in (204, 404):
            return None
        return self._to_connector_offer(
            expect_dict(_json(reponse, self.key), source_key=self.key, contexte="offre")
        )

    async def health_check(self) -> HealthStatus:
        await self._jeton()  # vérifie la configuration et l'authentification sans chercher d'offre
        return HealthStatus(HealthState.OK, datetime.now(UTC))

    # ------------------------------------------------------------------ interne

    def _parametres(self, criteria: SearchCriteria, debut: int, fin: int) -> dict[str, str]:
        mots = " ".join(
            [t for t in (criteria.title, criteria.company, criteria.sector) if t]
            + list(criteria.keywords)
            + list(criteria.skills)
        )
        parametres = {"range": f"{debut}-{fin}", "sort": "1"}  # 1 = plus récentes d'abord
        if mots:
            parametres["motsCles"] = mots[:_MAX_MOTS_CLES]
        if self._department:
            parametres["departement"] = self._department
        return parametres

    async def _get(
        self,
        url: str,
        *,
        params: dict[str, str] | None = None,
        not_found_ok: bool = False,
    ) -> httpx.Response:
        jeton = await self._jeton()
        reponse = await fetch(
            self._client,
            url,
            source_key=self.key,
            params=params,
            headers={"Authorization": f"Bearer {jeton}"},
        )
        if reponse.status_code == 401:
            self._token = None  # jeton révoqué ou expiré : il sera redemandé
            raise AuthenticationFailedError("Jeton refusé par la source.", source_key=self.key)
        if reponse.status_code in (204, 206) or (not_found_ok and reponse.status_code == 404):
            return reponse
        raise_for_status(reponse, source_key=self.key)
        return reponse

    async def _jeton(self) -> str:
        if self._id is None or self._secret is None:
            raise NotConfiguredError(
                "Identifiants France Travail absents "
                "(HAPPLY_FRANCE_TRAVAIL_CLIENT_ID / HAPPLY_FRANCE_TRAVAIL_CLIENT_SECRET).",
                source_key=self.key,
            )
        if self._token is not None and self._clock() < self._expires_at:
            return self._token
        try:
            reponse = await self._client.post(
                TOKEN_URL,
                params={"realm": "/partenaire"},
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._id.get_secret_value(),
                    "client_secret": self._secret.get_secret_value(),
                    "scope": SCOPE,
                },
            )
        except httpx.TimeoutException as erreur:
            raise SourceTimeoutError("Délai dépassé (jeton).", source_key=self.key) from erreur
        except httpx.TransportError as erreur:
            raise SourceUnavailableError("Erreur réseau (jeton).", source_key=self.key) from erreur
        if reponse.status_code in (400, 401, 403):
            # Message fixe : le corps de la réponse n'est jamais relayé.
            raise AuthenticationFailedError(
                "Identifiants refusés par la source.", source_key=self.key
            )
        if reponse.status_code >= 500:
            raise SourceUnavailableError(
                "Service d'authentification indisponible.", source_key=self.key
            )
        try:
            donnees = reponse.json()
            jeton = donnees["access_token"]
            duree = float(donnees.get("expires_in", 0))
        except (ValueError, KeyError, TypeError, AttributeError) as erreur:
            raise InvalidResponseError(
                "Réponse de jeton illisible.", source_key=self.key
            ) from erreur
        if not isinstance(jeton, str) or not jeton:
            raise InvalidResponseError("Réponse de jeton illisible.", source_key=self.key)
        self._token = jeton
        self._expires_at = self._clock() + max(0.0, duree - _MARGE_JETON)
        return jeton

    def _to_connector_offer(self, brut: dict[str, Any]) -> ConnectorOffer:
        identifiant = text_or_none(brut.get("id"))
        titre = text_or_none(brut.get("intitule"))
        if identifiant is None or titre is None:
            raise InvalidResponseError("Offre sans identifiant ou intitulé.", source_key=self.key)
        origine = brut.get("origineOffre")
        url_origine = text_or_none(origine.get("urlOrigine")) if isinstance(origine, dict) else None
        url_publique = f"{DETAIL_URL}/{quote(identifiant)}"
        entreprise = brut.get("entreprise")
        nom = text_or_none(entreprise.get("nom")) if isinstance(entreprise, dict) else None
        lieu = brut.get("lieuTravail")
        localisation = text_or_none(lieu.get("libelle")) if isinstance(lieu, dict) else None
        description = text_or_none(brut.get("description")) or titre
        url_candidature = url_origine or url_publique
        offre = NormalizedOffer(
            title=titre,
            description=description,
            application_url=url_candidature,
            canonical_url=url_publique,
            company_name=nom,
            location=localisation,
            country_code=CountryCode("FR"),
            employment_type=_CONTRATS.get((text_or_none(brut.get("typeContrat")) or "").upper()),
            published_at=_date(brut.get("dateCreation")),
            language="fr",
            content_hash=content_hash(titre, nom, localisation, description, url_candidature),
        )
        return ConnectorOffer(
            external_id=identifiant, offer=offre, raw_payload=brut, source_url=url_publique
        )


def _decoder_curseur(curseur: str | None, source_key: str) -> int:
    if curseur is None:
        return 0
    try:
        valeur = int(curseur)
    except ValueError as erreur:
        raise InvalidResponseError("Curseur invalide.", source_key=source_key) from erreur
    if valeur < 0:
        raise InvalidResponseError("Curseur invalide.", source_key=source_key)
    return valeur


def _json(reponse: httpx.Response, source_key: str) -> Any:
    try:
        return reponse.json()
    except ValueError as erreur:
        raise InvalidResponseError("JSON invalide.", source_key=source_key) from erreur


def _total(reponse: httpx.Response) -> int | None:
    """Total annoncé dans `Content-Range: offres 0-149/12345` ; `None` s'il est absent."""
    trouve = _CONTENT_RANGE.search(reponse.headers.get("Content-Range", ""))
    return int(trouve.group(1)) if trouve else None


def _date(valeur: Any) -> datetime | None:
    texte = text_or_none(valeur)
    if texte is None:
        return None
    try:
        date = datetime.fromisoformat(texte.replace("Z", "+00:00"))
    except ValueError:
        return None
    return date if date.tzinfo else date.replace(tzinfo=UTC)
