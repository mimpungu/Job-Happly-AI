"""Connecteur Workable : liste publique des offres publiées d'un compte.

Conditions vérifiées dans la documentation officielle (workable.readme.io, « Public Endpoints »,
2026-11-04) : `GET https://www.workable.com/api/accounts/{subdomain}` renvoie « the public jobs
for an account », sans authentification. Cette adresse redirige (HTTP 302) vers
`apply.workable.com/api/v1/widget/accounts/{subdomain}` ; comme les redirections ne sont jamais
suivies automatiquement, on appelle directement la cible. `robots.txt` d'apply.workable.com
autorise la lecture. Aucune limite de débit documentée : débit volontairement bas. Un compte
inexistant répond 404. Pas de détail public par offre : le détail relit la liste.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.domain.value_objects import (
    CountryCode,
    DomainValueError,
    EmploymentType,
    RemoteType,
)
from app.modules.job_discovery.domain.connector import (
    ConnectorCapabilities,
    ConnectorOffer,
    HealthState,
    HealthStatus,
    InvalidResponseError,
    SearchPage,
)
from app.modules.job_discovery.domain.criteria import SearchCriteria
from app.modules.job_discovery.domain.enums import SourceKind
from app.modules.job_discovery.domain.offers import NormalizedOffer
from app.modules.job_discovery.domain.text import content_hash, html_to_text
from app.modules.job_discovery.infrastructure.ats.common import (
    expect_dict,
    expect_list,
    paginate,
    parse_iso_datetime,
    text_or_none,
    validate_token,
)
from app.modules.job_discovery.infrastructure.http import get_json

BASE_URL = "https://apply.workable.com/api/v1/widget/accounts"

# « Full-time » ne dit pas CDI ou CDD, « Contract » pas freelance ou CDD : ils restent `None`.
_CONTRATS = {
    "part-time": EmploymentType.PART_TIME,
    "internship": EmploymentType.INTERNSHIP,
    "temporary": EmploymentType.TEMPORARY,
}
_TELETRAVAIL = {
    "remote": RemoteType.REMOTE,
    "hybrid": RemoteType.HYBRID,
    "on_site": RemoteType.ON_SITE,
}


class WorkableConnector:
    kind = SourceKind.PUBLIC_ATS

    def __init__(self, *, subdomain: str, company_name: str, client: httpx.AsyncClient) -> None:
        self._token = validate_token(subdomain, source="Workable")
        self._company = company_name
        self._client = client
        self.key = f"workable:{self._token}"
        self.name = f"{company_name} (Workable)"

    def get_capabilities(self) -> ConnectorCapabilities:
        return ConnectorCapabilities(
            supports_keywords=True,
            supports_location=True,
            supports_remote_filter=True,
            requires_credentials=False,
            max_page_size=100,
            requests_per_second=1.0,
        )

    async def search(self, criteria: SearchCriteria) -> SearchPage:
        offres = await self._offres_publiees()
        page, suivant, total = paginate([o.offer for o in offres], criteria)
        par_contenu = {id(o.offer): o for o in offres}
        return SearchPage(
            offers=tuple(par_contenu[id(o)] for o in page),
            next_cursor=suivant,
            total=total,
            retrieved_at=datetime.now(UTC),
        )

    async def get_details(self, external_id: str) -> ConnectorOffer | None:
        if not external_id.isalnum():
            raise InvalidResponseError("Identifiant d'offre invalide.", source_key=self.key)
        return next(
            (o for o in await self._offres_publiees() if o.external_id == external_id), None
        )

    async def health_check(self) -> HealthStatus:
        await self._lire_compte(details=False)
        return HealthStatus(HealthState.OK, datetime.now(UTC))

    async def _lire_compte(self, *, details: bool) -> list[Any]:
        donnees = await get_json(
            self._client,
            f"{BASE_URL}/{self._token}",
            source_key=self.key,
            params={"details": "true" if details else "false"},
        )
        return expect_list(
            expect_dict(donnees, source_key=self.key, contexte="réponse").get("jobs"),
            source_key=self.key,
            contexte="jobs",
        )

    async def _offres_publiees(self) -> list[ConnectorOffer]:
        return [
            self._to_connector_offer(expect_dict(j, source_key=self.key, contexte="offre"))
            for j in await self._lire_compte(details=True)
        ]

    def _to_connector_offer(self, brut: dict[str, Any]) -> ConnectorOffer:
        identifiant = text_or_none(brut.get("shortcode"))
        titre = text_or_none(brut.get("title"))
        url_publique = text_or_none(brut.get("url")) or text_or_none(brut.get("shortlink"))
        url_candidature = text_or_none(brut.get("application_url")) or url_publique
        if identifiant is None or titre is None or url_candidature is None:
            raise InvalidResponseError("Offre sans identifiant, titre ou URL.", source_key=self.key)
        localisation = _localisation(brut)
        description = html_to_text(text_or_none(brut.get("description")) or "")
        offre = NormalizedOffer(
            title=titre,
            description=description,
            application_url=url_candidature,
            canonical_url=url_publique,
            company_name=self._company,
            location=localisation,
            country_code=_pays(brut.get("locations")),
            employment_type=_CONTRATS.get(
                (text_or_none(brut.get("employment_type")) or "").lower()
            ),
            remote_type=_teletravail(brut),
            # `created_at` est la création interne du poste, pas sa publication : non retenue.
            published_at=parse_iso_datetime(brut.get("published_on")),
            content_hash=content_hash(
                titre, self._company, localisation, description, url_candidature
            ),
        )
        return ConnectorOffer(
            external_id=identifiant, offer=offre, raw_payload=brut, source_url=url_publique
        )


def _localisation(brut: dict[str, Any]) -> str | None:
    parties = [text_or_none(brut.get(champ)) for champ in ("city", "state", "country")]
    return ", ".join(p for p in parties if p) or None


def _pays(locations: Any) -> CountryCode | None:
    """Code ISO fourni par la source, seulement s'il est unique parmi les lieux affichés."""
    if not isinstance(locations, list):
        return None
    codes = {
        text_or_none(lieu.get("countryCode"))
        for lieu in locations
        if isinstance(lieu, dict) and lieu.get("hidden") is not True
    }
    codes.discard(None)
    if len(codes) != 1:
        return None
    try:
        return CountryCode(str(codes.pop()))
    except DomainValueError:
        return None


def _teletravail(brut: dict[str, Any]) -> RemoteType | None:
    # `workplace_type` (documenté) est plus précis que `telecommuting` ; `telecommuting = false`
    # ne distingue pas le sur site de l'hybride, il reste donc inconnu.
    precis = _TELETRAVAIL.get((text_or_none(brut.get("workplace_type")) or "").lower())
    if precis is not None:
        return precis
    return RemoteType.REMOTE if brut.get("telecommuting") is True else None
