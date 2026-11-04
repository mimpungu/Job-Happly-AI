"""Compilation pdfLaTeX isolée et sécurisée (FEATURE 012.3).

Défense en profondeur, du plus statique au plus dynamique :
- validation statique de la source (commandes et paquets interdits) ;
- TeX en mode paranoïaque : lecture/écriture limitées au dossier de travail
  (`openin_any=p`, `openout_any=p`), shell-escape coupé ;
- environnement minimal : aucun secret de l'application n'est transmis au processus ;
- dossier temporaire dédié, détruit dans tous les cas ;
- limites CPU, mémoire, taille de fichier et durée, groupe de processus tué au timeout ;
- espace réseau vide (`unshare --net`) lorsque le système l'autorise.
"""

from __future__ import annotations

import asyncio
import functools
import logging
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

from app.modules.document_generation.application.ports import (
    CompilationTimeoutError,
    CompilerUnavailableError,
    LaTeXCompilationError,
    LaTeXCompilerPort,
    LaTeXSourceTooLargeError,
    UnsafeLaTeXSourceError,
)
from app.modules.document_generation.domain.latex_safety import (
    ForbiddenLaTeXError,
    validate_latex_source,
)
from app.modules.document_generation.domain.pdf_safety import UnsafePdfError, assert_safe_pdf

logger = logging.getLogger(__name__)

MAX_LATEX_SOURCE_BYTES = 1_048_576  # 1 Mo
MAX_OUTPUT_BYTES = 20 * 1024 * 1024  # un CV de plus de 20 Mo est anormal
DEFAULT_TIMEOUT_SECONDS = 15.0
DEFAULT_MEMORY_LIMIT_MB = 1024

_STANDARD_PATHS = (
    "/Library/TeX/texbin/pdflatex",  # macOS (MacTeX)
    "/usr/bin/pdflatex",
    "/usr/local/bin/pdflatex",
)


