"""Tests du stockage documentaire local (ADR-0007)."""

import tempfile

import pytest

from app.modules.document_generation.infrastructure.document_storage import (
    LocalDocumentStorage,
)


async def test_stockage_lecture_et_suppression() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalDocumentStorage(base_directory=tmpdir)
        contenu = b"%PDF-1.4 test document content"

        cle, sha256, taille = await storage.store(contenu, extension="pdf")

        assert cle.endswith(".pdf")
        assert len(sha256) == 64
        assert taille == len(contenu)

        # Lecture
        lu = await storage.read(cle)
        assert lu == contenu

        # Suppression
        await storage.delete(cle)
        with pytest.raises(FileNotFoundError):
            await storage.read(cle)


async def test_protection_traversee_de_repertoire() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalDocumentStorage(base_directory=tmpdir)

        with pytest.raises(ValueError, match="traversée"):
            await storage.read("../../etc/passwd")

        with pytest.raises(ValueError, match="traversée"):
            await storage.read("dossier/fichier.pdf")
