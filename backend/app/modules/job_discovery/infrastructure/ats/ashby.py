"""Connecteur Ashby Job Postings : API publique de lecture du job board d'une entreprise.

Conditions vérifiées dans la documentation officielle (developers.ashbyhq.com, 2026-11-04) :
`GET /posting-api/job-board/{board}` est public, sans authentification, prévu pour afficher les
offres sur un site tiers. Aucune limite de débit documentée : débit volontairement bas. Un board
inexistant répond 404. L'API ne fournit pas de détail par offre : le détail relit le board.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from app.core.domain.value_objects import EmploymentType, RemoteType
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

BASE_URL = "https://api.ashbyhq.com/posting-api/job-board"

# « FullTime » ne dit pas CDI ou CDD, « Contract » pas freelance ou CDD : ils restent `None`.
_CONTRATS = {
    "Intern": EmploymentType.INTERNSHIP,
    "PartTime": EmploymentType.PART_TIME,
    "Temporary": EmploymentType.TEMPORARY,
}
_TELETRAVAIL = {
    "OnSite": RemoteType.ON_SITE,
    "Remote": RemoteType.REMOTE,
    "Hybrid": RemoteType.HYBRID,
}


class AshbyConnector:
    kind = SourceKind.PUBLIC_ATS

    def __init__(self, *, board_name: str, company_name: str, client: httpx.AsyncClient) -> None:
        self._token = validate_token(board_name, source="Ashby")
        self._company = company_name
        self._client = client
        self.key = f"ashby:{self._token}"
        self.name = f"{company_name} (Ashby)"

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
        if not external_id.replace("-", "").isalnum():
            raise InvalidResponseError("Identifiant d'offre invalide.", source_key=self.key)
        return next(
            (o for o in await self._offres_publiees() if o.external_id == external_id), None
        )

    async def health_check(self) -> HealthStatus:
        await self._lire_board(compensation=False)
        return HealthStatus(HealthState.OK, datetime.now(UTC))

    async def _lire_board(self, *, compensation: bool) -> list[Any]:
        donnees = await get_json(
            self._client,
            f"{BASE_URL}/{self._token}",
            source_key=self.key,
            params={"includeCompensation": "true" if compensation else "false"},
        )
        return expect_list(
            expect_dict(donnees, source_key=self.key, contexte="réponse").get("jobs"),
            source_key=self.key,
            contexte="jobs",
        )

    async def _offres_publiees(self) -> list[ConnectorOffer]:
        offres = []
        for brut in await self._lire_board(compensation=True):
            job = expect_dict(brut, source_key=self.key, contexte="offre")
            # Une offre non listée n'est accessible que par lien direct : l'entreprise ne la
            # publie pas, on ne la diffuse donc pas.
            if job.get("isListed") is False:
                continue
            offres.append(self._to_connector_offer(job))
        return offres

    def _to_connector_offer(self, brut: dict[str, Any]) -> ConnectorOffer:
        identifiant = text_or_none(brut.get("id"))
        titre = text_or_none(brut.get("title"))
        url_publique = text_or_none(brut.get("jobUrl"))
        url_candidature = text_or_none(brut.get("applyUrl")) or url_publique
        if identifiant is None or titre is None or url_candidature is None:
            raise InvalidResponseError("Offre sans identifiant, titre ou URL.", source_key=self.key)
        localisation = text_or_none(brut.get("location"))
        description = text_or_none(brut.get("descriptionPlain")) or html_to_text(
            text_or_none(brut.get("descriptionHtml")) or ""
        )
        salaire_min, salaire_max, devise = _salaire_annuel(brut.get("compensation"))
        offre = NormalizedOffer(
            title=titre,
            description=description,
            application_url=url_candidature,
            canonical_url=url_publique,
            company_name=self._company,
            location=localisation,
            # Ashby donne le pays en toutes lettres (« Spain », « European Union ») : aucun code
            # ISO fiable, on ne le devine pas.
            country_code=None,
            employment_type=_CONTRATS.get(text_or_none(brut.get("employmentType")) or ""),
            remote_type=_TELETRAVAIL.get(text_or_none(brut.get("workplaceType")) or ""),
            salary_min=salaire_min,
            salary_max=salaire_max,
            salary_currency=devise,
            published_at=parse_iso_datetime(brut.get("publishedAt")),
            content_hash=content_hash(
                titre, self._company, localisation, description, url_candidature
            ),
        )
        return ConnectorOffer(
            external_id=identifiant, offer=offre, raw_payload=brut, source_url=url_publique
        )


def _salaire_annuel(valeur: Any) -> tuple[Decimal | None, Decimal | None, str | None]:
    """Fourchette salariale annuelle unique, sinon rien.

    Plusieurs composantes « Salary » (paliers par pays, par niveau) rendraient toute fourchette
    unique trompeuse : on ne retient que le cas sans ambiguïté.
    """
    if not isinstance(valeur, dict):
        return None, None, None
    composantes = valeur.get("summaryComponents")
    if not isinstance(composantes, list):
        return None, None, None
    salaires = [
        c for c in composantes if isinstance(c, dict) and c.get("compensationType") == "Salary"
    ]
    if len(salaires) != 1 or salaires[0].get("interval") != "1 YEAR":
        return None, None, None
    salaire = salaires[0]
    devise = text_or_none(salaire.get("currencyCode"))
    try:
        minimum = _montant(salaire.get("minValue"))
        maximum = _montant(salaire.get("maxValue"))
    except InvalidOperation:
        return None, None, None
    if devise is None or len(devise) != 3 or (minimum is None and maximum is None):
        return None, None, None
    if (minimum is not None and minimum < 0) or (maximum is not None and maximum < 0):
        return None, None, None
    if minimum is not None and maximum is not None and maximum < minimum:
        return None, None, None
    return minimum, maximum, devise.upper()


def _montant(valeur: Any) -> Decimal | None:
    if valeur is None:
        return None
    if isinstance(valeur, bool) or not isinstance(valeur, int | float):
        raise InvalidOperation
    return Decimal(str(valeur))
