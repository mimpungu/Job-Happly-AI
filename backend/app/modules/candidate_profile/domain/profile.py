"""Profil maître : document éditable, règles de validité et différences entre deux états.

Deux niveaux d'exigence, volontairement distincts :

- **brouillon** : tout peut être incomplet (un import ignore parfois l'entreprise ou le mois) ;
  seules les incohérences (période inversée, e-mail mal formé…) sont refusées ;
- **élément validé / profil validé** : complet, et confirmé par l'utilisateur. Rien n'est
  jamais validé à sa place.
"""

from __future__ import annotations

import re
import uuid
from datetime import date
from decimal import Decimal
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.domain.value_objects import (
    CountryCode,
    DomainValueError,
    EmploymentType,
    LanguageCode,
    RemoteType,
    SkillLevel,
)
from app.modules.candidate_profile.domain.enums import DataOrigin, LanguageProficiency

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
MAX_EXPERIENCES = 50
MAX_ITEMS = 300


def _nettoye(valeur: str | None) -> str | None:
    """Texte rogné ; une chaîne vide devient « absent » (jamais un faux texte vide)."""
    return " ".join(valeur.split()) or None if valeur is not None else None


class DocDate(BaseModel):
    """Date de CV : l'année suffit, le mois est facultatif (jamais deviné)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    year: int = Field(ge=1950, le=2100)
    month: int | None = Field(default=None, ge=1, le=12)

    def sort_key(self) -> tuple[int, int]:
        return (self.year, self.month or 1)

    def label(self) -> str:
        return f"{self.year}-{self.month:02d}" if self.month else str(self.year)

    def as_date(self) -> date:
        """Jour de stockage ; la précision (« year »/« month ») dit ce qui est connu."""
        return date(self.year, self.month or 1, 1)

    @property
    def precision(self) -> str:
        return "month" if self.month else "year"

    @classmethod
    def from_storage(cls, jour: date | None, precision: str) -> DocDate | None:
        if jour is None:
            return None
        return cls(year=jour.year, month=jour.month if precision == "month" else None)


class _Item(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: uuid.UUID | None = None
    origin: DataOrigin = DataOrigin.MANUAL
    # Confirmé par l'utilisateur. Un élément importé reste non validé jusqu'à sa relecture.
    validated: bool = False
    # Extrait du document d'origine (traçabilité) ; absent pour une saisie manuelle.
    source_text: str | None = Field(default=None, max_length=4000)


class Identity(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    first_name: str | None = Field(default=None, max_length=120)
    last_name: str | None = Field(default=None, max_length=120)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=40)
    city: str | None = Field(default=None, max_length=120)
    country_code: str | None = None
    headline: str | None = Field(default=None, max_length=200)

    @field_validator("first_name", "last_name", "email", "phone", "city", "headline")
    @classmethod
    def _texte(cls, valeur: str | None) -> str | None:
        return _nettoye(valeur)

    @field_validator("email")
    @classmethod
    def _email_valide(cls, valeur: str | None) -> str | None:
        if valeur is not None and not _EMAIL.match(valeur):
            raise ValueError("Adresse e-mail invalide.")
        return valeur

    @field_validator("country_code")
    @classmethod
    def _pays(cls, valeur: str | None) -> str | None:
        if not valeur:
            return None
        try:
            return CountryCode(valeur).value
        except DomainValueError as erreur:
            raise ValueError(str(erreur)) from erreur


def _periode_coherente(debut: DocDate | None, fin: DocDate | None) -> None:
    if debut and fin and fin.sort_key() < debut.sort_key():
        raise ValueError("La date de fin précède la date de début.")


class ExperienceDoc(_Item):
    title: str | None = Field(default=None, max_length=200)
    company: str | None = Field(default=None, max_length=200)
    location: str | None = Field(default=None, max_length=200)
    start: DocDate | None = None
    end: DocDate | None = None
    is_current: bool = False
    description: str | None = Field(default=None, max_length=5000)
    achievements: tuple[str, ...] = Field(default=(), max_length=50)

    @field_validator("title", "company", "location", "description")
    @classmethod
    def _texte(cls, valeur: str | None) -> str | None:
        return _nettoye(valeur)

    @field_validator("achievements")
    @classmethod
    def _realisations(cls, valeurs: tuple[str, ...]) -> tuple[str, ...]:
        propres = tuple(t for v in valeurs if (t := _nettoye(v)))
        if any(len(t) > 500 for t in propres):
            raise ValueError("Une réalisation dépasse 500 caractères.")
        return propres

    @model_validator(mode="after")
    def _coherence(self) -> Self:
        if self.is_current and self.end is not None:
            raise ValueError("Une expérience en cours n'a pas de date de fin.")
        _periode_coherente(self.start, self.end)
        return self


class EducationDoc(_Item):
    degree: str | None = Field(default=None, max_length=200)
    institution: str | None = Field(default=None, max_length=200)
    field_of_study: str | None = Field(default=None, max_length=200)
    start: DocDate | None = None
    end: DocDate | None = None
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("degree", "institution", "field_of_study", "description")
    @classmethod
    def _texte(cls, valeur: str | None) -> str | None:
        return _nettoye(valeur)

    @model_validator(mode="after")
    def _coherence(self) -> Self:
        _periode_coherente(self.start, self.end)
        return self


class SkillDoc(_Item):
    name: str = Field(min_length=1, max_length=120)
    category: str | None = Field(default=None, max_length=80)
    # Absent = niveau non renseigné (différent de « débutant »).
    level: SkillLevel | None = None

    @field_validator("name")
    @classmethod
    def _nom(cls, valeur: str) -> str:
        nettoye = _nettoye(valeur)
        if nettoye is None:
            raise ValueError("Le nom de la compétence est obligatoire.")
        return nettoye

    @field_validator("category")
    @classmethod
    def _categorie(cls, valeur: str | None) -> str | None:
        return _nettoye(valeur)


class LanguageDoc(_Item):
    language_code: str
    # Absent = niveau inconnu ; « courant » n'est jamais converti en niveau CECR à la place
    # de l'utilisateur, il reste dans `level_text`.
    proficiency: LanguageProficiency | None = None
    level_text: str | None = Field(default=None, max_length=80)

    @field_validator("language_code")
    @classmethod
    def _code(cls, valeur: str) -> str:
        try:
            return LanguageCode(valeur).value
        except DomainValueError as erreur:
            raise ValueError(str(erreur)) from erreur

    @field_validator("level_text")
    @classmethod
    def _texte(cls, valeur: str | None) -> str | None:
        return _nettoye(valeur)


class CertificationDoc(_Item):
    name: str = Field(min_length=1, max_length=200)
    issuer: str | None = Field(default=None, max_length=200)
    issued_on: DocDate | None = None
    expires_on: DocDate | None = None
    credential_url: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def _nom(cls, valeur: str) -> str:
        nettoye = _nettoye(valeur)
        if nettoye is None:
            raise ValueError("Le nom de la certification est obligatoire.")
        return nettoye

    @field_validator("issuer")
    @classmethod
    def _emetteur(cls, valeur: str | None) -> str | None:
        return _nettoye(valeur)

    @field_validator("credential_url")
    @classmethod
    def _url(cls, valeur: str | None) -> str | None:
        if valeur is None or not valeur.strip():
            return None
        if not valeur.lower().startswith(("http://", "https://")):
            raise ValueError("L'URL doit commencer par http:// ou https://.")
        return valeur.strip()

    @model_validator(mode="after")
    def _coherence(self) -> Self:
        _periode_coherente(self.issued_on, self.expires_on)
        return self


class Preferences(BaseModel):
    """Critères de recherche d'emploi du candidat (TASK-005-18)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    job_titles: tuple[str, ...] = Field(default=(), max_length=20)
    country_codes: tuple[str, ...] = Field(default=(), max_length=30)
    cities: tuple[str, ...] = Field(default=(), max_length=30)
    remote_types: tuple[RemoteType, ...] = ()
    employment_types: tuple[EmploymentType, ...] = ()
    salary_min: Decimal | None = Field(default=None, ge=0, le=Decimal("100000000"))
    salary_currency: str | None = None
    application_languages: tuple[str, ...] = Field(default=(), max_length=10)

    @field_validator("job_titles", "cities")
    @classmethod
    def _listes(cls, valeurs: tuple[str, ...]) -> tuple[str, ...]:
        propres = tuple(dict.fromkeys(t for v in valeurs if (t := _nettoye(v))))
        if any(len(t) > 100 for t in propres):
            raise ValueError("Une valeur dépasse 100 caractères.")
        return propres

    @field_validator("country_codes")
    @classmethod
    def _pays(cls, valeurs: tuple[str, ...]) -> tuple[str, ...]:
        try:
            return tuple(dict.fromkeys(CountryCode(v).value for v in valeurs))
        except DomainValueError as erreur:
            raise ValueError(str(erreur)) from erreur

    @field_validator("application_languages")
    @classmethod
    def _langues(cls, valeurs: tuple[str, ...]) -> tuple[str, ...]:
        try:
            return tuple(dict.fromkeys(LanguageCode(v).value for v in valeurs))
        except DomainValueError as erreur:
            raise ValueError(str(erreur)) from erreur

    @field_validator("salary_currency")
    @classmethod
    def _devise(cls, valeur: str | None) -> str | None:
        if valeur is None or not valeur.strip():
            return None
        devise = valeur.strip().upper()
        if len(devise) != 3 or not devise.isalpha():
            raise ValueError(f"Devise invalide : {valeur!r}")
        return devise

    @model_validator(mode="after")
    def _salaire(self) -> Self:
        # 45 000 sans devise ne veut rien dire : même règle que pour la recherche d'offres.
        if self.salary_min is not None and not self.salary_currency:
            raise ValueError("Un salaire souhaité exige une devise.")
        return self


