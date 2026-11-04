"""Garde-fous de gouvernance des données : toute nouvelle table ou tâche IA doit être déclarée."""

import ast
from pathlib import Path

from app.core.database.registry import metadata
from app.modules.privacy.domain.ai_transfers import AI_TRANSFERS
from app.modules.privacy.domain.categories import (
    CATEGORY_TABLES,
    RETENTION_RULES,
    SYSTEM_TABLES,
    DataCategory,
)

RACINE_APP = Path(__file__).resolve().parents[3] / "app"


def test_chaque_table_a_proprietaire_est_dans_une_seule_categorie() -> None:
    avec_proprietaire = {t.name for t in metadata.tables.values() if "owner_id" in t.c}
    classees = [t for tables in CATEGORY_TABLES.values() for t in tables]

    assert len(classees) == len(set(classees)), "une table figure dans deux catégories"
    assert avec_proprietaire - SYSTEM_TABLES == set(classees), (
        "Toute table avec owner_id doit être classée dans une catégorie RGPD "
        "(export, conservation, suppression) ou déclarée technique."
    )


def test_toutes_les_categories_sont_renseignees() -> None:
    assert set(CATEGORY_TABLES) == set(DataCategory)


def test_les_regles_de_conservation_visent_des_tables_existantes() -> None:
    for regle in RETENTION_RULES:
        assert regle.table in metadata.tables
        assert (regle.days is None) != regle.automatic or regle.days is not None


def test_chaque_tache_ia_du_code_est_documentee_avec_le_bon_indicateur() -> None:
    """Un appel IA ajouté sans fiche de transfert (données envoyées) fait échouer la CI."""
    trouvees: dict[str, bool] = {}
    for fichier in RACINE_APP.rglob("*.py"):
        for noeud in ast.walk(ast.parse(fichier.read_text(encoding="utf-8"))):
            if not (isinstance(noeud, ast.Call) and getattr(noeud.func, "id", "") == "AIRequest"):
                continue
            options = {k.arg: k.value for k in noeud.keywords}
            tache, perso = options.get("task_type"), options.get("contains_personal_data")
            if isinstance(tache, ast.Constant):
                trouvees[str(tache.value)] = isinstance(perso, ast.Constant) and perso.value is True

    documentees = {t.task_type: t.personal_data for t in AI_TRANSFERS}

    assert trouvees, "aucun appel IA détecté : le motif de recherche est à revoir"
    assert trouvees == documentees
