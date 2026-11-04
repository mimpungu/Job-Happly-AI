"""Lecture des offres collectées : filtres, tri, pagination côté base, fiche détaillée, états."""

from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Any, cast

from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.job_discovery.domain.enums import OfferState, OfferStatus
from app.modules.job_discovery.domain.multilingual import expand_term
from app.modules.job_discovery.domain.search import (
    OfferDetail,
    OfferFilter,
    OfferNotFoundError,
    OfferPage,
    OfferSort,
    OfferSourceView,
    OfferSummary,
    ScoreContext,
    ScoringUnavailableError,
    StateFilter,
    SuggestionField,
)
from app.modules.job_discovery.domain.text import search_words
from app.modules.job_discovery.infrastructure.models import (
    JobOfferModel,
    JobOfferSourceModel,
    JobOfferStateModel,
    JobSourceModel,
)

# Jointure en lecture seule avec les scores calculés par `job_intelligence` (modèle de lecture) :
# nécessaire pour trier et filtrer côté base sans charger toutes les offres en mémoire.
from app.modules.job_intelligence.infrastructure.models import JobMatchScoreModel

_ECHAPPEMENT = "\\"

# Recherche insensible aux accents sans extension PostgreSQL (`unaccent` exige des droits
# supplémentaires) : `translate` replie les lettres accentuées usuelles, majuscules comprises
# (le `lower()` de la base ne touche que l'ASCII selon sa locale), des deux côtés de la comparaison.
_PLIAGE = {
    **dict.fromkeys("àâäáãåÀÂÄÁÃÅæÆ", "a"),
    **dict.fromkeys("éèêëÉÈÊË", "e"),
    **dict.fromkeys("íìîïÍÌÎÏ", "i"),
    **dict.fromkeys("óòôöõÓÒÔÖÕœŒ", "o"),
    **dict.fromkeys("úùûüÚÙÛÜ", "u"),
    **dict.fromkeys("ýÿÝ", "y"),
    "ç": "c",
    "Ç": "c",
    "ñ": "n",
    "Ñ": "n",
}
_PLIAGE_SOURCE = "".join(_PLIAGE)
_PLIAGE_CIBLE = "".join(_PLIAGE.values())


def _plier(terme: str) -> str:
    """Minuscules sans accents, comme `_replie` côté base ; la ponctuation est conservée."""
    return "".join(_PLIAGE.get(c, c) for c in terme).lower()


def _replie(colonne: Any) -> ColumnElement[str]:
    return cast(
        "ColumnElement[str]",
        func.lower(func.translate(colonne, _PLIAGE_SOURCE, _PLIAGE_CIBLE)),
    )


def _contient(colonne: Any, terme: str) -> ColumnElement[bool]:
    """Contient `terme`, sans casse ni accents ; `%` et `_` saisis restent littéraux."""
    protege = (
        _plier(terme)
        .replace(_ECHAPPEMENT, _ECHAPPEMENT * 2)
        .replace("%", r"\%")
        .replace("_", r"\_")
    )
    return cast("ColumnElement[bool]", _replie(colonne).like(f"%{protege}%", escape=_ECHAPPEMENT))


_COLONNES_TEXTE = (JobOfferModel.title, JobOfferModel.company_name, JobOfferModel.description)


def _condition_texte(texte: str, *, multilingue: bool) -> ColumnElement[bool]:
    """Chaque mot saisi doit figurer (intitulé, entreprise ou description), dans n'importe quel
    ordre : « python développeur » trouve « Développeur Python ». En mode multilingue, chaque mot
    (et la phrase entière) accepte aussi ses équivalents français / anglais."""
    mots = search_words(texte) or [texte]

    def un_terme(terme: str) -> ColumnElement[bool]:
        variantes = expand_term(terme) if multilingue else (terme,)
        return or_(*(_contient(c, v) for v in variantes for c in _COLONNES_TEXTE))

    tous_les_mots = and_(*(un_terme(m) for m in mots))
    if not multilingue or len(mots) == 1:
        return tous_les_mots
    # Phrase connue d'un autre langage (« data analyst » ↔ « analyste de données »).
    equivalents = [v for v in expand_term(texte) if v != texte]
    if not equivalents:
        return tous_les_mots
    return or_(tous_les_mots, *(_contient(c, v) for v in equivalents for c in _COLONNES_TEXTE))


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
        # Les offres sans score passent après les offres notées, pas avant.
        OfferSort.SCORE_DESC: [JobMatchScoreModel.score.desc().nulls_last()],
    }
    return [*ordres[tri], JobOfferModel.id.asc()]


