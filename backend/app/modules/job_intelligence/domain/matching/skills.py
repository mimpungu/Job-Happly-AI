"""Comparaison des compétences du profil et des exigences d'une offre.

Quatre états, jamais confondus (spécification §8) :
- **présente** : la compétence exigée figure dans le profil (ou un synonyme connu) ;
- **partielle** : une compétence proche du même domaine figure dans le profil ;
- **absente** : exigée par l'offre, introuvable dans le profil — ce qui ne prouve pas que la
  personne ne la maîtrise pas, seulement qu'elle n'est pas écrite dans son profil ;
- **non vérifiable** : exigence qu'on ne sait pas comparer (« esprit d'équipe »).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from app.modules.job_intelligence.domain.matching.models import (
    Criterion,
    CriterionResult,
    MatchItem,
    MatchKind,
    ProfileFacts,
    Status,
)
from app.modules.job_intelligence.domain.matching.offer_requirements import (
    Importance,
    OfferRequirements,
    extraire_annees,
    niveau_d_etudes,
)
from app.modules.job_intelligence.domain.matching.text import compact, fold, words

# Synonymes : même compétence écrite autrement (formes compactes, voir `compact`).
_SYNONYMES = {
    "js": "javascript", "ts": "typescript", "postgres": "postgresql", "psql": "postgresql",
    "k8s": "kubernetes", "node": "nodejs", "reactjs": "react", "vuejs": "vue", "golang": "go",
    "msexcel": "excel", "microsoftexcel": "excel", "gcp": "googlecloud", "py": "python",
    "mssql": "sqlserver", "microsoftsqlserver": "sqlserver", "powerbi": "powerbi", "ml": "machinelearning",
    "scikitlearn": "sklearn", "tf": "tensorflow", "dotnet": "net", "csharp": "c#",
}  # fmt: skip

# Équivalents français → anglais de compétences non techniques courantes (TASK-017-13) : un profil
# en français et une offre en anglais (ou l'inverse) doivent se rencontrer. Les noms techniques
# (Python, SQL, Docker…) sont les mêmes dans toutes les langues et n'en ont pas besoin.
_SYNONYMES_MULTILINGUES = {
    "gestiondeprojet": "projectmanagement", "gestiondeprojets": "projectmanagement",
    "conduitedeprojet": "projectmanagement", "travaildequipe": "teamwork",
    "travailenequipe": "teamwork", "espritdequipe": "teamwork",
    "analysededonnees": "dataanalysis",
    "visualisationdedonnees": "datavisualization", "entrepotdedonnees": "datawarehouse",
    "basededonnees": "database", "basesdedonnees": "database",
    "apprentissageautomatique": "machinelearning", "apprentissageprofond": "deeplearning",
    "intelligenceartificielle": "artificialintelligence", "ia": "artificialintelligence",
    "ai": "artificialintelligence", "traitementdulanguagenaturel": "nlp", "tal": "nlp",
    "integrationcontinue": "cicd", "deploiementcontinu": "cicd",
    "methodeagile": "agile", "methodesagiles": "agile", "gestiondeproduit": "productmanagement",
    "relationclient": "customerservice", "serviceclient": "customerservice",
    "negociation": "negotiation", "redaction": "writing", "communicationorale": "communication",
    "gestiondutemps": "timemanagement", "resolutiondeproblemes": "problemsolving",
    "espritdanalyse": "analyticalthinking",
    "cybersecurite": "cybersecurity", "securiteinformatique": "cybersecurity",
    "comptabilite": "accounting", "gestionbudgetaire": "budgeting", "ressourceshumaines": "hr",
    "marketingdigital": "digitalmarketing", "referencementnaturel": "seo",
}  # fmt: skip
_SYNONYMES = {**_SYNONYMES, **_SYNONYMES_MULTILINGUES}

# Familles : une compétence proche, sans être la même, vaut une correspondance partielle.
_FAMILLES: tuple[frozenset[str], ...] = (
    frozenset({"sql", "postgresql", "mysql", "mariadb", "sqlserver", "oracle", "sqlite"}),
    frozenset({"react", "vue", "angular", "svelte"}),
    frozenset({"aws", "azure", "googlecloud"}),
    frozenset({"powerbi", "tableau", "looker", "qlik", "metabase"}),
    frozenset({"python", "r", "julia"}),
    frozenset({"java", "kotlin", "scala"}),
    frozenset({"docker", "kubernetes", "podman"}),
    frozenset({"pandas", "numpy", "polars", "sklearn", "scipy"}),
    frozenset({"spark", "hadoop", "flink", "kafka"}),
    frozenset({"airflow", "dagster", "prefect", "luigi"}),
    frozenset({"tensorflow", "pytorch", "keras"}),
    frozenset({"git", "gitlab", "github", "bitbucket"}),
    frozenset({"excel", "googlesheets", "libreoffice"}),
    frozenset({"jira", "trello", "asana", "confluence"}),
)  # fmt: skip

# Majuscules fréquentes qui ne sont pas des compétences (sigles de contrat, diplômes, etc.).
_SIGLES_IGNORES = {
    "cdi", "cdd", "rh", "pme", "tpe", "usa", "uk", "eu", "tva", "bac", "bts", "dut", "mba", "cv",
    "etp", "rtt", "faq", "pdf", "ok", "ca", "bu", "sas", "sarl", "gmbh", "ltd", "inc", "llc", "ceo",
    "cto", "cfo", "coo", "cio", "ue", "no", "id", "ii", "iii", "iv",
    # Zones géographiques (constatées dans de vraies annonces) : pas des compétences.
    "us", "emea", "apac", "amer", "latam", "dach", "nyc", "sf", "eur", "usd",
}  # fmt: skip

# Abréviations de ponctuation écrites avec un point (« e.g », « i.e ») : le point les ferait
# passer pour des jetons techniques comme `Node.js`.
_ABREVIATIONS = {"e.g", "i.e", "etc", "vs", "approx", "cf", "ex", "n.b", "p.s"}
_MOTS_IGNORES = {
    "vous", "nous", "une", "des", "les", "bac", "master", "licence", "bachelor", "experience",
    "connaissance", "connaissances", "maitrise", "notions", "bonne", "bon", "tres", "esprit",
    "autonomie", "anglais", "francais", "english", "french", "strong", "good", "excellent",
    "knowledge", "ability", "proficiency", "fluent", "france", "paris", "lyon", "europe",
    "janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet", "aout", "septembre",
    "octobre", "novembre", "decembre", "lundi", "mardi", "mercredi", "jeudi", "vendredi",
    "monday", "tuesday", "wednesday", "thursday", "friday", "the", "and", "our", "your",
    "senior", "junior", "bonnes", "capacite", "capacites", "autonome", "rigueur", "curiosite",
    # Mots anglais courants en tête de phrase (constatés dans de vraies annonces).
    "this", "that", "these", "those", "there", "their", "they", "you", "we", "it",
    "with", "from", "have", "will", "can", "about", "also", "must", "should", "would", "who",
    "what", "when", "where", "why", "how", "for", "are", "was", "were", "has", "had", "not",
    "all", "any", "each", "both", "such", "some", "more", "most", "other", "own", "new", "if",
    "as", "at", "by", "in", "of", "on", "to", "an", "or", "so", "but", "be", "do", "is",
}  # fmt: skip

_CONNECTEURS = {"et", "ou", "and", "or", "avec", "with"}
_NON_COMPETENCE = re.compile(r"^(bac\+\d|m[12]|b[1-5]|l[1-3]|bts|dut|but)$")
_JETON = re.compile(r"\.?[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9+#]*(?:[.\-][A-Za-z0-9+#]+)*")
_SEPARATEURS_LISTE = re.compile(r"[,;/]| et | ou | and | or ", re.IGNORECASE)
MAX_MOTS_LIGNE_COURTE = 5
MAX_TERMES_PAR_LIGNE = 12
_POIDS = {
    Importance.MANDATORY: Decimal(2),
    Importance.EXPECTED: Decimal(1),
    Importance.OPTIONAL: Decimal("0.5"),
    Importance.MENTIONED: Decimal("0.5"),
}
_RANG = {
    Importance.MANDATORY: 3,
    Importance.EXPECTED: 2,
    Importance.OPTIONAL: 1,
    Importance.MENTIONED: 0,
}
_SCORE = {
    MatchKind.PRESENT: Decimal(1),
    MatchKind.PARTIAL: Decimal("0.5"),
    MatchKind.ABSENT: Decimal(0),
}


def canonique(nom: str) -> str:
    forme = compact(nom)
    return _SYNONYMES.get(forme, forme)


def _famille(canon: str) -> frozenset[str] | None:
    return next((f for f in _FAMILLES if canon in f), None)


def _est_technique(jeton: str) -> bool:
    return (
        any(c.isdigit() for c in jeton)
        or "+" in jeton
        or "#" in jeton
        or jeton.startswith(".")
        or "." in jeton.strip(".")
    )


def extract_terms(ligne: str, *, strict: bool = False) -> list[str]:
    """Termes ressemblant à des compétences dans une ligne d'exigences.

    - toujours : jetons techniques (`C++`, `.NET`, `Node.js`, `Python3`) et sigles (`SQL`, `AWS`) ;
    - en contexte d'énumération ou de ligne courte seulement : mots capitalisés (`Docker`,
      `Excel`), sauf en tête de phrase — une phrase de prose ne livre pas de compétences ;
    - `strict` (hors rubrique d'exigences) : seuls les jetons techniques et sigles comptent.
    """
    jetons = list(_JETON.finditer(ligne))
    liste = bool(_SEPARATEURS_LISTE.search(ligne)) or len(ligne.split()) <= MAX_MOTS_LIGNE_COURTE

    def eligible(m: re.Match[str], *, tete_autorisee: bool) -> bool:
        jeton = m.group(0)
        plie = fold(jeton)
        if _NON_COMPETENCE.match(plie):
            return False  # « Bac+5 », « M2 » : des diplômes, pas des compétences
        if plie in _ABREVIATIONS:
            return False
        if _est_technique(jeton):
            return True
        if jeton.isupper() and 2 <= len(jeton) <= 8 and jeton.isalpha():
            return plie not in _SIGLES_IGNORES
        if jeton[0].isupper() and len(jeton) >= 2 and not strict and liste:
            return plie not in _MOTS_IGNORES and (m.start() > 0 or tete_autorisee)
        return False

    # Le premier mot d'une phrase est capitalisé sans être un nom propre : il n'est retenu que si
    # la ligne n'est qu'une énumération de compétences (« Kubernetes », « Docker / Git / AWS »).
    # « Dynamisme et rigueur » contient des mots courants : son premier mot est écarté.
    enumeration_pure = all(
        eligible(m, tete_autorisee=True) or fold(m.group(0)) in _CONNECTEURS for m in jetons
    )
    candidats: list[tuple[int, int, str]] = [
        (m.start(), m.end(), m.group(0))
        for m in jetons
        if eligible(m, tete_autorisee=enumeration_pure)
    ]

    termes: list[str] = []
    courant: list[str] = []
    fin_precedente = -1
    for debut, fin, jeton in candidats:
        if courant and ligne[fin_precedente:debut] == " ":
            courant.append(jeton)
        else:
            if courant:
                termes.append(" ".join(courant))
            courant = [jeton]
        fin_precedente = fin
    if courant:
        termes.append(" ".join(courant))
    return termes[:MAX_TERMES_PAR_LIGNE]


def match_term(terme: str, profil: dict[str, str]) -> tuple[MatchKind, str | None]:
    """`profil` associe la forme canonique de chaque compétence à son nom d'origine."""
    canon = canonique(terme)
    if canon in profil:
        return MatchKind.PRESENT, profil[canon]
    mots_terme = words(terme)
    for canon_profil, nom in profil.items():
        mots_profil = words(nom)
        n = len(mots_terme)
        if n > 1 and any(
            mots_profil[i : i + n] == mots_terme for i in range(len(mots_profil) - n + 1)
        ):
            return MatchKind.PRESENT, nom  # « Power BI » dans « Microsoft Power BI »
        famille = _famille(canon)
        if famille is not None and canon_profil in famille:
            return MatchKind.PARTIAL, nom
    return MatchKind.ABSENT, None


class SkillMatcher:
    """Retrouve les compétences du profil citées dans un texte (mots entiers).

    Le motif est compilé une fois pour tout le profil : un seul passage par ligne d'offre, au
    lieu d'une recherche par compétence (ce qui dominait le temps de calcul d'un score).
    """

    def __init__(self, competences: tuple[str, ...]) -> None:
        self._ordre = {nom: i for i, nom in enumerate(competences)}
        self._par_forme = {fold(nom).strip(): nom for nom in competences if fold(nom).strip()}
        formes = sorted(self._par_forme, key=len, reverse=True)  # « c++ » avant « c »
        self._motif = (
            re.compile(
                rf"(?<![a-z0-9+#&])(?:{'|'.join(re.escape(f) for f in formes)})(?![a-z0-9+#&])"
            )
            if formes
            else None
        )

    def find(self, texte: str) -> list[str]:
        if self._motif is None:
            return []
        trouvees = {self._par_forme[m.group(0)] for m in self._motif.finditer(fold(texte))}
        return sorted(trouvees, key=lambda nom: self._ordre[nom])


def skills_in_text(competences: tuple[str, ...], texte: str) -> list[str]:
    """Compétences du profil citées telles quelles dans un texte (mot entier)."""
    return SkillMatcher(competences).find(texte)


@dataclass(frozen=True, slots=True)
class TermAnalysis:
    label: str
    importance: Importance
    kind: MatchKind
    profile_skill: str | None


@dataclass(frozen=True, slots=True)
class SkillAnalysis:
    terms: tuple[TermAnalysis, ...]
    unverifiable: tuple[str, ...]
    result: CriterionResult


_LIBELLE_IMPORTANCE = {
    Importance.MANDATORY: "obligatoire",
    Importance.EXPECTED: "attendue",
    Importance.OPTIONAL: "souhaitée",
    Importance.MENTIONED: "citée",
}


def _termes_de_l_offre(
    exigences: OfferRequirements, profil: dict[str, str], noms: tuple[str, ...]
) -> tuple[dict[str, tuple[str, Importance]], list[str]]:
    """Termes distincts (forme canonique -> libellé, importance la plus forte) et lignes non vérifiables."""
    termes: dict[str, tuple[str, Importance]] = {}
    non_verifiables: list[str] = []
    reperer = SkillMatcher(noms)

    def ajouter(libelle: str, importance: Importance) -> None:
        canon = canonique(libelle)
        existant = termes.get(canon)
        if existant is None or _RANG[importance] > _RANG[existant[1]]:
            termes[canon] = (libelle, importance)

    for ligne in exigences.lines:
        trouves = extract_terms(ligne.text)
        connus = reperer.find(ligne.text)
        for libelle in [*trouves, *connus]:
            ajouter(libelle, ligne.importance)
        # Années d'expérience et diplôme ont leur propre critère : ce ne sont pas des exigences
        # « non vérifiables », juste d'un autre ressort.
        autre_critere = extraire_annees(ligne.text) or niveau_d_etudes(ligne.text) is not None
        if not trouves and not connus and not autre_critere:
            non_verifiables.append(ligne.text)

    for texte_ligne in exigences.body_lines:
        # Hors rubrique d'exigences : une simple mention. Sans rubrique du tout, les sigles et
        # jetons techniques comptent aussi (offres non structurées) ; sinon seules les
        # compétences déjà au profil sont relevées, pour ne pas inventer d'exigences.
        if not exigences.has_requirement_section:
            for libelle in extract_terms(texte_ligne, strict=True):
                ajouter(libelle, Importance.MENTIONED)
        for libelle in reperer.find(texte_ligne):
            ajouter(libelle, Importance.MENTIONED)
    return termes, non_verifiables


def evaluate_skills(
    profil: ProfileFacts, exigences: OfferRequirements, poids: Decimal
) -> SkillAnalysis:
    noms = tuple(dict.fromkeys(s.strip() for s in profil.skills if s.strip()))
    if not noms:
        return SkillAnalysis(
            (),
            (),
            CriterionResult(
                Criterion.SKILLS,
                Status.MISSING_DATA,
                poids,
                None,
                "Votre profil ne contient aucune compétence : impossible de les comparer à l'offre.",
            ),
        )
    index = {canonique(n): n for n in noms}
    termes, non_verifiables = _termes_de_l_offre(exigences, index, noms)
    if not termes:
        return SkillAnalysis(
            (),
            tuple(non_verifiables),
            CriterionResult(
                Criterion.SKILLS,
                Status.MISSING_DATA,
                poids,
                None,
                "L'offre ne cite aucune compétence identifiable automatiquement.",
                items=tuple(MatchItem(MatchKind.UNVERIFIABLE, t) for t in non_verifiables),
            ),
        )

    analyses: list[TermAnalysis] = []
    for libelle, importance in termes.values():
        kind, nom = match_term(libelle, index)
        analyses.append(TermAnalysis(libelle, importance, kind, nom))

    total = sum((_POIDS[a.importance] for a in analyses), Decimal(0))
    obtenu = sum((_POIDS[a.importance] * _SCORE[a.kind] for a in analyses), Decimal(0))
    score = obtenu / total

    items = [
        MatchItem(
            a.kind,
            a.label,
            {
                MatchKind.PRESENT: f"Dans votre profil : {a.profile_skill}",
                MatchKind.PARTIAL: (
                    f"Compétence transférable : vous maîtrisez « {a.profile_skill} » (même famille). "
                    "À valoriser sans prétendre maîtriser celle de l'offre."
                ),
                MatchKind.ABSENT: f"Compétence {_LIBELLE_IMPORTANCE[a.importance]}, non trouvée dans votre profil",
            }[a.kind],
        )
        for a in analyses
    ]
    items.extend(
        MatchItem(MatchKind.UNVERIFIABLE, t, "À évaluer vous-même") for t in non_verifiables
    )

    comptes = {
        k: sum(1 for a in analyses if a.kind is k)
        for k in (MatchKind.PRESENT, MatchKind.PARTIAL, MatchKind.ABSENT)
    }
    explication = (
        f"{comptes[MatchKind.PRESENT]} compétence(s) présente(s), {comptes[MatchKind.PARTIAL]} partielle(s), "
        f"{comptes[MatchKind.ABSENT]} absente(s) de votre profil sur {len(analyses)} repérée(s) dans l'offre."
    )
    if comptes[MatchKind.PARTIAL]:
        transferables = ", ".join(
            f"{a.label} (via {a.profile_skill})" for a in analyses if a.kind is MatchKind.PARTIAL
        )
        explication += f" Compétence(s) transférable(s) à valoriser : {transferables}."
    if comptes[MatchKind.ABSENT]:
        explication += " Une compétence « absente » n'est pas forcément absente chez vous : complétez votre profil si besoin."
    return SkillAnalysis(
        tuple(analyses),
        tuple(non_verifiables),
        CriterionResult(
            Criterion.SKILLS, Status.EVALUATED, poids, score, explication, items=tuple(items)
        ),
    )