@functools.cache
def _network_isolation_prefix() -> tuple[str, ...]:
    """Préfixe de commande donnant un espace réseau vide, ou () si le système l'interdit."""
    unshare = shutil.which("unshare")
    if unshare is None or not sys.platform.startswith("linux"):
        return ()
    for options in (("--net",), ("--net", "--map-root-user")):
        try:
            test = subprocess.run(  # noqa: S603
                [unshare, *options, "true"],
                capture_output=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if test.returncode == 0:
            return (unshare, *options)
    logger.warning(
        "Isolation réseau de la compilation LaTeX indisponible : shell-escape coupé et "
        "accès fichiers restreint restent actifs."
    )
    return ()


class IsolatedLaTeXCompiler(LaTeXCompilerPort):
    """Compilateur pdfLaTeX exécuté dans un environnement restreint."""

    def __init__(
        self,
        *,
        pdflatex_path: str | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        memory_limit_mb: int = DEFAULT_MEMORY_LIMIT_MB,
    ) -> None:
        # Résolution paresseuse : consulter ou télécharger un CV ne doit pas exiger pdfLaTeX.
        self._configured_path = pdflatex_path
        self._timeout_seconds = timeout_seconds
        self._memory_limit_bytes = memory_limit_mb * 1024 * 1024

    def _resolve_pdflatex(self) -> str:
        candidats = [self._configured_path, shutil.which("pdflatex"), *_STANDARD_PATHS]
        for chemin in candidats:
            if chemin and os.path.isfile(chemin) and os.access(chemin, os.X_OK):
                return chemin
        raise CompilerUnavailableError(
            "Le compilateur pdfLaTeX est introuvable. "
            "Installez TeX Live / MacTeX ou définissez HAPPLY_PDFLATEX_PATH."
        )

    async def compile(self, latex_source: str) -> bytes:
        """Valide puis compile hors de la boucle d'événements principale."""
        taille_octets = len(latex_source.encode("utf-8"))
        if taille_octets > MAX_LATEX_SOURCE_BYTES:
            raise LaTeXSourceTooLargeError(
                f"La source LaTeX ({taille_octets} octets) dépasse la taille maximale "
                f"autorisée ({MAX_LATEX_SOURCE_BYTES} octets)."
            )
        try:
            validate_latex_source(latex_source)
        except ForbiddenLaTeXError as err:
            raise UnsafeLaTeXSourceError(str(err)) from err

        pdflatex = self._resolve_pdflatex()
        return await asyncio.to_thread(self._compile_sync, pdflatex, latex_source)

    def _environment(self, tmpdir: str) -> dict[str, str]:
        """Environnement minimal : ni clés d'API ni URL de base de données."""
        return {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": tmpdir,
            "TEXMFVAR": f"{tmpdir}/texmf-var",
            "TEXMFCONFIG": f"{tmpdir}/texmf-config",
            "LANG": "C.UTF-8",
            "openin_any": "p",
            "openout_any": "p",
            "shell_escape": "f",
        }

    def _limit_resources(self) -> None:  # pragma: no cover - exécuté dans le processus fils
        import resource

        limites = (
            (resource.RLIMIT_CPU, int(self._timeout_seconds) + 5),
            (resource.RLIMIT_FSIZE, MAX_OUTPUT_BYTES),
            (resource.RLIMIT_CORE, 0),
            (resource.RLIMIT_AS, self._memory_limit_bytes),
        )
        for limite, valeur in limites:
            try:
                resource.setrlimit(limite, (valeur, valeur))
            except (ValueError, OSError):
                # Certaines limites ne sont pas applicables sur toutes les plateformes (macOS).
                continue

    def _compile_sync(self, pdflatex: str, latex_source: str) -> bytes:
        with tempfile.TemporaryDirectory(prefix="happly_latex_") as tmpdir:
            tex_file = Path(tmpdir) / "document.tex"
            pdf_file = Path(tmpdir) / "document.pdf"
            log_file = Path(tmpdir) / "document.log"
            tex_file.write_text(latex_source, encoding="utf-8")

            commande = [
                *_network_isolation_prefix(),
                pdflatex,
                "-no-shell-escape",
                "-interaction=nonstopmode",
                "-halt-on-error",
                "document.tex",
            ]
            posix = sys.platform != "win32"
            # Commande sans shell, arguments statiques, dossier dédié, environnement minimal.
            processus = subprocess.Popen(  # noqa: S603
                commande,
                cwd=tmpdir,
                env=self._environment(tmpdir),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=posix,
                preexec_fn=self._limit_resources if posix else None,
            )
            try:
                code = processus.wait(timeout=self._timeout_seconds)
            except subprocess.TimeoutExpired as exc:
                self._tuer(processus)
                raise CompilationTimeoutError(
                    f"Délai limite de compilation dépassé ({self._timeout_seconds}s)."
                ) from exc

            if code != 0 or not pdf_file.exists():
                message_erreur, log_snippet = self._extraire_erreur_log(log_file)
                raise LaTeXCompilationError(
                    f"Échec compilation pdfLaTeX ({code}) : {message_erreur}",
                    log_snippet=log_snippet,
                )
            contenu = pdf_file.read_bytes()
            try:
                assert_safe_pdf(contenu)
            except UnsafePdfError as erreur:
                raise UnsafeLaTeXSourceError(str(erreur)) from erreur
            return contenu

    @staticmethod
    def _tuer(processus: subprocess.Popen[bytes]) -> None:
        """Tue tout le groupe de processus (pdflatex lance parfois mktexpk, kpsewhich…)."""
        try:
            if sys.platform != "win32":
                os.killpg(processus.pid, signal.SIGKILL)
            else:  # pragma: no cover
                processus.kill()
        except ProcessLookupError:
            pass
        processus.wait()

    @staticmethod
    def _extraire_erreur_log(log_path: Path) -> tuple[str, str | None]:
        """Extrait le message d'erreur significatif depuis le journal TeX."""
        if not log_path.exists():
            return "Erreur inconnue (fichier log introuvable).", None

        try:
            contenu = log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return "Impossible de lire le fichier journal de compilation.", None

        lignes = contenu.splitlines()
        erreurs = [
            " ".join(lignes[i : i + 3]) for i, ligne in enumerate(lignes) if ligne[:1] == "!"
        ]
        if erreurs:
            return erreurs[0], "\n".join(lignes[-30:])
        return "Erreur TeX générique sans description explicite.", "\n".join(lignes[-20:])
