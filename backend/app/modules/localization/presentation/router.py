"""Routes des préférences et du référentiel géographique (`/api/v1`)."""

from __future__ import annotations

import uuid
import zoneinfo
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, FastAPI, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core.api.dependencies import SessionDep as Session
from app.core.api.dependencies import get_owner_id
from app.core.api.errors import error_response
from app.modules.localization.domain.preferences import (
    SUPPORTED_UI_LANGUAGES,
    InvalidPreferencesError,
    Preferences,
    validate,
)
from app.modules.localization.infrastructure.cldr import BabelGeographyReference
from app.modules.localization.infrastructure.repository import SqlPreferencesRepository

router = APIRouter(prefix="/api/v1", tags=["localization"])

Owner = Annotated[uuid.UUID, Depends(get_owner_id)]
Locale = Annotated[Literal["fr", "en"], Query()]

_REFERENCE = BabelGeographyReference()


def _fuseaux() -> frozenset[str]:
    return frozenset(zoneinfo.available_timezones())


# Code pays ISO 3166-1 alpha-2 ; la casse est normalisée et la valeur vérifiée par le référentiel.
CodePays = Annotated[str, StringConstraints(min_length=2, max_length=2)]


class PreferencesBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ui_language: str = Field(min_length=2, max_length=5)
    country_code: str | None = Field(default=None, max_length=2)
    currency: str | None = Field(default=None, max_length=3)
    timezone: str | None = Field(default=None, max_length=60)
    willing_to_relocate: bool | None = None
    target_countries: list[CodePays] = Field(default_factory=list, max_length=60)
    work_permit_countries: list[CodePays] = Field(default_factory=list, max_length=60)
    needs_sponsorship: bool | None = None


class PreferencesResponse(PreferencesBody):
    supported_ui_languages: list[str]


def _vue(prefs: Preferences) -> PreferencesResponse:
    return PreferencesResponse(
        ui_language=prefs.ui_language,
        country_code=prefs.country_code,
        currency=prefs.currency,
        timezone=prefs.timezone,
        willing_to_relocate=prefs.willing_to_relocate,
        target_countries=list(prefs.target_countries),
        work_permit_countries=list(prefs.work_permit_countries),
        needs_sponsorship=prefs.needs_sponsorship,
        supported_ui_languages=list(SUPPORTED_UI_LANGUAGES),
    )


@router.get("/preferences", response_model=PreferencesResponse)
async def get_preferences(session: Session, owner_id: Owner) -> PreferencesResponse:
    return _vue(await SqlPreferencesRepository(session).get(owner_id))


@router.put("/preferences", response_model=PreferencesResponse)
async def put_preferences(
    session: Session, owner_id: Owner, body: PreferencesBody
) -> PreferencesResponse:
    """Remplace les préférences ; chaque valeur est vérifiée contre le référentiel."""
    prefs = validate(
        Preferences(
            ui_language=body.ui_language,
            country_code=body.country_code,
            currency=body.currency,
            timezone=body.timezone,
            willing_to_relocate=body.willing_to_relocate,
            target_countries=tuple(body.target_countries),
            work_permit_countries=tuple(body.work_permit_countries),
            needs_sponsorship=body.needs_sponsorship,
        ),
        _REFERENCE,
        _fuseaux(),
    )
    await SqlPreferencesRepository(session).save(owner_id, prefs)
    return _vue(prefs)


class CountryView(BaseModel):
    code: str
    name: str
    official_languages: list[str]
    currencies: list[str]


class CurrencyView(BaseModel):
    code: str
    name: str
    symbol: str


@router.get("/reference/countries", response_model=list[CountryView])
async def list_countries(locale: Locale = "fr") -> list[CountryView]:
    """Pays (ISO 3166-1) avec langues officielles et devises, triés par nom."""
    return [
        CountryView(
            code=c.code,
            name=c.name,
            official_languages=list(c.official_languages),
            currencies=list(c.currencies),
        )
        for c in _REFERENCE.countries(locale)
    ]


@router.get("/reference/currencies", response_model=list[CurrencyView])
async def list_currencies(locale: Locale = "fr") -> list[CurrencyView]:
    return [
        CurrencyView(code=d.code, name=d.name, symbol=d.symbol)
        for d in _REFERENCE.currencies(locale)
    ]


@router.get("/reference/timezones", response_model=list[str])
async def list_timezones() -> list[str]:
    """Fuseaux IANA reconnus par le serveur."""
    return sorted(_fuseaux())


def register_localization_errors(application: FastAPI) -> None:
    async def _preferences_invalides(_: Request, erreur: Exception) -> JSONResponse:
        # Messages rédigés par nos soins (jamais d'entrée brute renvoyée telle quelle).
        return error_response(422, "preferences_invalid", str(erreur))

    application.add_exception_handler(InvalidPreferencesError, _preferences_invalides)
