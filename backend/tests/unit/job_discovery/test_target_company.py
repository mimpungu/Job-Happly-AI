import httpx
import pytest

from app.modules.job_discovery.application.target_connectors import connector_for
from app.modules.job_discovery.domain.target_company import AtsKind, detect_from_url
from app.modules.job_discovery.infrastructure.ats.greenhouse import GreenhouseConnector
from app.modules.job_discovery.infrastructure.ats.lever import LeverConnector
from app.modules.job_discovery.infrastructure.http import create_http_client
from app.modules.job_discovery.infrastructure.models import TargetCompanyModel


class TestDetection:
    @pytest.mark.parametrize(
        ("url", "type_", "jeton", "region"),
        [
            ("https://boards.greenhouse.io/exemplesa", AtsKind.GREENHOUSE, "exemplesa", None),
            (
                "https://job-boards.greenhouse.io/exemplesa/jobs/123",
                AtsKind.GREENHOUSE,
                "exemplesa",
                None,
            ),
            ("https://jobs.lever.co/exemplesa/abc-def", AtsKind.LEVER, "exemplesa", "global"),
            ("https://jobs.eu.lever.co/exemplesa", AtsKind.LEVER, "exemplesa", "eu"),
            ("https://JOBS.LEVER.CO/Exemple", AtsKind.LEVER, "Exemple", "global"),
        ],
    )
    def test_reconnait_un_ats_public(
        self, url: str, type_: AtsKind, jeton: str, region: str | None
    ) -> None:
        source = detect_from_url(url)

        assert source is not None
        assert (source.ats_kind, source.token, source.region) == (type_, jeton, region)
        assert source.method == "url_pattern"

    @pytest.mark.parametrize(
        "url",
        [
            "https://www.exemple.test/carrieres",
            "http://boards.greenhouse.io/exemplesa",  # pas de HTTPS
            "https://boards.greenhouse.io/",  # pas de jeton
            "https://evil.test/boards.greenhouse.io/exemplesa",
            "https://boards.greenhouse.io.evil.test/exemplesa",
            "pas une url",
            "",
        ],
    )
    def test_ne_devine_rien_pour_une_url_inconnue(self, url: str) -> None:
        assert detect_from_url(url) is None


def _entreprise(**champs: object) -> TargetCompanyModel:
    valeurs: dict[str, object] = {"name": "Exemple SA", "detection_status": "supported"}
    valeurs.update(champs)
    return TargetCompanyModel(**valeurs)


class TestConstructionDuConnecteur:
    def test_greenhouse(self) -> None:
        connecteur = connector_for(
            _entreprise(ats_kind="greenhouse", ats_token="exemplesa"), create_http_client()
        )

        assert isinstance(connecteur, GreenhouseConnector)
        assert connecteur.key == "greenhouse:exemplesa"

    def test_lever_region_europeenne(self) -> None:
        transport = httpx.MockTransport(lambda r: httpx.Response(200, json=[]))
        client = create_http_client(transport=transport)

        connecteur = connector_for(
            _entreprise(ats_kind="lever", ats_token="exemplesa", ats_region="eu"), client
        )

        assert isinstance(connecteur, LeverConnector)

    @pytest.mark.parametrize(
        "champs",
        [
            {"detection_status": "pending", "ats_kind": "greenhouse", "ats_token": "x"},
            {"detection_status": "unsupported", "ats_kind": "unsupported"},
            {"ats_kind": "careers_page"},
            {"ats_kind": "greenhouse", "ats_token": None},
        ],
    )
    def test_aucun_connecteur_pour_une_source_non_supportee(
        self, champs: dict[str, object]
    ) -> None:
        assert connector_for(_entreprise(**champs), create_http_client()) is None
