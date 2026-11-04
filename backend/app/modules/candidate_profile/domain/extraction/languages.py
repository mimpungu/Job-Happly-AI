"""Langues parlées. Un niveau n'est reconnu que s'il est explicite (CEFR ou langue maternelle)."""

from __future__ import annotations

import re
import unicodedata

from app.modules.candidate_profile.domain.extraction.models import ExtractedLanguage

_LANGUES = {
    "francais": "fr", "french": "fr", "anglais": "en", "english": "en", "espagnol": "es",
    "spanish": "es", "allemand": "de", "german": "de", "italien": "it", "italian": "it",
    "portugais": "pt", "portuguese": "pt", "neerlandais": "nl", "dutch": "nl", "arabe": "ar",
    "arabic": "ar", "chinois": "zh", "chinese": "zh", "mandarin": "zh", "japonais": "ja",
    "japanese": "ja", "russe": "ru", "russian": "ru", "lingala": "ln", "swahili": "sw",
    "turc": "tr", "turkish": "tr", "polonais": "pl", "polish": "pl", "coreen": "ko",
    "korean": "ko", "hindi": "hi", "kikongo": "kg",
}  # fmt: skip
_NATIF = re.compile(
    r"\b(?:natif|native|maternelle|langue maternelle|mother tongue|native speaker"
    r"|bilingue|bilingual)\b"
)
_CECR = re.compile(r"\b([abc][12])\b", re.IGNORECASE)
_SEPARATEURS = re.compile(r"\s*[,;|•·]\s*")
_NIVEAU_TEXTE = re.compile(r"[(:–—-]\s*(?P<niveau>[^()]{2,40})\)?\s*$")


def _sans_accents(texte: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texte) if unicodedata.category(c) != "Mn"
    )


def extract_languages(lignes: tuple[str, ...]) -> tuple[ExtractedLanguage, ...]:
    trouvees: dict[str, ExtractedLanguage] = {}
    for ligne in lignes:
        texte = ligne.strip()
        texte = texte[2:].strip() if texte.startswith("- ") else texte
        if not texte:
            continue
        # Plusieurs langues sur une ligne « Français, Anglais » ; un niveau entre parenthèses
        # contient parfois une virgule, on découpe donc hors parenthèses.
        for morceau in _decouper_hors_parentheses(texte):
            langue = _langue(morceau)
            if langue is None:
                continue
            cle = langue.name.casefold()
            # « Français » puis « Français - C2 » : la mention la plus précise l'emporte.
            if cle not in trouvees or (_sans_niveau(trouvees[cle]) and not _sans_niveau(langue)):
                trouvees[cle] = langue
    return tuple(trouvees.values())


def _sans_niveau(langue: ExtractedLanguage) -> bool:
    return langue.proficiency is None and langue.level_text is None


def _decouper_hors_parentheses(texte: str) -> list[str]:
    profondeur = 0
    courant: list[str] = []
    morceaux: list[str] = []
    for c in texte:
        profondeur += (c == "(") - (c == ")")
        if c in ",;|•·" and profondeur <= 0:
            morceaux.append("".join(courant))
            courant = []
        else:
            courant.append(c)
    morceaux.append("".join(courant))
    return [m.strip() for m in morceaux if m.strip()]


def _langue(morceau: str) -> ExtractedLanguage | None:
    sans = _sans_accents(morceau.lower())
    premier_mot = re.match(r"[a-z]+", sans)
    if premier_mot is None:
        return None
    nom = morceau[: premier_mot.end()]
    # Le nom doit être en tête : « Parle couramment l'anglais » est une phrase, pas une entrée.
    code = _LANGUES.get(premier_mot.group(0))
    if code is None:
        return None
    reste = morceau[premier_mot.end() :]
    niveau_texte = None
    m = _NIVEAU_TEXTE.search(reste)
    if m:
        niveau_texte = m.group("niveau").strip(" )") or None
    elif reste.strip(" :–—-"):
        niveau_texte = reste.strip(" :–—-()") or None

    proficiency: str | None = None
    cecr = _CECR.search(reste)
    if cecr:
        proficiency = cecr.group(1).lower()
    elif _NATIF.search(_sans_accents(reste.lower())):
        proficiency = "native"
    return ExtractedLanguage(nom, code, proficiency, niveau_texte, morceau)
