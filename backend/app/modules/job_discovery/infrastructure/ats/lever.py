"""Connecteur Lever Postings : API de lecture publique des offres publiées d'une entreprise.

Conditions vérifiées dans la documentation officielle (2026-11-03) : la lecture des offres
publiées n'exige pas de clé (la clé ne sert qu'à la candidature par POST, jamais utilisée ici),
HTTPS obligatoire, instances globale et EU. Débit volontairement bas.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

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
    text_or_none,
    validate_token,
)
from app.modules.job_discovery.infrastructure.http import get_json

BASE_URLS = {
    "global": "https://api.lever.co/v0/postings",
    "eu": "https://api.eu.lever.co/v0/postings",
}

# Correspondances sûres uniquement : un libellé ambigu reste `None` plutôt qu'inventé
# (« Full-time » ne dit pas s'il s'agit d'un CDI ou d'un CDD).
_CONTRATS = {
    "intern": EmploymentType.INTERNSHIP,
    "internship": EmploymentType.INTERNSHIP,
    "part-time": EmploymentType.PART_TIME,
    "part time": EmploymentType.PART_TIME,
    "temporary": EmploymentType.TEMPORARY,
}
_TELETRAVAIL = {
    "remote": RemoteType.REMOTE,
    "hybrid": RemoteType.HYBRID,
    "on-site": RemoteType.ON_SITE,
    "onsite": RemoteType.ON_SITE,
}


class LeverConnector:
    kind = SourceKind.PUBLIC_ATS

    def __init__(
        self,
        *,
        company_token: str,
        company_name: str,
        client: httpx.AsyncClient,
        region: Literal["global", "eu"] = "global",
    ) -> None:
        self._token = validate_token(company_token, source="Lever")
        self._company = company_name
        self._client = client
        self._base = f"{BASE_URLS[region]}/{self._token}"
        self.key = f"lever:{self._token}"
        self.name = f"{company_name} (Lever)"

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
        donnees = await get_json(
            self._client, self._base, source_key=self.key, params={"mode": "json"}
        )
        brut = expect_list(donnees, source_key=self.key, contexte="liste des offres")
        offres = [
            self._to_connector_offer(expect_dict(o, source_key=self.key, contexte="offre"))
            for o in brut
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
        if not external_id.replace("-", "").isalnum():
            raise InvalidResponseError("Identifiant d'offre invalide.", source_key=self.key)
        donnees = await get_json(
            self._client,
            f"{self._base}/{external_id}",
            source_key=self.key,
            params={"mode": "json"},
            not_found_is_error=False,
        )
        if donnees is None:
            return None
        return self._to_connector_offer(expect_dict(donnees, source_key=self.key, contexte="offre"))

    async def health_check(self) -> HealthStatus:
        await get_json(
            self._client, self._base, source_key=self.key, params={"mode": "json", "limit": "1"}
        )
        return HealthStatus(HealthState.OK, datetime.now(UTC))

    def _to_connector_offer(self, brut: dict[str, Any]) -> ConnectorOffer:
        identifiant = text_or_none(brut.get("id"))
        titre = text_or_none(brut.get("text"))
        url_publique = text_or_none(brut.get("hostedUrl"))
        url_candidature = text_or_none(brut.get("applyUrl")) or url_publique
        if identifiant is None or titre is None or url_candidature is None:
            raise InvalidResponseError("Offre sans identifiant, titre ou URL.", source_key=self.key)
        categories_brut = brut.get("categories")
        categories: dict[str, Any] = categories_brut if isinstance(categories_brut, dict) else {}
        localisation = text_or_none(categories.get("location"))
        description = self._description(brut)
        salaire_min, salaire_max, devise = self._salaire(brut.get("salaryRange"))
        offre = NormalizedOffer(
            title=titre,
            description=description,
            application_url=url_candidature,
            canonical_url=url_publique,
            company_name=self._company,
            location=localisation,
            country_code=self._pays(brut.get("country")),
            employment_type=_CONTRATS.get(
                (text_or_none(categories.get("commitment")) or "").lower()
            ),
            remote_type=_TELETRAVAIL.get((text_or_none(brut.get("workplaceType")) or "").lower()),
            salary_min=salaire_min,
            salary_max=salaire_max,
            salary_currency=devise,
            published_at=self._date(brut.get("createdAt")),
            content_hash=content_hash(
                titre, self._company, localisation, description, url_candidature
            ),
        )
        return ConnectorOffer(
            external_id=identifiant, offer=offre, raw_payload=brut, source_url=url_publique
        )

    @staticmethod
    def _description(brut: dict[str, Any]) -> str:
        parties = [
            text_or_none(brut.get("descriptionPlain"))
            or html_to_text(text_or_none(brut.get("description")) or ""),
            text_or_none(brut.get("additionalPlain"))
            or html_to_text(text_or_none(brut.get("additional")) or ""),
        ]
        listes = brut.get("lists")
        if isinstance(listes, list):
            for bloc in listes:
                if isinstance(bloc, dict):
                    parties.append(text_or_none(bloc.get("text")) or "")
                    parties.append(html_to_text(text_or_none(bloc.get("content")) or ""))
        return "\n\n".join(p for p in parties if p)

    @staticmethod
    def _pays(valeur: Any) -> CountryCode | None:
        code = text_or_none(valeur)
        if code is None:
            return None
        try:
            return CountryCode(code)
        except DomainValueError:
            return None

    @staticmethod
    def _date(valeur: Any) -> datetime | None:
        if isinstance(valeur, bool) or not isinstance(valeur, int | float):
            return None
        try:
            return datetime.fromtimestamp(valeur / 1000, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None

    @staticmethod
    def _salaire(valeur: Any) -> tuple[Decimal | None, Decimal | None, str | None]:
        """Seuls les salaires annuels sont retenus : on ne mélange pas taux horaire et annuel."""
        if not isinstance(valeur, dict) or valeur.get("interval") != "per-year-salary":
            return None, None, None
        devise = text_or_none(valeur.get("currency"))
        try:
            minimum = Decimal(str(valeur["min"])) if valeur.get("min") is not None else None
            maximum = Decimal(str(valeur["max"])) if valeur.get("max") is not None else None
        except InvalidOperation:
            return None, None, None
        if devise is None or len(devise) != 3 or (minimum is None and maximum is None):
            return None, None, None
        if (minimum is not None and minimum < 0) or (maximum is not None and maximum < 0):
            return None, None, None
        if minimum is not None and maximum is not None and maximum < minimum:
            return None, None, None
        return minimum, maximum, devise.upper()
