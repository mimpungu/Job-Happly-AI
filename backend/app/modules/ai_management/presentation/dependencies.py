"""Dépendances FastAPI de la passerelle IA, partagées par les modules qui l'utilisent."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request

from app.core.database.session import UnitOfWork
from app.modules.ai_management.application.gateway import AIGateway
from app.modules.ai_management.application.providers import get_providers
from app.modules.ai_management.domain.provider import AIProvider

Providers = Annotated[list[AIProvider], Depends(get_providers)]


def get_gateway(request: Request, providers: Providers) -> AIGateway:
    """Une passerelle par application : ses verrous doivent survivre aux requêtes."""
    passerelle: AIGateway | None = getattr(request.app.state, "ai_gateway", None)
    if passerelle is None:
        fabrique = getattr(request.app.state, "session_factory", None)
        if fabrique is None:
            raise HTTPException(status_code=503, detail="Base de données non configurée.")
        passerelle = AIGateway(UnitOfWork(fabrique), providers)
        request.app.state.ai_gateway = passerelle
    return passerelle


GatewayDep = Annotated[AIGateway, Depends(get_gateway)]
