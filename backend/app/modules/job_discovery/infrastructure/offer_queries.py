"""Lecture des offres collectées : filtres, tri, pagination côté base, fiche détaillée, états."""

from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Any, cast

from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.job_discovery.domain.enums import OfferState
from app.modules.job_discovery.domain.search import (
    OfferDetail,
    OfferFilter,
    OfferNotFoundError,
    OfferPage,
    OfferSort,
    OfferSourceView,
    OfferSummary,
    StateFilter,
)
from app.modules.job_discovery.infrastructure.models import (
    JobOfferModel,
    JobOfferSourceModel,
    JobOfferStateModel,
    JobSourceModel,
)

_ECHAPPEMENT = "\\"


def _contient(colonne: Any, terme: str) -> ColumnElement[bool]:
    """`ILIKE '%terme%'` avec échappement : `%` et `_` saisis restent littéraux."""
    protege = terme.replace(_ECHAPPEMENT, _ECHAPPEMENT * 2).replace("%", r"\%").replace("_", r"\_")
    return cast("ColumnElement[bool]", colonne.ilike(f"%{protege}%", escape=_ECHAPPEMENT))


def _tri(tri: OfferSort) -> list[ColumnElement[Any]]:
    # `id` départage les ex æquo : sans lui, une page pourrait répéter ou sauter une offre.
    ordres: dict[OfferSort, list[ColumnElement[Any]]] = {
        OfferSort.PUBLISHED_DESC: [JobOfferModel.published_at.desc().nulls_last()],
        OfferSort.PUBLISHED_ASC: [JobOfferModel.published_at.asc().nulls_last()],
        OfferSort.TITLE_ASC: [func.lower(JobOfferModel.title).asc()],
        OfferSort.COMPANY_ASC: [func.lower(JobOfferModel.company_name).asc().nulls_last()],
        OfferSort.SALARY_DESC: [
            func.coalesce(JobOfferModel.salary_max, JobOfferModel.salary_min).desc().nulls_last()
        ],
        OfferSort.RECENTLY_SEEN: [JobOfferModel.last_seen_at.desc()],
    }
    return [*ordres[tri], JobOfferModel.id.asc()]


def _conditions(owner_id: uuid.UUID, f: OfferFilter) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = [JobOfferModel.owner_id == owner_id]
    if f.statuses:
        conditions.append(JobOfferModel.status.in_([s.value for s in f.statuses]))
    if f.text:
        conditions.append(
            or_(
                _contient(JobOfferModel.title, f.text),
                _contient(JobOfferModel.company_name, f.text),
                _contient(JobOfferModel.description, f.text),
            )
        )
    for mot in f.keywords:
        conditions.append(
            or_(_contient(JobOfferModel.title, mot), _contient(JobOfferModel.description, mot))
        )
    if f.company:
        conditions.append(_contient(JobOfferModel.company_name, f.company))
    if f.city:
        conditions.append(_contient(JobOfferModel.location, f.city))
    if f.country_codes:
        conditions.append(JobOfferModel.country_code.in_(f.country_codes))
    if f.remote_types:
        conditions.append(JobOfferModel.remote_type.in_([r.value for r in f.remote_types]))
    if f.employment_types:
        conditions.append(JobOfferModel.employment_type.in_([e.value for e in f.employment_types]))
    if f.salary_min is not None:
        # Une offre sans salaire connu ne satisfait pas un seuil : on ne devine pas.
        conditions.append(
            and_(
                JobOfferModel.salary_currency == f.salary_currency,
                func.coalesce(JobOfferModel.salary_max, JobOfferModel.salary_min) >= f.salary_min,
            )
        )
    if f.published_since is not None:
        conditions.append(JobOfferModel.published_at >= f.published_since)
    if f.language:
        # « fr » doit aussi retrouver « fr-FR ».
        conditions.append(
            or_(
                JobOfferModel.language == f.language,
                JobOfferModel.language.like(f"{f.language}-%"),
            )
        )
    return conditions


def _filtre_etat(requete: Any, etat: StateFilter) -> Any:
    colonne = JobOfferStateModel.state
    if etat is StateFilter.VISIBLE:
        return requete.where(or_(colonne.is_(None), colonne != OfferState.IGNORED.value))
    if etat is StateFilter.SAVED:
        return requete.where(colonne == OfferState.SAVED.value)
    if etat is StateFilter.IGNORED:
        return requete.where(colonne == OfferState.IGNORED.value)
    return requete


def _jointure_etat(requete: Any, owner_id: uuid.UUID) -> Any:
    return requete.outerjoin(
        JobOfferStateModel,
        and_(
            JobOfferStateModel.offer_id == JobOfferModel.id,
            JobOfferStateModel.owner_id == owner_id,
        ),
    )


