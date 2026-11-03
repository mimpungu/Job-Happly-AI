import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.job_discovery.infrastructure.models import TargetCompanyModel
from app.modules.job_discovery.infrastructure.target_company_repository import (
    SqlTargetCompanyRepository,
    TargetCompanyError,
)

MAINTENANT = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)


async def test_ajoute_une_entreprise_et_detecte_son_ats(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    depot = SqlTargetCompanyRepository(session)

    entreprise = await depot.add(
        user_id, name=" Exemple SA ", careers_url="https://jobs.lever.co/exemplesa", now=MAINTENANT
    )

    assert entreprise.name == "Exemple SA"
    assert entreprise.ats_kind == "lever"
    assert entreprise.ats_token == "exemplesa"
    assert entreprise.detection_status == "supported"
    assert entreprise.enabled is False  # jamais active sans décision
    assert entreprise.detected_at == MAINTENANT


async def test_une_url_inconnue_reste_en_attente_de_detection(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    entreprise = await SqlTargetCompanyRepository(session).add(
        user_id, name="Autre", careers_url="https://www.autre.test/carrieres", now=MAINTENANT
    )

    assert entreprise.detection_status == "pending"
    assert entreprise.ats_kind is None


async def test_refuse_un_nom_vide_et_un_doublon_insensible_a_la_casse(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    depot = SqlTargetCompanyRepository(session)
    with pytest.raises(TargetCompanyError):
        await depot.add(user_id, name="   ", careers_url=None, now=MAINTENANT)

    await depot.add(user_id, name="Exemple", careers_url=None, now=MAINTENANT)
    with pytest.raises(DBAPIError):
        async with session.begin_nested():
            await depot.add(user_id, name="EXEMPLE", careers_url=None, now=MAINTENANT)


async def test_active_seulement_une_source_supportee(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    depot = SqlTargetCompanyRepository(session)
    supportee = await depot.add(
        user_id, name="A", careers_url="https://boards.greenhouse.io/a", now=MAINTENANT
    )
    inconnue = await depot.add(user_id, name="B", careers_url=None, now=MAINTENANT)

    await depot.set_enabled(supportee, True)
    assert supportee.enabled is True
    with pytest.raises(TargetCompanyError):
        await depot.set_enabled(inconnue, True)


async def test_une_source_qui_refuse_l_acces_devient_non_supportee_et_inactive(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    depot = SqlTargetCompanyRepository(session)
    entreprise = await depot.add(
        user_id, name="A", careers_url="https://boards.greenhouse.io/a", now=MAINTENANT
    )
    await depot.set_enabled(entreprise, True)

    await depot.mark_unsupported(entreprise, "robots_txt", MAINTENANT)

    assert entreprise.enabled is False
    assert entreprise.ats_kind == "unsupported"
    assert entreprise.detection_status == "unsupported"
    with pytest.raises(TargetCompanyError):
        await depot.set_enabled(entreprise, True)


async def test_une_page_carrieres_exige_la_verification_des_cgu(
    session: AsyncSession, user_id: uuid.UUID
) -> None:
    depot = SqlTargetCompanyRepository(session)
    entreprise = await depot.add(user_id, name="A", careers_url=None, now=MAINTENANT)
    entreprise.ats_kind = "careers_page"
    entreprise.detection_status = "supported"
    await session.flush()

    with pytest.raises(TargetCompanyError):
        await depot.set_enabled(entreprise, True)

    entreprise.tos_verified_at = MAINTENANT
    await depot.set_enabled(entreprise, True)
    assert entreprise.enabled is True


@pytest.mark.parametrize(
    "champs",
    [
        {"enabled": True},  # activée sans être supportée
        {"ats_kind": "greenhouse"},  # ATS sans jeton
        {"ats_kind": "inconnu"},
        {"detection_status": "nouveau"},
        {"ats_kind": "careers_page", "detection_status": "supported", "enabled": True},  # sans CGU
    ],
)
async def test_la_base_refuse_les_etats_incoherents(
    session: AsyncSession, user_id: uuid.UUID, champs: dict[str, object]
) -> None:
    with pytest.raises(DBAPIError):
        async with session.begin_nested():
            session.add(TargetCompanyModel(owner_id=user_id, name="X", **champs))
            await session.flush()


async def test_liste_triee_par_nom(session: AsyncSession, user_id: uuid.UUID) -> None:
    depot = SqlTargetCompanyRepository(session)
    for nom in ("Zeta", "Alpha"):
        await depot.add(user_id, name=nom, careers_url=None, now=MAINTENANT)

    assert [e.name for e in await depot.list(user_id)] == ["Alpha", "Zeta"]