class ProfileDocument(BaseModel):
    """Contenu complet et éditable d'une version du profil maître."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    identity: Identity = Field(default_factory=Identity)
    summary: str | None = Field(default=None, max_length=3000)
    experiences: tuple[ExperienceDoc, ...] = Field(default=(), max_length=MAX_EXPERIENCES)
    educations: tuple[EducationDoc, ...] = Field(default=(), max_length=MAX_ITEMS)
    skills: tuple[SkillDoc, ...] = Field(default=(), max_length=MAX_ITEMS)
    languages: tuple[LanguageDoc, ...] = Field(default=(), max_length=MAX_ITEMS)
    certifications: tuple[CertificationDoc, ...] = Field(default=(), max_length=MAX_ITEMS)
    preferences: Preferences = Field(default_factory=Preferences)

    @field_validator("summary")
    @classmethod
    def _resume(cls, valeur: str | None) -> str | None:
        return _nettoye(valeur)

    @model_validator(mode="after")
    def _doublons(self) -> Self:
        for nom, valeurs in (
            ("compétences", [s.name.casefold() for s in self.skills]),
            ("langues", [lg.language_code for lg in self.languages]),
        ):
            if len(valeurs) != len(set(valeurs)):
                raise ValueError(f"Doublon dans les {nom}.")
        return self


class Issue(BaseModel):
    """Problème de complétude : `path` désigne le champ (ex. `experiences[0].company`)."""

    model_config = ConfigDict(frozen=True)

    path: str
    message: str


def item_issues(document: ProfileDocument, *, only_validated: bool) -> list[Issue]:
    """Éléments incomplets. Avec `only_validated`, seuls ceux marqués validés sont contrôlés
    (un brouillon peut contenir des éléments inachevés, pas des éléments « validés » inachevés)."""
    problemes: list[Issue] = []

    def signaler(actif: bool, chemin: str, champ: str, manquant: bool) -> None:
        if manquant and actif:
            problemes.append(Issue(path=f"{chemin}.{champ}", message="Champ obligatoire."))

    for i, e in enumerate(document.experiences):
        actif = e.validated or not only_validated
        chemin = f"experiences[{i}]"
        signaler(actif, chemin, "title", e.title is None)
        signaler(actif, chemin, "company", e.company is None)
        signaler(actif, chemin, "start", e.start is None)
    for i, f in enumerate(document.educations):
        actif = f.validated or not only_validated
        chemin = f"educations[{i}]"
        signaler(actif, chemin, "degree", f.degree is None)
        signaler(actif, chemin, "institution", f.institution is None)
    for i, lg in enumerate(document.languages):
        signaler(
            lg.validated or not only_validated,
            f"languages[{i}]",
            "proficiency",
            lg.proficiency is None,
        )
    return problemes


def validation_issues(document: ProfileDocument) -> list[Issue]:
    """Ce qui empêche de valider le profil : identité, éléments complets et confirmés."""
    problemes: list[Issue] = []
    if document.identity.first_name is None:
        problemes.append(Issue(path="identity.first_name", message="Prénom obligatoire."))
    if document.identity.last_name is None:
        problemes.append(Issue(path="identity.last_name", message="Nom obligatoire."))
    problemes.extend(item_issues(document, only_validated=False))

    groupes: tuple[tuple[str, tuple[_Item, ...]], ...] = (
        ("experiences", document.experiences),
        ("educations", document.educations),
        ("skills", document.skills),
        ("languages", document.languages),
        ("certifications", document.certifications),
    )
    for nom, elements in groupes:
        for i, element in enumerate(elements):
            if not element.validated:
                problemes.append(
                    Issue(
                        path=f"{nom}[{i}]",
                        message="Élément non confirmé : relisez-le et validez-le.",
                    )
                )
    return problemes


# --- Différences (journal des modifications) -------------------------------------------------


class Change(BaseModel):
    model_config = ConfigDict(frozen=True)

    entity_type: str
    entity_id: uuid.UUID | None
    action: str
    label: str | None
    changes: dict[str, Any]


def _valeurs(modele: BaseModel, exclu: set[str]) -> dict[str, Any]:
    return modele.model_dump(mode="json", exclude=exclu)


def _etiquette(element: BaseModel) -> str | None:
    for champ in ("title", "degree", "name", "language_code"):
        valeur = getattr(element, champ, None)
        if valeur:
            return str(valeur)
    return None


def _delta(avant: dict[str, Any], apres: dict[str, Any]) -> dict[str, Any]:
    champs = avant.keys() | apres.keys()
    return {c: [avant.get(c), apres.get(c)] for c in champs if avant.get(c) != apres.get(c)}


def _changement(
    type_entite: str,
    action: str,
    element: BaseModel | None,
    delta: dict[str, Any],
    *,
    label: str | None = None,
) -> Change:
    identifiant = getattr(element, "id", None)
    return Change(
        entity_type=type_entite,
        entity_id=identifiant,
        action=action,
        label=label or (_etiquette(element) if element is not None else None),
        changes=delta,
    )


_GROUPES = (
    ("experience", "experiences"),
    ("education", "educations"),
    ("skill", "skills"),
    ("language", "languages"),
    ("certification", "certifications"),
)
# Ces champs ne sont pas des modifications de contenu : ils ne génèrent pas d'entrée de journal.
_TECHNIQUES = {"id", "origin", "source_text"}


def diff_documents(ancien: ProfileDocument, nouveau: ProfileDocument) -> list[Change]:
    """Changements entre deux états, élément par élément (appariés par `id`)."""
    changements: list[Change] = []
    for type_entite, avant_m, apres_m in (
        ("identity", ancien.identity, nouveau.identity),
        ("preferences", ancien.preferences, nouveau.preferences),
    ):
        delta = _delta(_valeurs(avant_m, set()), _valeurs(apres_m, set()))
        if delta:
            changements.append(_changement(type_entite, "update", None, delta, label=type_entite))
    if ancien.summary != nouveau.summary:
        delta = {"summary": [ancien.summary, nouveau.summary]}
        changements.append(_changement("summary", "update", None, delta))

    for type_entite, attribut in _GROUPES:
        avant = {e.id: e for e in getattr(ancien, attribut) if e.id}
        apres: tuple[_Item, ...] = getattr(nouveau, attribut)
        presents = {e.id for e in apres if e.id}
        for element in apres:
            if element.id is None or element.id not in avant:
                delta = _delta({}, _valeurs(element, _TECHNIQUES))
                changements.append(_changement(type_entite, "create", element, delta))
                continue
            delta = _delta(_valeurs(avant[element.id], _TECHNIQUES), _valeurs(element, _TECHNIQUES))
            if delta:
                changements.append(_changement(type_entite, "update", element, delta))
        for identifiant, ancien_element in avant.items():
            if identifiant not in presents:
                delta = _delta(_valeurs(ancien_element, _TECHNIQUES), {})
                changements.append(_changement(type_entite, "delete", ancien_element, delta))
    return changements
