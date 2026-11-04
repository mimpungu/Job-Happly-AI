"""Surface d'attaque contrôlée par la CI (EPIC 018 : injections, SSRF, secrets).

Ces tests ne prouvent pas l'absence de faille ; ils empêchent qu'une nouvelle surface sensible
(connexion sortante, processus, SQL assemblé, secret en clair) apparaisse sans revue explicite.
"""

import ast
from pathlib import Path

from app.core.config import Settings

APP = Path(__file__).resolve().parents[2] / "app"

# Modules autorisés à ouvrir des connexions sortantes (httpx), avec la protection appliquée.
_SORTANT: dict[str, str] = {
    "modules/ai_management/infrastructure/gemini.py": "hôte HTTPS fixe ; clé en SecretStr",
    "modules/ai_management/infrastructure/ollama.py": "URL de boucle locale imposée par la config",
    "modules/job_discovery/infrastructure/http.py": "client unique, en-têtes honnêtes",
    "modules/job_discovery/infrastructure/public_pages.py": "ensure_public_url + robots.txt",
    "modules/job_discovery/infrastructure/france_travail.py": "hôtes officiels fixes",
    "modules/job_discovery/infrastructure/ats/discovery.py": "hôtes ATS fixes (liste blanche)",
    "modules/job_discovery/infrastructure/ats/greenhouse.py": "hôte ATS fixe",
    "modules/job_discovery/infrastructure/ats/lever.py": "hôtes ATS fixes",
    "modules/job_discovery/infrastructure/ats/ashby.py": "hôte ATS fixe ; jeton validé",
    "modules/job_discovery/infrastructure/ats/workable.py": "hôte ATS fixe ; jeton validé ; "
    "la redirection 302 de l'adresse documentée n'est jamais suivie",
    "modules/job_discovery/application/collection.py": "type de client uniquement",
    "modules/job_discovery/application/target_connectors.py": "type de client uniquement",
    "modules/job_discovery/application/company_resolution.py": "type de client uniquement ; "
    "la découverte passe par ats/discovery.py (hôtes ATS fixes)",
    "modules/job_discovery/infrastructure/search_sources.py": "type de client uniquement ; "
    "seules les sources officielles configurées sont construites",
}
# Modules autorisés à lancer un processus.
_PROCESSUS: dict[str, str] = {
    "modules/document_generation/infrastructure/latex_compiler.py": (
        "pdfLaTeX isolé : liste noire, mode paranoïaque, env minimal, rlimits, unshare réseau"
    ),
}
_APPELS_INTERDITS = {"eval", "exec", "compile", "__import__"}
_MODULES_INTERDITS = {"pickle", "marshal", "shelve", "telnetlib", "ftplib"}


def _sources() -> list[tuple[str, ast.Module]]:
    return [
        (str(p.relative_to(APP)), ast.parse(p.read_text(encoding="utf-8")))
        for p in sorted(APP.rglob("*.py"))
    ]


def _importe(arbre: ast.Module, nom: str) -> bool:
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import) and any(a.name.split(".")[0] == nom for a in noeud.names):
            return True
        if isinstance(noeud, ast.ImportFrom) and (noeud.module or "").split(".")[0] == nom:
            return True
    return False


def test_les_connexions_sortantes_sont_toutes_declarees() -> None:
    utilisateurs = {chemin for chemin, arbre in _sources() if _importe(arbre, "httpx")}

    assert utilisateurs == set(_SORTANT), (
        "Un module ouvre (ou n'ouvre plus) des connexions sortantes : mettez à jour la liste "
        "après revue SSRF (HTTPS, hôte fixe ou ensure_public_url)."
    )


def test_aucune_bibliotheque_reseau_alternative() -> None:
    for chemin, arbre in _sources():
        for nom in ("requests", "urllib3", "aiohttp", "socket", "smtplib"):
            if chemin.endswith(("http.py",)) and nom == "socket":
                continue  # résolution DNS de ensure_public_url
            if chemin.endswith("email_sender.py") and nom == "smtplib":
                continue  # envoi de notifications : hôte configuré par l'utilisateur
            assert not _importe(arbre, nom), f"{chemin} importe {nom} sans revue"


