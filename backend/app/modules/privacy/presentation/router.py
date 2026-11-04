"""Routes de confidentialité (EPIC 018) : transparence, export, effacement, conservation.

Rien n'est supprimé sans confirmation saisie ; rien ne quitte la machine : l'export est un
téléchargement local.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import IO, Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, StringConstraints

from app.core.api.dependencies import SessionDep, UnitOfWorkDep, get_owner_id
from app.modules.ai_management.domain.models import PersonalDataPolicy
from app.modules.ai_management.infrastructure.repositories import SqlAIConfigRepository
from app.modules.privacy.domain.ai_transfers import AI_TRANSFERS
from app.modules.privacy.domain.categories import (
    CONFIRMATION_WORD,
    RETENTION_RULES,
    DataCategory,
)
from app.modules.privacy.infrastructure.composition import build_privacy_service

router = APIRouter(prefix="/api/v1/privacy", tags=["privacy"])
Owner = Annotated[uuid.UUID, Depends(get_owner_id)]


class CategoryResponse(BaseModel):
    category: DataCategory
    label: str
    rows: int
    file_bytes: int
    tables: dict[str, int]


class EraseRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    scope: Annotated[str, StringConstraints(min_length=1, max_length=40)]
    """Une catégorie ou `all`."""
    confirmation: Annotated[str, StringConstraints(max_length=40)]
    """Le mot de confirmation, saisi par l'utilisateur."""


class ErasureResponse(BaseModel):
    scope: str
    total_rows: int
    rows_deleted: dict[str, int]
    files_deleted: int
    files_failed: int
    notes: list[str]


class RetentionRuleResponse(BaseModel):
    table: str
    category: DataCategory
    days: int | None
    description: str
    automatic: bool


class PurgeResponse(BaseModel):
    rows_purged: dict[str, int]


class AITransferResponse(BaseModel):
    task_type: str
    purpose: str
    data_sent: str
    never_sent: str
    personal_data: bool
    optional: bool


class PrivacySettingsBody(BaseModel):
    model_config = ConfigDict(frozen=True)

    personal_data_policy: PersonalDataPolicy


class PrivacySettingsResponse(BaseModel):
    personal_data_policy: PersonalDataPolicy
    confirmation_word: str = CONFIRMATION_WORD


@router.get("/summary", response_model=list[CategoryResponse])
async def summary(uow: UnitOfWorkDep, owner_id: Owner) -> list[CategoryResponse]:
    """Ce qui est stocké sur vous, par catégorie."""
    resumes = await build_privacy_service(uow).summary(owner_id=owner_id)
    return [
        CategoryResponse(
            category=r.category,
            label=r.label,
            rows=r.rows,
            file_bytes=r.file_bytes,
            tables=r.tables,
        )
        for r in resumes
    ]


def _lire_et_fermer(fichier: IO[bytes]) -> Iterator[bytes]:
    try:
        while bloc := fichier.read(64 * 1024):
            yield bloc
    finally:
        fichier.close()


@router.get("/export")
async def export_data(uow: UnitOfWorkDep, owner_id: Owner) -> StreamingResponse:
    """Archive ZIP de toutes vos données (JSON par table) et de vos PDF générés."""
    archive = await build_privacy_service(uow).export_zip(owner_id=owner_id)
    return StreamingResponse(
        _lire_et_fermer(archive),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="happly-export.zip"'},
    )


@router.post("/erase", response_model=ErasureResponse)
async def erase(body: EraseRequest, uow: UnitOfWorkDep, owner_id: Owner) -> ErasureResponse:
    """Suppression définitive d'une catégorie ou de tout, après confirmation saisie."""
    rapport = await build_privacy_service(uow).erase(
        owner_id=owner_id, scope=body.scope, confirmation=body.confirmation
    )
    return ErasureResponse(
        scope=rapport.scope,
        total_rows=rapport.total_rows,
        rows_deleted=rapport.rows_deleted,
        files_deleted=rapport.files_deleted,
        files_failed=rapport.files_failed,
        notes=rapport.notes,
    )


@router.get("/retention", response_model=list[RetentionRuleResponse])
async def retention_policy() -> list[RetentionRuleResponse]:
    """Politique de conservation : combien de temps chaque donnée est gardée."""
    return [
        RetentionRuleResponse(
            table=r.table,
            category=r.category,
            days=r.days,
            description=r.description,
            automatic=r.automatic,
        )
        for r in RETENTION_RULES
    ]


@router.post("/retention/purge", response_model=PurgeResponse)
async def purge(uow: UnitOfWorkDep, owner_id: Owner) -> PurgeResponse:
    """Applique maintenant la conservation automatique (données expirées uniquement)."""
    return PurgeResponse(
        rows_purged=await build_privacy_service(uow).purge_expired(owner_id=owner_id)
    )


@router.get("/ai-transfers", response_model=list[AITransferResponse])
async def ai_transfers() -> list[AITransferResponse]:
    """Quelles données partent vers un fournisseur d'IA, pour quel usage."""
    return [AITransferResponse(**t.__dict__) for t in AI_TRANSFERS]


@router.get("/settings", response_model=PrivacySettingsResponse)
async def get_settings_(session: SessionDep, owner_id: Owner) -> PrivacySettingsResponse:
    config = await SqlAIConfigRepository(session).get(owner_id)
    return PrivacySettingsResponse(personal_data_policy=config.personal_data_policy)


@router.put("/settings", response_model=PrivacySettingsResponse)
async def update_settings(
    body: PrivacySettingsBody, session: SessionDep, owner_id: Owner
) -> PrivacySettingsResponse:
    """Politique d'envoi des données personnelles à l'IA : `allowed`, `local_only` ou `never`."""
    depot = SqlAIConfigRepository(session)
    await depot.set_personal_data_policy(owner_id, body.personal_data_policy)
    return PrivacySettingsResponse(personal_data_policy=body.personal_data_policy)
