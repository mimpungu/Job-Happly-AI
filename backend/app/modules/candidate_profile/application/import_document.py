"""Cas d'usage : lire un CV importé et en produire un texte propre."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import replace

from app.modules.candidate_profile.domain.documents import (
    MIN_USEFUL_CHARS,
    EmptyDocumentError,
    ExtractedText,
)
from app.modules.candidate_profile.domain.text_normalization import normalize_document_text

# Contrat de l'extracteur (nom du fichier, contenu) -> texte brut ; implémenté en infrastructure.
Extractor = Callable[[str, bytes], ExtractedText]


class DocumentReader:
    def __init__(self, extractor: Extractor) -> None:
        self._extractor = extractor

    async def read(self, filename: str, content: bytes) -> ExtractedText:
        """Extrait puis normalise le texte, sans jamais conserver le fichier.

        L'extraction (PDF surtout) est CPU-bound : exécutée dans un thread pour ne pas bloquer
        la boucle d'événements.
        """
        brut = await asyncio.to_thread(self._extractor, filename, content)
        texte = normalize_document_text(brut.text)
        if len(texte) < MIN_USEFUL_CHARS:
            raise EmptyDocumentError(
                "Aucun texte exploitable dans ce document. S'il s'agit d'un scan, "
                "la reconnaissance de caractères n'est pas encore disponible : "
                "importez une version avec texte sélectionnable ou saisissez le profil à la main."
            )
        return replace(brut, text=texte)