def _conditions(owner_id: uuid.UUID, f: OfferFilter) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = [JobOfferModel.owner_id == owner_id]
    if f.statuses:
        conditions.append(JobOfferModel.status.in_([s.value for s in f.statuses]))
    if f.text:
        conditions.append(_condition_texte(f.text, multilingue=f.multilingual))
    for mot in f.keywords:
        variantes = expand_term(mot) if f.multilingual else (mot,)
        conditions.append(
            or_(
                *(
                    _contient(colonne, v)
                    for v in variantes
                    for colonne in (JobOfferModel.title, JobOfferModel.description)
                )
            )
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
    if f.max_experience_years is not None:
        conditions.append(
            or_(
                JobOfferModel.required_experience_years.is_(None),
                JobOfferModel.required_experience_years <= f.max_experience_years,
            )
        )
    if f.published_since is not None:
        conditions.append(JobOfferModel.published_at >= f.published_since)
    if f.min_score is not None:
        conditions.append(JobMatchScoreModel.score >= f.min_score)
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


def _resume(
    offre: JobOfferModel,
    etat: str | None,
    sources: tuple[str, ...],
    score: Any = None,
    fiabilite: str | None = None,
) -> OfferSummary:
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
        match_score=score,
        match_reliability=fiabilite,
        is_demo=offre.is_demo,
    )


def _jointure_score(requete: Any, owner_id: uuid.UUID, contexte: ScoreContext | None) -> Any:
    """Associe à chaque offre son score (profil validé et poids courants), s'il existe."""
    if contexte is None:
        return requete
    return requete.outerjoin(
        JobMatchScoreModel,
        and_(
            JobMatchScoreModel.offer_id == JobOfferModel.id,
            JobMatchScoreModel.owner_id == owner_id,
            JobMatchScoreModel.profile_id == contexte.profile_id,
            JobMatchScoreModel.weights_version == contexte.weights_version,
        ),
    )


_COLONNE_SUGGESTION: dict[SuggestionField, Any] = {
    SuggestionField.TITLE: JobOfferModel.title,
    SuggestionField.COMPANY: JobOfferModel.company_name,
    SuggestionField.CITY: JobOfferModel.location,
}


class SqlOfferQueryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def suggest(
        self, *, owner_id: uuid.UUID, field: SuggestionField, prefix: str, limit: int
    ) -> list[str]:
        """Valeurs déjà présentes dans les offres actives, les plus fréquentes d'abord.

        Jamais de valeur inventée : on ne propose que ce qui existe dans les offres collectées.
        """
        colonne = _COLONNE_SUGGESTION[field]
        requete = (
            select(colonne, func.count().label("total"))
            .where(
                JobOfferModel.owner_id == owner_id,
                JobOfferModel.status == OfferStatus.ACTIVE.value,
                colonne.is_not(None),
                _contient(colonne, prefix),
            )
            .group_by(colonne)
            .order_by(func.count().desc(), colonne.asc())
            .limit(limit)
        )
        return [valeur for valeur, _ in (await self._session.execute(requete)).all()]

    async def search(
        self,
        *,
        owner_id: uuid.UUID,
        offer_filter: OfferFilter,
        score_context: ScoreContext | None = None,
    ) -> OfferPage:
        demande_un_score = (
            offer_filter.min_score is not None or offer_filter.sort is OfferSort.SCORE_DESC
        )
        if demande_un_score and score_context is None:
            # Pas de profil validé : aucun score n'existe. On le dit plutôt que de renvoyer une
            # liste vide ou un tri arbitraire qui laisserait croire à un classement.
            raise ScoringUnavailableError(
                "Le tri et le filtre par score exigent un profil validé (Espace CV)."
            )
        conditions = _conditions(owner_id, offer_filter)

        base = _filtre_etat(
            _jointure_score(
                _jointure_etat(select(JobOfferModel.id), owner_id), owner_id, score_context
            ),
            offer_filter.state,
        ).where(*conditions)
        total = int(
            await self._session.scalar(select(func.count()).select_from(base.subquery())) or 0
        )

        colonnes: list[Any] = [JobOfferModel, JobOfferStateModel.state]
        if score_context is not None:
            colonnes += [
                JobMatchScoreModel.score,
                JobMatchScoreModel.breakdown["reliability"].as_string(),
            ]
        requete = _filtre_etat(
            _jointure_score(_jointure_etat(select(*colonnes), owner_id), owner_id, score_context),
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
        items = tuple(
            _resume(ligne[0], ligne[1], sources.get(ligne[0].id, ()), *ligne[2:])
            for ligne in lignes
        )
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
            visa_sponsorship=offre.visa_sponsorship,
            work_authorization_required=offre.work_authorization_required,
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