def _resume(offre: JobOfferModel, etat: str | None, sources: tuple[str, ...]) -> OfferSummary:
    return OfferSummary(
        id=offre.id,
        title=offre.title,
        company_name=offre.company_name,
        location=offre.location,
        country_code=offre.country_code,
        employment_type=offre.employment_type,
        remote_type=offre.remote_type,
        salary_min=offre.salary_min,
        salary_max=offre.salary_max,
        salary_currency=offre.salary_currency,
        published_at=offre.published_at,
        status=offre.status,
        state=OfferState(etat) if etat else None,
        source_keys=sources,
    )


class SqlOfferQueryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def search(self, *, owner_id: uuid.UUID, offer_filter: OfferFilter) -> OfferPage:
        conditions = _conditions(owner_id, offer_filter)

        base = _filtre_etat(
            _jointure_etat(select(JobOfferModel.id), owner_id), offer_filter.state
        ).where(*conditions)
        total = int(
            await self._session.scalar(select(func.count()).select_from(base.subquery())) or 0
        )

        requete = _filtre_etat(
            _jointure_etat(select(JobOfferModel, JobOfferStateModel.state), owner_id),
            offer_filter.state,
        )
        lignes = (
            await self._session.execute(
                requete.where(*conditions)
                .order_by(*_tri(offer_filter.sort))
                .limit(offer_filter.page_size)
                .offset(offer_filter.offset)
            )
        ).all()

        sources = await self._sources_par_offre([ligne[0].id for ligne in lignes])
        items = tuple(_resume(offre, etat, sources.get(offre.id, ())) for offre, etat in lignes)
        return OfferPage(
            items=items, total=total, page=offer_filter.page, page_size=offer_filter.page_size
        )

    async def _sources_par_offre(
        self, offer_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, tuple[str, ...]]:
        if not offer_ids:
            return {}
        lignes = await self._session.execute(
            select(JobOfferSourceModel.offer_id, JobSourceModel.key)
            .join(JobSourceModel, JobSourceModel.id == JobOfferSourceModel.source_id)
            .where(JobOfferSourceModel.offer_id.in_(offer_ids))
            .order_by(JobSourceModel.key)
        )
        regroupees: dict[uuid.UUID, list[str]] = defaultdict(list)
        for offer_id, cle in lignes:
            regroupees[offer_id].append(cle)
        return {offer_id: tuple(dict.fromkeys(cles)) for offer_id, cles in regroupees.items()}

    async def get(self, *, owner_id: uuid.UUID, offer_id: uuid.UUID) -> OfferDetail:
        ligne = (
            await self._session.execute(
                _jointure_etat(select(JobOfferModel, JobOfferStateModel.state), owner_id).where(
                    JobOfferModel.id == offer_id, JobOfferModel.owner_id == owner_id
                )
            )
        ).first()
        if ligne is None:
            raise OfferNotFoundError(str(offer_id))
        offre, etat = ligne

        observations = (
            await self._session.execute(
                select(JobOfferSourceModel, JobSourceModel)
                .join(JobSourceModel, JobSourceModel.id == JobOfferSourceModel.source_id)
                .where(
                    JobOfferSourceModel.offer_id == offer_id,
                    JobOfferSourceModel.owner_id == owner_id,
                )
                .order_by(JobSourceModel.key)
            )
        ).all()
        vues = tuple(
            OfferSourceView(
                source_key=source.key,
                source_name=source.name,
                source_url=observation.source_url,
                last_seen_at=observation.last_seen_at,
                still_listed=observation.gone_at is None,
            )
            for observation, source in observations
        )
        return OfferDetail(
            summary=_resume(offre, etat, tuple(dict.fromkeys(v.source_key for v in vues))),
            description=offre.description,
            application_url=offre.application_url,
            language=offre.language,
            expires_at=offre.expires_at,
            first_seen_at=offre.first_seen_at,
            last_seen_at=offre.last_seen_at,
            sources=vues,
        )

    async def set_state(
        self, *, owner_id: uuid.UUID, offer_id: uuid.UUID, state: OfferState | None
    ) -> None:
        existe = await self._session.scalar(
            select(JobOfferModel.id).where(
                JobOfferModel.id == offer_id, JobOfferModel.owner_id == owner_id
            )
        )
        if existe is None:
            raise OfferNotFoundError(str(offer_id))
        if state is None:
            await self._session.execute(
                JobOfferStateModel.__table__.delete().where(  # type: ignore[attr-defined]
                    JobOfferStateModel.owner_id == owner_id,
                    JobOfferStateModel.offer_id == offer_id,
                )
            )
            return
        # Upsert : poser deux fois le même état est sans effet, changer d'état le remplace.
        instruction = insert(JobOfferStateModel).values(
            owner_id=owner_id, offer_id=offer_id, state=state.value
        )
        await self._session.execute(
            instruction.on_conflict_do_update(
                index_elements=["owner_id", "offer_id"],
                set_={"state": state.value, "updated_at": func.now()},
            )
        )
