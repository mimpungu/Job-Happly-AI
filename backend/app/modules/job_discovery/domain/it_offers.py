"""Reconnaissance par règles des offres informatiques (aucune IA).

Choix : on se fonde sur l'intitulé, pas sur la description — presque toute annonce d'une
entreprise tech y mentionne « software » ou « data ». Les règles sont volontairement
explicites et limitées : une offre au titre atypique peut être manquée (limite documentée).
"""

from __future__ import annotations

import re

from app.modules.job_discovery.domain.text import normalize_text

_MOTIFS = (
    r"\b(software|logiciel|developpeu[rs]e?s?|developer|programm?er|programmeur)\b",
    r"\b(devops|devsecops|sre|site reliability|platform engineer|cloud engineer)\b",
    r"\b(back ?end|front ?end|full ?stack|mobile (engineer|developer)|ios|android)\b",
    r"\bdata (scientist|engineer|analyst|architect|platform)\b",
    r"\b(machine learning|ml engineer|ai engineer|ia|intelligence artificielle)\b",
    r"\b(cyber ?securit[ey]|security engineer|ingenieur securite|pentest)\b",
    r"\b(informatique|systemes? d'information|si|it)\b",
    r"\b(qa engineer|test automation|sdet|ingenieur (de )?tests?)\b",
    r"\b(solutions? architect|architecte (logiciel|solution|si|technique)|technical architect)\b",
    r"\b(sysadmin|administrateur (systemes?|reseaux?)|network engineer|infrastructure engineer)\b",
    r"\b(engineering manager|tech lead|cto)\b",
    r"\b(ingenieur (developpement|logiciel|etudes)|chef de projet (it|informatique|si))\b",
)
_REGEX = re.compile("|".join(_MOTIFS))
_EXCLUSIONS = re.compile(r"\b(sales|commercial|account|recruit\w*|talent|legal|finance)\b")


def is_it_offer(title: str) -> bool:
    """Vrai si l'intitulé relève de l'informatique (métiers commerciaux ou RH exclus)."""
    texte = normalize_text(title)
    return bool(_REGEX.search(texte)) and not _EXCLUSIONS.search(texte)
