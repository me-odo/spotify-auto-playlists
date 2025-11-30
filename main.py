from app.pipeline import run_cli_pipeline
from app.core.cli_utils import configure_logging


if __name__ == "__main__":
    configure_logging()
    run_cli_pipeline()
