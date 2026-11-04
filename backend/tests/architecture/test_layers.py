"""Couches de la Clean Architecture (EPIC 004) : le métier ne touche jamais la base.

- `domain` : aucun framework d'accès aux données ou web (SQLAlchemy, FastAPI, Starlette).
- `application` et `presentation` : aucun appel SQL direct sur une session (`execute`, `scalar`,
  `scalars`) ; les requêtes vivent dans des repositories (`infrastructure`).
Exceptions : liste justifiée ci-dessous.
"""

import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[2] / "app" / "modules"
_FRAMEWORKS_INTERDITS_AU_DOMAINE = {"sqlalchemy", "fastapi", "starlette", "alembic", "psycopg"}
_APPELS_SQL = {"execute", "scalar", "scalars"}

# Types d'exception ou annotations seulement (aucune requête) : tolérés dans `application`.
_IMPORTS_TOLERES_DANS_APPLICATION = {
    "modules/job_discovery/application/ingestion.py": "capture DBAPIError pour rejeter une offre",
    "modules/job_discovery/application/manual_offers.py": "type de la session reçue",
    "modules/notifications/application/runtime.py": "types de la fabrique de sessions (type-check)",
}


def _fichiers(couche: str) -> list[tuple[str, ast.Module]]:
    return [
        (str(p.relative_to(APP.parent)), ast.parse(p.read_text(encoding="utf-8")))
        for p in sorted(APP.glob(f"*/{couche}/**/*.py"))
    ]


def _racines_importees(arbre: ast.Module) -> set[str]:
    racines: set[str] = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            racines |= {a.name.split(".")[0] for a in noeud.names}
        elif isinstance(noeud, ast.ImportFrom) and noeud.module:
            racines.add(noeud.module.split(".")[0])
    return racines


def test_le_domaine_n_importe_aucun_framework_d_acces_aux_donnees_ou_web() -> None:
    fautifs = {
        chemin: sorted(_racines_importees(arbre) & _FRAMEWORKS_INTERDITS_AU_DOMAINE)
        for chemin, arbre in _fichiers("domain")
        if _racines_importees(arbre) & _FRAMEWORKS_INTERDITS_AU_DOMAINE
    }

    assert fautifs == {}


def test_l_application_n_importe_pas_sqlalchemy_hors_exceptions_justifiees() -> None:
    fautifs = [
        chemin
        for chemin, arbre in _fichiers("application")
        if "sqlalchemy" in _racines_importees(arbre)
        and chemin not in _IMPORTS_TOLERES_DANS_APPLICATION
    ]

    assert fautifs == [], "Déplacez la requête dans un repository (infrastructure)."


def test_les_exceptions_justifiees_existent_encore() -> None:
    utilises = {
        chemin
        for chemin, arbre in _fichiers("application")
        if "sqlalchemy" in _racines_importees(arbre)
    }

    assert set(_IMPORTS_TOLERES_DANS_APPLICATION) <= utilises, "exception obsolète à retirer"


def test_ni_l_application_ni_la_presentation_n_executent_de_sql_directement() -> None:
    fautifs: list[str] = []
    for couche in ("application", "presentation"):
        for chemin, arbre in _fichiers(couche):
            for noeud in ast.walk(arbre):
                if (
                    isinstance(noeud, ast.Call)
                    and isinstance(noeud.func, ast.Attribute)
                    and noeud.func.attr in _APPELS_SQL
                    and "session" in ast.unparse(noeud.func.value)
                ):
                    fautifs.append(f"{chemin}:{noeud.lineno} {ast.unparse(noeud.func)}")

    assert fautifs == [], "Les requêtes appartiennent aux repositories."
