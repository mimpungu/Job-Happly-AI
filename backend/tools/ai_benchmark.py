"""Banc d'essai des modèles IA sur de vraies offres publiques (outil de développement).

Usage (depuis la racine du dépôt, API lancée) :
    PYTHONPATH=backend uv run --project backend python backend/tools/ai_benchmark.py --n 20
    PYTHONPATH=backend uv run --project backend python backend/tools/ai_benchmark.py --n 20 --gemini

Chaque appel passe par AIGateway : journal, plafonds et cache s'appliquent comme en production.
Gemini n'est interrogé qu'avec --gemini : les textes d'offres (publics) partent alors chez Google
(palier gratuit : contenus réutilisables). Aucun CV ni donnée personnelle n'est jamais envoyé.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import time
import urllib.request
import uuid
from collections import Counter
from pathlib import Path

from pydantic import BaseModel, ValidationError
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database.session import UnitOfWork, create_engine, create_session_factory
from app.modules.ai_management.application.benchmark import (
    Run,
    estimated_cost,
    grounded_ratio,
    jaccard,
    summarize,
)
from app.modules.ai_management.application.gateway import AIGateway
from app.modules.ai_management.application.providers import build_providers
from app.modules.ai_management.domain.errors import AIError
from app.modules.ai_management.domain.models import AIRequest
from app.modules.ai_management.domain.provider import AIProvider
from app.modules.platform.infrastructure.models import UserModel

API = "http://127.0.0.1:8000/api/v1"
SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "skills": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "skills"],
}
INSTRUCTIONS = (
    "Résume l'offre d'emploi en deux phrases au maximum et liste uniquement les compétences "
    "techniques citées explicitement dans le texte (n'en ajoute aucune). "
    "Réponds en JSON avec les clés summary et skills."
)
# Tarifs payants publiés (USD / million de tokens), pour estimer un coût même au palier gratuit.
TARIFS = {"gemini-3.1-flash-lite": (0.25, 1.50), "gemini-3-flash-preview": (0.50, 3.00)}


class Sortie(BaseModel):
    summary: str
    skills: list[str]


def valider(brut: object) -> Sortie:
    try:
        return Sortie.model_validate(brut)
    except ValidationError as erreur:
        raise ValueError(str(erreur)) from erreur


def _get(chemin: str) -> dict[str, object]:
    with urllib.request.urlopen(f"{API}{chemin}", timeout=30) as reponse:  # noqa: S310 - local
        return json.load(reponse)  # type: ignore[no-any-return]


def echantillon(n: int, graine: int) -> list[dict[str, object]]:
    """Offres variées (tirage reproductible), avec leur description complète."""
    page = _get("/offers?page_size=100")
    items = list(page["items"])  # type: ignore[call-overload]
    random.Random(graine).shuffle(items)  # noqa: S311 - tirage reproductible, pas de cryptographie
    detailles = []
    for o in items[:n]:
        detail = _get(f"/offers/{o['id']}")
        # Le détail ne répète pas le titre ni l'entreprise : ils viennent de la liste.
        detailles.append({**detail, "title": o["title"], "company_name": o["company_name"]})
    return detailles


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=20)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument(
        "--gemini", action="store_true", help="envoie les offres (publiques) à Gemini"
    )
    parser.add_argument("--out", type=Path, default=Path("benchmark.md"))
    parser.add_argument(
        "--pause",
        type=float,
        default=0.0,
        help="secondes d'attente après chaque appel réel (quota du palier gratuit)",
    )
    parser.add_argument(
        "--models",
        nargs="*",
        help="restreint aux modèles listés (ex. gemma4:e4b gemini-3.1-flash-lite)",
    )
    args = parser.parse_args()

    reglages = get_settings()
    if reglages.database_url is None:
        raise SystemExit("HAPPLY_DATABASE_URL est absent.")
    fournisseurs = [p for p in build_providers(reglages) if args.gemini or p.name != "gemini"]
    if not fournisseurs:
        raise SystemExit("Aucun fournisseur configuré.")
    moteur = create_engine(reglages.database_url)
    uow = UnitOfWork(create_session_factory(moteur))
    async with uow.begin() as session:
        owner = (await session.execute(select(UserModel.id).limit(1))).scalar_one()

    offres = echantillon(args.n, args.seed)
    print(f"{len(offres)} offres, fournisseurs : {[p.name for p in fournisseurs]}", flush=True)
    resultats: dict[str, list[Run]] = {}
    sorties: dict[str, list[list[str]]] = {}
    for fournisseur in fournisseurs:
        for niveau in (1, 2):
            modele = fournisseur.model_for(niveau, "economy")
            if modele is None:
                continue
            nom = f"{fournisseur.name}:{modele}"
            if args.models and modele not in args.models:
                continue
            pause = args.pause if fournisseur.kind.value == "api" else 0.0
            resultats[nom], sorties[nom] = await executer(
                uow, owner, fournisseur, niveau, offres, pause
            )
            s = summarize(resultats[nom])
            print(
                f"{nom}: valides {s.valid_rate:.0%}, médiane {s.median_seconds:.1f}s, "
                f"p90 {s.p90_seconds:.1f}s, ancrage {s.mean_grounded or 0:.0%}",
                flush=True,
            )
            erreurs = Counter(r.error for r in resultats[nom] if r.error)
            for message, nombre in erreurs.most_common(3):
                print(f"    {nombre} fois : {message}", flush=True)
    await moteur.dispose()
    ecrire(args.out, offres, resultats, sorties)
    print(f"Comparaison écrite dans {args.out}")


async def executer(
    uow: UnitOfWork,
    owner: uuid.UUID,
    fournisseur: AIProvider,
    niveau: int,
    offres: list[dict[str, object]],
    pause: float = 0.0,
) -> tuple[list[Run], list[list[str]]]:
    passerelle = AIGateway(uow, [fournisseur], timeout=240.0)
    runs: list[Run] = []
    competences: list[list[str]] = []
    for offre in offres:
        texte = str(offre.get("description") or "")[:3500]
        contenu = (
            f"Intitulé : {offre.get('title')}\nEntreprise : {offre.get('company_name')}\n\n{texte}"
        )
        requete = AIRequest(
            "benchmark_offer", niveau, "bench-v1", INSTRUCTIONS, contenu, 500, SCHEMA
        )
        debut = time.monotonic()
        try:
            r = await passerelle.run(owner_id=owner, request=requete, validate=valider)
        except AIError as erreur:
            runs.append(Run(False, time.monotonic() - debut, error=str(erreur)))
            competences.append([])
            continue
        duree = time.monotonic() - debut
        if pause and not r.cache_hit:
            await asyncio.sleep(pause)  # respecte le quota par minute du palier gratuit
        runs.append(
            Run(
                True,
                duree,
                r.input_tokens,
                r.output_tokens,
                r.value.skills,
                grounded_ratio(r.value.skills, contenu),
            )
        )
        competences.append(r.value.skills)
    return runs, competences


def ecrire(
    chemin: Path,
    offres: list[dict[str, object]],
    resultats: dict[str, list[Run]],
    sorties: dict[str, list[list[str]]],
) -> None:
    lignes = [
        "# Banc d'essai IA",
        "",
        "| Modèle | JSON valide | Médiane | p90 | Ancrage* | Compétences/offre | Tokens (e/s) "
        "| Coût au tarif payant |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for nom, runs in resultats.items():
        s = summarize(runs)
        tarif = TARIFS.get(nom.split(":", 1)[1])
        cout = f"{estimated_cost(s, *tarif):.4f} $" if tarif else "0 (local)"
        ancrage = f"{s.mean_grounded:.0%}" if s.mean_grounded is not None else "—"
        lignes.append(
            f"| {nom} | {s.valid_rate:.0%} | {s.median_seconds:.1f}s | {s.p90_seconds:.1f}s | "
            f"{ancrage} | {s.mean_skills:.1f} | {s.input_tokens}/{s.output_tokens} | {cout} |"
        )
    lignes += [
        "",
        "*Ancrage : part des compétences citées réellement présentes dans le texte "
        "(bas = invention).",
        "",
    ]
    noms = list(resultats)
    if len(noms) > 1:
        lignes += ["## Accord entre modèles (recouvrement moyen des compétences)", ""]
        for i, a in enumerate(noms):
            for b in noms[i + 1 :]:
                accords = [jaccard(x, y) for x, y in zip(sorties[a], sorties[b], strict=True)]
                lignes.append(f"- {a} ↔ {b} : {sum(accords) / len(accords):.0%}")
        lignes.append("")
    lignes += ["## À relire (5 premières offres)", ""]
    for index, offre in enumerate(offres[:5]):
        lignes += [f"### {offre.get('title')} — {offre.get('company_name')}", ""]
        for nom in noms:
            lignes.append(f"- **{nom}** : {', '.join(sorties[nom][index]) or '(aucune)'}")
        lignes.append("")
    chemin.write_text("\n".join(lignes), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
