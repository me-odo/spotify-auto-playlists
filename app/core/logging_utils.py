import logging

# Global project logger (can be tuned via logging_config)
logger = logging.getLogger("spotify_auto_playlists")


def log_section(title: str) -> None:
    """
    Log a top-level section header.
    """
    logger.info("")  # blank line for readability
    logger.info("=== %s ===", title)


def log_info(message: str) -> None:
    """
    Neutral information message.
    """
    logger.info("%s", message)


def log_step(message: str) -> None:
    """
    Action step / ongoing work.
    """
    logger.info("→ %s", message)


def log_success(message: str) -> None:
    """
    Successful outcome.
    """
    logger.info("✅ %s", message)


def log_warning(message: str) -> None:
    """
    Warning / non-fatal problem.
    """
    logger.warning("⚠️ %s", message)


def log_error(message: str) -> None:
    """
    Error / fatal problem.
    """
    logger.error("❌ %s", message)


def log_progress(
    current: int,
    total: int,
    prefix: str = "",
) -> None:
    """
    Simple progress logging.

    Example:
      log_progress(10, 100, prefix="Fetching pages")
      -> "Fetching pages 10/100 (10.0%)"
    """
    if total <= 0:
        total = 1

    fraction = max(0.0, min(1.0, current / total))
    percent = fraction * 100

    if prefix:
        logger.info("%s %d/%d (%.1f%%)", prefix, current, total, percent)
    else:
        logger.info("%d/%d (%.1f%%)", current, total, percent)