def test_les_processus_sont_lances_uniquement_par_le_compilateur_latex() -> None:
    utilisateurs = {chemin for chemin, arbre in _sources() if _importe(arbre, "subprocess")}

    assert utilisateurs == set(_PROCESSUS)


def test_aucun_shell_ni_eval_ni_deserialisation_dangereuse() -> None:
    for chemin, arbre in _sources():
        for module in _MODULES_INTERDITS:
            assert not _importe(arbre, module), f"{chemin} importe {module}"
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Call):
                nom = getattr(noeud.func, "id", None)
                assert nom not in _APPELS_INTERDITS, f"{chemin}:{noeud.lineno} appelle {nom}()"
                for mot_cle in noeud.keywords:
                    assert not (
                        mot_cle.arg == "shell"
                        and isinstance(mot_cle.value, ast.Constant)
                        and mot_cle.value.value is True
                    ), f"{chemin}:{noeud.lineno} shell=True"
                attribut = getattr(noeud.func, "attr", "")
                proprietaire = getattr(getattr(noeud.func, "value", None), "id", "")
                assert not (proprietaire == "os" and attribut in {"system", "popen"}), (
                    f"{chemin}:{noeud.lineno} os.{attribut}"
                )
                assert not (proprietaire == "yaml" and attribut == "load"), (
                    f"{chemin}:{noeud.lineno} yaml.load non sûr"
                )


def test_aucun_sql_assemble_par_concatenation_ou_f_string() -> None:
    """Toute requête passe par l'ORM ou des paramètres liés (TASK-018-08)."""
    for chemin, arbre in _sources():
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.Call):
                continue
            nom = getattr(noeud.func, "id", getattr(noeud.func, "attr", ""))
            if nom not in {"text", "execute"} or not noeud.args:
                continue
            argument = noeud.args[0]
            dynamique = isinstance(argument, ast.JoinedStr) or (
                isinstance(argument, ast.BinOp) and isinstance(argument.op, ast.Add | ast.Mod)
            )
            appel_format = (
                isinstance(argument, ast.Call) and getattr(argument.func, "attr", "") == "format"
            )
            assert not (dynamique or appel_format), (
                f"{chemin}:{noeud.lineno} SQL construit dynamiquement"
            )


def test_les_secrets_de_configuration_sont_des_secretstr() -> None:
    """Un secret en `str` apparaîtrait dans `repr()` et les logs."""
    for nom, champ in Settings.model_fields.items():
        if any(mot in nom for mot in ("key", "secret", "password", "token")):
            annotation = str(champ.annotation)
            assert "SecretStr" in annotation, f"{nom} doit être un SecretStr"


def test_la_config_ne_publie_aucun_secret_dans_repr() -> None:
    config = Settings(
        gemini_api_key="AIzaSyA1234567890abcdefghij",
        database_url="postgresql://u:motdepasse@127.0.0.1/db",
    )

    texte = repr(config) + str(config.model_dump())

    assert "AIzaSyA1234567890" not in texte
    assert "motdepasse" not in texte


def test_chaque_appel_ia_declare_ses_donnees_personnelles_et_exige_une_sortie_structuree() -> None:
    """TASK-018-12 et 018-13 : `contains_personal_data` n'est jamais implicite, la sortie est
    toujours décrite par un schéma JSON (et validée par la passerelle)."""
    requetes = 0
    for chemin, arbre in _sources():
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Call) and getattr(noeud.func, "id", "") == "AIRequest":
                if chemin.endswith("ai_management/domain/models.py"):
                    continue
                requetes += 1
                options = {k.arg for k in noeud.keywords}
                assert "contains_personal_data" in options, f"{chemin}:{noeud.lineno} implicite"
                assert "json_schema" in options, f"{chemin}:{noeud.lineno} sans schéma de sortie"

    assert requetes >= 5, "aucune requête IA détectée : le motif de recherche est à revoir"
