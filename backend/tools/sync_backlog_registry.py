"""Synchronise le registre `docs/product/PROJECT_BACKLOG.md` avec le backlog maître.

Le backlog maître fait foi (statut réalisé ou non des EPIC, features et tâches). Ce script ne
modifie que les statuts et les compteurs du registre, jamais le périmètre : une tâche absente du
registre est signalée, pas ajoutée.

Usage : `uv run python tools/sync_backlog_registry.py [--check]`
`--check` n'écrit rien et sort en erreur si le registre est désynchronisé (utilisable en CI).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
MAITRE = RACINE / "docs" / "HAPPLY_AI_MASTER_BACKLOG.md"
REGISTRE = RACINE / "docs" / "product" / "PROJECT_BACKLOG.md"

FAIT = "\u2705"
OUVERT = "\u2796"
STATUT = f"[{FAIT}{OUVERT}]"  # classe de caractères : l'un ou l'autre statut

_EPIC = re.compile(rf"^# \[({STATUT})\] EPIC (\d{{3}}) — ", re.M)
_FEATURE = re.compile(rf"^### \[({STATUT})\] FEATURE (\d{{3}}\.\d+)", re.M)
_TACHE = re.compile(rf"^\[({STATUT})\] \*\*TASK-(\d{{3}}-\d{{2}}) — ", re.M)

_LIGNE_TACHE = re.compile(
    rf"\| \[{STATUT}\] \| TASK-(?P<id>\d{{3}}-\d{{2}}) \|(?P<milieu>[^\n]*)"
    r"\| (?P<etat>[A-Z_]+) \|(?P<fin>[^\n]*)"
)
_TITRE_EPIC = re.compile(rf"^## \[{STATUT}\] EPIC (\d{{3}}) — ", re.M)
_TITRE_FEATURE = re.compile(rf"^### \[{STATUT}\] FEATURE (\d{{3}}\.\d+)", re.M)
_SYNTHESE = re.compile(
    rf"\| \[{STATUT}\] \| (?P<num>\d{{3}}) — (?P<titre>[^|]+?) \| (?P<p>P\d) \| (?P<f>\d+) \| "
    r"(?P<t>\d+) \| \d+ \|"
)


def lire_maitre() -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    texte = MAITRE.read_text(encoding="utf-8")
    return (
        {m[2]: m[1] for m in _EPIC.finditer(texte)},
        {m[2]: m[1] for m in _FEATURE.finditer(texte)},
        {m[2]: m[1] for m in _TACHE.finditer(texte)},
    )


def synchroniser(texte: str) -> tuple[str, list[str]]:
    epics, features, taches = lire_maitre()
    inconnues: list[str] = []

    def tache(m: re.Match[str]) -> str:
        statut = taches.get(m["id"])
        if statut is None:
            inconnues.append(m["id"])
            return m[0]
        etat = m["etat"]
        if statut == FAIT:
            etat = "DONE"
        elif etat == "DONE":
            etat = "BACKLOG"
        return f"| [{statut}] | TASK-{m['id']} |{m['milieu']}| {etat} |{m['fin']}"

    def synthese(m: re.Match[str]) -> str:
        faites = sum(1 for i, s in taches.items() if i.startswith(f"{m['num']}-") and s == FAIT)
        return (
            f"| [{epics.get(m['num'], OUVERT)}] | {m['num']} — {m['titre']} | {m['p']} | "
            f"{m['f']} | {m['t']} | {faites} |"
        )

    texte = _LIGNE_TACHE.sub(tache, texte)
    texte = _TITRE_EPIC.sub(lambda m: f"## [{epics.get(m[1], OUVERT)}] EPIC {m[1]} — ", texte)
    texte = _TITRE_FEATURE.sub(
        lambda m: f"### [{features.get(m[1], OUVERT)}] FEATURE {m[1]}", texte
    )
    return _SYNTHESE.sub(synthese, texte), inconnues


def main() -> int:
    original = REGISTRE.read_text(encoding="utf-8")
    nouveau, inconnues = synchroniser(original)
    if inconnues:
        print("Tâches absentes du backlog maître :", ", ".join(inconnues), file=sys.stderr)
    if "--check" in sys.argv:
        if nouveau != original:
            print("Registre désynchronisé : relancer sans --check.", file=sys.stderr)
            return 1
        return 0
    REGISTRE.write_text(nouveau, encoding="utf-8")
    print("Registre synchronisé.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
