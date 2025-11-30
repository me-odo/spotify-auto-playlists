import logging
import sys


def configure_logging(level: int = logging.INFO) -> None:
    """
    Configure root logging for the application.

    - Logs go to stdout
    - Simple, readable format with time, level, and logger name
    """
    root = logging.getLogger()

    # Avoid adding handlers multiple times
    if root.handlers:
        root.setLevel(level)
        return

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%H:%M:%S",
    )
    handler.setFormatter(formatter)

    root.addHandler(handler)
    root.setLevel(level)
