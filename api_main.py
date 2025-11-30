from app.api import app
from app.core import configure_logging

configure_logging()

__all__ = ["app"]
