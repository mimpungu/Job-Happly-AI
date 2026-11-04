"""Mode local sans authentification (ADR-0008, TASK-018-33 et 018-37) : vérifié, pas supposé."""

import re
import subprocess
from pathlib import Path

import pytest

from app.core.config import Settings

RACINE = Path(__file__).resolve().parents[3]


def test_tous_les_ports_docker_sont_publies_sur_la_boucle_locale() -> None:
    compose = (RACINE / "docker-compose.yml").read_text(encoding="utf-8")

    ports = re.findall(r'^\s+-\s+"?([^"\n]*:\d+:\d+)"?\s*$', compose, flags=re.M)

    assert ports, "aucun port trouvé : le motif de recherche est à revoir"
    assert all(p.startswith("127.0.0.1:") for p in ports), (
        f"port exposé hors boucle locale : {ports}"
    )


def test_l_api_ecoute_par_defaut_sur_la_boucle_locale_avec_un_cors_restreint() -> None:
    config = Settings(_env_file=None)

    assert config.host == "127.0.0.1"
    assert config.cors_allowed_origins == ["http://127.0.0.1:3000"]


def test_le_cors_generique_est_refuse() -> None:
    with pytest.raises(ValueError, match="CORS"):
        Settings(cors_allowed_origins=["*"], _env_file=None)


def test_un_modele_local_distant_est_refuse() -> None:
    with pytest.raises(ValueError, match="boucle locale"):
        Settings(ollama_url="http://10.0.0.5:11434", _env_file=None)


def test_la_production_exige_une_base_et_refuse_le_mot_de_passe_d_exemple() -> None:
    with pytest.raises(ValueError):
        Settings(environment="production", _env_file=None)
    with pytest.raises(ValueError, match="exemple"):
        Settings(
            environment="production",
            database_url="postgresql://u:change-me@h/db",
            _env_file=None,
        )


def test_aucun_fichier_d_environnement_ni_cle_n_est_versionne() -> None:
    suivis = subprocess.run(
        ["git", "ls-files"],  # noqa: S607
        cwd=RACINE,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()

    interdits = [
        f
        for f in suivis
        if Path(f).name == ".env"
        or (Path(f).name.startswith(".env.") and f != ".env.example")
        or f.endswith((".pem", ".key"))
    ]

    assert interdits == []


def test_le_modele_d_environnement_ne_contient_aucune_vraie_valeur() -> None:
    exemple = (RACINE / ".env.example").read_text(encoding="utf-8")

    for ligne in exemple.splitlines():
        if ligne.startswith(("HAPPLY_GEMINI_API_KEY", "HAPPLY_FRANCE_TRAVAIL")):
            assert ligne.split("=", 1)[1].strip() == "", (
                f"valeur réelle dans .env.example : {ligne}"
            )
    assert not re.search(r"AIza[0-9A-Za-z_-]{20,}|sk-[0-9A-Za-z]{16,}", exemple)
