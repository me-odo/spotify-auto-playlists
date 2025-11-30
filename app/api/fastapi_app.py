from typing import Any, Dict

from fastapi import FastAPI
from pydantic import BaseModel

from app.pipeline.orchestration import PipelineOptions, run_pipeline

app = FastAPI(
    title="Spotify Auto-Playlists API",
    version="0.1.0",
    description="Backend API for mood-based Spotify auto playlists.",
)


class RunRequest(BaseModel):
    refresh_tracks: bool = False
    force_external_refresh: bool = False
    refresh_classification: bool = False
    apply_changes: bool = False  # False = preview only, True = write to Spotify


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/run")
def run(req: RunRequest) -> Dict[str, Any]:
    """
    Run the full pipeline in non-interactive mode.

    Example body:
    {
      "refresh_tracks": false,
      "force_external_refresh": false,
      "refresh_classification": false,
      "apply_changes": false,
    }
    """
    opts = PipelineOptions(
        refresh_tracks=req.refresh_tracks,
        force_external_refresh=req.force_external_refresh,
        refresh_classification=req.refresh_classification,
        apply_changes=req.apply_changes,
    )
    result = run_pipeline(opts)
    return result
