"""Recherche multilingue (TASK-008-10) : équivalents français ↔ anglais des termes d'emploi.

Choix assumé : un lexique fermé et revu à la main, déterministe et sans coût (niveau 0), plutôt
qu'une traduction automatique. Il couvre les intitulés et types de contrat courants ; un terme
inconnu n'est jamais « deviné » : il est cherché tel quel.
"""

from __future__ import annotations

from app.modules.job_discovery.domain.text import normalize_text

# Chaque groupe réunit des termes équivalents (toutes langues). Ordre sans importance.
_GROUPES: tuple[tuple[str, ...], ...] = (
    ("développeur", "developpeur", "developer", "software engineer", "programmeur"),
    ("ingénieur", "ingenieur", "engineer"),
    ("ingénieur logiciel", "software engineer"),
    ("analyste de données", "data analyst", "analyste data"),
    ("data scientist", "scientifique des données"),
    ("ingénieur données", "data engineer"),
    ("chef de projet", "project manager"),
    ("product owner", "responsable produit", "product manager"),
    ("designer", "concepteur", "graphiste"),
    ("comptable", "accountant"),
    ("commercial", "sales"),
    ("responsable", "manager"),
    ("directeur", "director", "head of"),
    ("stagiaire", "intern", "internship", "stage"),
    ("alternance", "apprenticeship", "apprentice"),
    ("apprenti", "apprentice"),
    ("testeur", "tester", "qa engineer"),
    ("administrateur système", "administrateur systeme", "system administrator", "sysadmin"),
    ("réseau", "reseau", "network"),
    ("sécurité", "securite", "security"),
    ("marketing", "mercatique"),
    ("ressources humaines", "human resources"),
    ("support client", "customer support", "service client", "customer service"),
    ("juriste", "legal counsel", "lawyer"),
    ("infirmier", "infirmière", "nurse"),
    ("télétravail", "teletravail", "remote"),
    ("temps partiel", "part-time", "part time"),
    ("temps plein", "full-time", "full time"),
)

_INDEX: dict[str, tuple[str, ...]] = {}
for _groupe in _GROUPES:
    for _terme in _groupe:
        _cle = normalize_text(_terme)
        _INDEX[_cle] = tuple(dict.fromkeys((*_INDEX.get(_cle, ()), *_groupe)))


def expand_term(terme: str) -> tuple[str, ...]:
    """Le terme lui-même, puis ses équivalents d'une autre langue (sans doublon).

    Seul un terme **entier** du lexique est étendu ; les mots composés sont traités mot à mot
    par l'appelant s'il le souhaite. Un terme inconnu est renvoyé seul.
    """
    brut = terme.strip()
    if not brut:
        return ()
    equivalents = _INDEX.get(normalize_text(brut), ())
    return tuple(dict.fromkeys((brut, *equivalents)))
