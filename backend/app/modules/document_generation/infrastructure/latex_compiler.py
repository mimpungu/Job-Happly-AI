"""Service de compilation LaTeX isolé et sécurisé (FEATURE 012.3).

Respecte les critères de sécurité et de robustesse :
- TASK-012-12 : Détection et configuration sécurisée de pdfLaTeX.
- TASK-012-13 : Dossier temporaire isolé et suppression garantie.
- TASK-012-14 : Diagnostic clair des erreurs TeX depuis les logs.
- TASK-012-15 : Limites strictes de temps (timeout) et de taille de fichier.
- TASK-012-16 : Accès réseau et shell désactivés (-no-shell-escape).
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.modules.document_generation.application.ports import (
    CompilationTimeoutError,
    LaTeXCompilationError,
    LaTeXCompilerPort,
    LaTeXSourceTooLargeError,
)

MAX_LATEX_SOURCE_BYTES = 1_048_576  # 1 Mo
DEFAULT_TIMEOUT_SECONDS = 15.0


class IsolatedLaTeXCompiler(LaTeXCompilerPort):
    """Compilateur pdfLaTeX exécuté dans un environnement isolé."""

    def __init__(
        self,
        *,
        pdflatex_path: str | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._pdflatex_path = self._resolve_pdflatex(pdflatex_path)
        self._timeout_seconds = timeout_seconds

    @staticmethod
    def _resolve_pdflatex(custom_path: str | None) -> str:
        """Trouve le binaire pdflatex sur le système (TASK-012-12)."""
        if custom_path and os.path.exists(custom_path) and os.access(custom_path, os.X_OK):
            return custom_path

        from_which = shutil.which("pdflatex")
        if from_which:
            return from_which

        chemins_standards = [
            "/Library/TeX/texbin/pdflatex",  # macOS TeX Live / MacTeX
            "/usr/bin/pdflatex",  # Linux standard
            "/usr/local/bin/pdflatex",
        ]
        for chemin in chemins_standards:
            if os.path.exists(chemin) and os.access(chemin, os.X_OK):
                return chemin

        raise FileNotFoundError(
            "Le compilateur pdfLaTeX est introuvable. "
            "Veuillez installer TeX Live / MacTeX ou définir HAPPLY_PDFLATEX_PATH."
        )

    async def compile(self, latex_source: str) -> bytes:
        """Exécute la compilation hors de la boucle d'événements principale."""
        taille_octets = len(latex_source.encode("utf-8"))
        if taille_octets > MAX_LATEX_SOURCE_BYTES:
            raise LaTeXSourceTooLargeError(
                f"La source LaTeX ({taille_octets} octets) dépasse la taille maximale "
                f"autorisée ({MAX_LATEX_SOURCE_BYTES} octets)."
            )

        return await asyncio.to_thread(self._compile_sync, latex_source)

    def _compile_sync(self, latex_source: str) -> bytes:
        with tempfile.TemporaryDirectory(prefix="happly_latex_") as tmpdir:
            tex_file = Path(tmpdir) / "document.tex"
            pdf_file = Path(tmpdir) / "document.pdf"
            log_file = Path(tmpdir) / "document.log"

            tex_file.write_text(latex_source, encoding="utf-8")

            cmd = [
                self._pdflatex_path,
                "-no-shell-escape",
                "-interaction=nonstopmode",
                "-halt-on-error",
                "document.tex",
            ]

            try:
                # Commande sans shell, arguments strictement statiques dans un tempdir dédié
                resultat = subprocess.run(  # noqa: S603
                    cmd,
                    cwd=tmpdir,
                    capture_output=True,
                    text=True,
                    timeout=self._timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise CompilationTimeoutError(
                    f"Délai limite de compilation dépassé ({self._timeout_seconds}s)."
                ) from exc

            if resultat.returncode != 0 or not pdf_file.exists():
                message_erreur, log_snippet = self._extraire_erreur_log(log_file)
                raise LaTeXCompilationError(
                    f"Échec compilation pdfLaTeX ({resultat.returncode}) : {message_erreur}",
                    log_snippet=log_snippet,
                )

            return pdf_file.read_bytes()

    @staticmethod
    def _extraire_erreur_log(log_path: Path) -> tuple[str, str | None]:
        """Extrait le message d'erreur significatif depuis le journal TeX."""
        if not log_path.exists():
            return "Erreur inconnue (fichier log introuvable).", None

        try:
            contenu = log_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return "Impossible de lire le fichier journal de compilation.", None

        lignes_erreur: list[str] = []
        lignes = contenu.splitlines()
        for idx, ligne in enumerate(lignes):
            if ligne.startswith("!"):
                contexte = " ".join(lignes[idx : idx + 3])
                lignes_erreur.append(contexte)

        if lignes_erreur:
            resume = lignes_erreur[0]
            snippet = "\n".join(lignes[-30:])
            return resume, snippet

        return "Erreur TeX générique sans description explicite.", "\n".join(lignes[-20:])
