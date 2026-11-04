"""Connecteur Greenhouse Job Board : API de lecture publique d'une entreprise.

Conditions vérifiées dans la documentation officielle (2026-11-03) : les requêtes GET du job
board sont publiques, sans authentification ; seule la candidature (POST) en exige une, et
n'est jamais utilisée ici. Aucune limite de débit n'est documentée : débit volontairement bas.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.domain.value_objects import CountryCode, DomainValueError
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

BASE_URL = "https://boards-api.greenhouse.io/v1/boards"


class GreenhouseConnector:
    kind = SourceKind.PUBLIC_ATS

    def __init__(self, *, board_token: str, company_name: str, client: httpx.AsyncClient) -> None:
        self._token = validate_token(board_token, source="Greenhouse")
        self._company = company_name
        self._client = client
        self.key = f"greenhouse:{self._token}"
        self.name = f"{company_name} (Greenhouse)"

    def get_capabilities(self) -> ConnectorCapabilities:
        return ConnectorCapabilities(
            supports_keywords=True,
            supports_location=True,
            requires_credentials=False,
            max_page_size=100,
            requests_per_second=1.0,
        )

    async def search(self, criteria: SearchCriteria) -> SearchPage:
        donnees = await get_json(
            self._client,
            f"{BASE_URL}/{self._token}/jobs",
            source_key=self.key,
            params={"content": "true"},
        )
        brut = expect_list(
            expect_dict(donnees, source_key=self.key, contexte="réponse").get("jobs"),
            source_key=self.key,
            contexte="jobs",
        )
        offres = [
            self._to_connector_offer(expect_dict(j, source_key=self.key, contexte="offre"))
            for j in brut
        ]
        page, suivant, total = paginate([o.offer for o in offres], criteria)
        par_contenu = {id(o.offer): o for o in offres}
        return SearchPage(
            offers=tuple(par_contenu[id(o)] for o in page),
            next_cursor=suivant,
            total=total,
            retrieved_at=datetime.now(UTC),
        )

    async def get_details(self, external_id: str) -> ConnectorOffer | None:
        if not external_id.isdigit():
            raise InvalidResponseError("Identifiant d'offre invalide.", source_key=self.key)
        donnees = await get_json(
            self._client,
            f"{BASE_URL}/{self._token}/jobs/{external_id}",
            source_key=self.key,
            not_found_is_error=False,
        )
        if donnees is None:
            return None
        return self._to_connector_offer(expect_dict(donnees, source_key=self.key, contexte="offre"))

    async def health_check(self) -> HealthStatus:
        await get_json(self._client, f"{BASE_URL}/{self._token}/jobs", source_key=self.key)
        return HealthStatus(HealthState.OK, datetime.now(UTC))

    def _to_connector_offer(self, brut: dict[str, Any]) -> ConnectorOffer:
        identifiant = brut.get("id")
        titre = text_or_none(brut.get("title"))
        url = text_or_none(brut.get("absolute_url"))
        if identifiant is None or titre is None or url is None:
            raise InvalidResponseError("Offre sans identifiant, titre ou URL.", source_key=self.key)
        lieu = brut.get("location")
        localisation = text_or_none(lieu.get("name")) if isinstance(lieu, dict) else None
        description = html_to_text(text_or_none(brut.get("content")) or "")
        langue = text_or_none(brut.get("language"))
        pays = None
        if (code := text_or_none(brut.get("country"))) is not None:
            try:
                pays = CountryCode(code)
            except DomainValueError:
                pays = None
        offre = NormalizedOffer(
            title=titre,
            description=description,
            application_url=url,
            canonical_url=url,
            company_name=self._company,
            location=localisation,
            country_code=pays,
            # `updated_at` est une date de mise à jour, pas de publication : on ne la déguise pas.
            published_at=parse_iso_datetime(brut.get("first_published")),
            language=langue,
            content_hash=content_hash(titre, self._company, localisation, description, url),
        )
        return ConnectorOffer(
            external_id=str(identifiant),
            offer=offre,
            raw_payload=brut,
            source_url=url,
        )
