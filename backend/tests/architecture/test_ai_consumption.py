"""Réduction de la consommation IA (TASK-010-32) : garde-fous vérifiés par la CI.

L'IA est un enrichissement : chaque tâche a un traitement déterministe qui fonctionne sans elle,
une sortie JSON à schéma strict et une sortie bornée. Une nouvelle tâche qui ne respecte pas ces
règles fait échouer la CI.
"""

import ast
from pathlib import Path

from app.modules.ai_management.domain.estimate_profiles import ESTIMATE_PROFILES
from app.modules.privacy.domain.ai_transfers import AI_TRANSFERS

APP = Path(__file__).resolve().parents[2] / "app"
# Outils de diagnostic ou de calcul local : ils n'ont pas de repli « sans IA » à proposer.
_SANS_REPLI = {"platform_test", "estimate"}


def _appels_ia() -> list[tuple[str, dict[str, ast.expr]]]:
    appels: list[tuple[str, dict[str, ast.expr]]] = []
    for fichier in APP.rglob("*.py"):
        for noeud in ast.walk(ast.parse(fichier.read_text(encoding="utf-8"))):
            if isinstance(noeud, ast.Call) and getattr(noeud.func, "id", "") == "AIRequest":
                options = {k.arg: k.value for k in noeud.keywords if k.arg}
                tache = options.get("task_type")
                if isinstance(tache, ast.Constant):
                    appels.append((str(tache.value), options))
    return appels


def test_chaque_tache_ia_a_un_traitement_deterministe_de_niveau_zero() -> None:
    documentees = {t.task_type for t in AI_TRANSFERS} - _SANS_REPLI

    assert documentees == set(ESTIMATE_PROFILES), (
        "Toute tâche IA doit déclarer, dans ESTIMATE_PROFILES, le traitement sans IA qui la "
        "remplace (niveau 0) et ses bornes de coût."
    )
    assert all(p.baseline.strip() for p in ESTIMATE_PROFILES.values())


def test_chaque_appel_ia_exige_une_sortie_json_stricte_et_bornee() -> None:
    appels = _appels_ia()

    assert appels, "aucun appel IA détecté : le motif de recherche est à revoir"
    for tache, options in appels:
        if tache == "estimate":
            continue  # calcul de coût : aucun modèle n'est appelé
        schema = options.get("json_schema")
        assert schema is not None, f"{tache} : schéma JSON absent"
        assert not (isinstance(schema, ast.Constant) and schema.value is None), (
            f"{tache} : sortie libre interdite, le schéma JSON est obligatoire"
        )
        assert "max_output_tokens" in options, f"{tache} : sortie non bornée"


def test_les_bornes_d_estimation_couvrent_les_sorties_declarees() -> None:
    for tache, options in _appels_ia():
        profil = ESTIMATE_PROFILES.get(tache)
        sortie = options.get("max_output_tokens")
        if profil is not None and isinstance(sortie, ast.Constant):
            assert sortie.value <= profil.max_output_tokens, (
                f"{tache} : la sortie réelle dépasse celle utilisée pour estimer le coût"
            )
