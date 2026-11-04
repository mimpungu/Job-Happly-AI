"""Découpage d'une section en blocs (une expérience, une formation) ancrés sur leurs dates."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from app.modules.candidate_profile.domain.extraction.dates import DateRange, find_date_range

# Au plus deux lignes d'en-tête situées avant la date (entreprise, intitulé) : au-delà, on
# risquerait d'absorber la description de l'élément précédent.
MAX_LIGNES_AVANT = 2
MAX_LIGNES_ENTETE = 2

_SEPARATEURS_FORTS = re.compile(r"\s+[–—|@]\s+|\s+-\s+|\s*\|\s*|\s+chez\s+|\s+at\s+", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class Block:
    dates: DateRange
    header_pieces: tuple[str, ...]
    """Morceaux de l'en-tête (intitulé, organisation…), dates retirées."""
    bullets: tuple[str, ...]
    prose: tuple[str, ...]
    source_text: str


def est_puce(ligne: str) -> bool:
    return ligne.lstrip().startswith("- ")


def split_blocks(
    lignes: tuple[str, ...], *, is_anchor: Callable[[DateRange], bool]
) -> tuple[Block, ...]:
    ancres: list[tuple[int, DateRange]] = []
    for i, ligne in enumerate(lignes):
        plage = None if est_puce(ligne) else find_date_range(ligne)
        if plage is not None and is_anchor(plage):
            ancres.append((i, plage))
    positions = [i for i, _ in ancres]
    debuts = [_debut_entete(lignes, i, positions) for i in positions]
    blocs = []
    for n, (ancre, plage) in enumerate(ancres):
        fin = debuts[n + 1] if n + 1 < len(ancres) else len(lignes)
        blocs.append(_construire(lignes, debuts[n], ancre, fin, plage))
    return tuple(blocs)


def _debut_entete(lignes: tuple[str, ...], ancre: int, ancres: list[int]) -> int:
    debut = ancre
    while (
        debut > 0
        and ancre - debut < MAX_LIGNES_AVANT
        and lignes[debut - 1].strip()
        and not est_puce(lignes[debut - 1])
        and (debut - 1) not in ancres
        # Une ligne qui suit directement une puce prolonge cette puce, pas l'en-tête suivant.
        and not (debut - 2 >= 0 and est_puce(lignes[debut - 2]) and lignes[debut - 1][:1].islower())
    ):
        debut -= 1
    return debut


def _construire(
    lignes: tuple[str, ...], debut: int, ancre: int, fin: int, plage: DateRange
) -> Block:
    avant = [ligne.strip() for ligne in lignes[debut:ancre]]
    texte_ancre = lignes[ancre]
    reste = (texte_ancre[: plage.span[0]] + " " + texte_ancre[plage.span[1] :]).strip(
        " \t-–—|,;:()"
    )
    entete = [*avant, reste] if reste else list(avant)

    suivant = ancre + 1
    manque = MAX_LIGNES_ENTETE - len(entete)
    # Date entièrement seule (rien avant, rien sur sa ligne) : l'intitulé et l'organisation
    # suivent. Si un en-tête précède la date, ce qui suit est la description.
    if not entete:
        while (
            manque > 0
            and suivant < fin
            and lignes[suivant].strip()
            and not est_puce(lignes[suivant])
        ):
            entete.append(lignes[suivant].strip())
            suivant += 1
            manque -= 1

    puces: list[str] = []
    prose: list[str] = []
    for ligne in lignes[suivant:fin]:
        texte = ligne.strip()
        if not texte:
            continue
        if est_puce(texte):
            puces.append(texte[2:].strip())
        elif puces and texte[:1].islower() and not prose:
            puces[-1] = f"{puces[-1]} {texte}"  # ligne coupée par la mise en page
        else:
            prose.append(texte)

    morceaux = tuple(m for ligne in entete for m in _decouper(ligne))
    source = "\n".join(ligne.strip() for ligne in lignes[debut:fin] if ligne.strip())
    return Block(plage, morceaux, tuple(puces), tuple(prose), source)


def _decouper(ligne: str) -> list[str]:
    return [p.strip(" \t,;:") for p in _SEPARATEURS_FORTS.split(ligne) if p.strip(" \t,;:")]
