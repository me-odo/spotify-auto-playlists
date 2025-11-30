import logging

# Logger global du projet
LOGGER_NAME = "spotify_auto_playlists"
logger = logging.getLogger(LOGGER_NAME)


def configure_logging(level: int = logging.INFO) -> None:
    """
    Configure le logging global de l'application.

    - Format lisible type backend :
      2025-02-17 21:03:12 [INFO] message...
    - N'est appliqué qu'une seule fois (si aucun handler n'est défini).
    """
    root_logger = logging.getLogger()
    if root_logger.handlers:
        # Déjà configuré (par FastAPI / Uvicorn ou autre), on ne double pas.
        return

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def print_header(title: str) -> None:
    """Top-level section header (affiché comme un log INFO)."""
    logger.info("=== %s ===", title)


def print_info(message: str) -> None:
    """Information neutre."""
    logger.info(message)


def print_step(message: str) -> None:
    """Étape en cours (log INFO avec un léger marquage)."""
    logger.info("→ %s", message)


def print_success(message: str) -> None:
    """Résultat OK."""
    logger.info("✅ %s", message)


def print_warning(message: str) -> None:
    """Avertissement (non bloquant)."""
    logger.warning(message)


def print_error(message: str) -> None:
    """Erreur (bloquante ou sérieuse)."""
    logger.error(message)


def print_question(message: str) -> None:
    """
    Prompt pour l'utilisateur (CLI uniquement).
    On reste sur un simple print, car c'est une interaction directe.
    """
    print(f"?  {message}", end="")


def print_progress_bar(
    current: int,
    total: int,
    prefix: str = "",
    length: int = 30,
) -> None:
    """
    Progression simple, adaptée aux logs backend.

    Au lieu d'une vraie "barre" avec \\r (peu lisible dans les logs),
    on logge une ligne comme :
      prefix 12/57 (21.1%)
    """
    if total <= 0:
        total = 1

    fraction = max(0.0, min(1.0, current / total))
    percent = fraction * 100
    logger.info("%s %d/%d (%.1f%%)", prefix, current, total, percent)
