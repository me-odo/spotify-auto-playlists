from app.api import app
from app.core.cli_utils import configure_logging

configure_logging()

__all__ = ["app"]
