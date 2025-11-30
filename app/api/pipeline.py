from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.pipeline import PipelineOptions, run_pipeline
from app.spotify import SpotifyTokenMissing, build_spotify_auth_url

router = APIRouter()


class RunRequest(BaseModel):
    refresh_tracks: bool = False
    force_external_refresh: bool = False
    refresh_classification: bool = False
    apply_changes: bool = False  # False = preview only, True = write to Spotify


@router.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@router.post("/run")
def run(req: RunRequest) -> Dict[str, Any]:
    """
    Run the full pipeline in non-interactive mode.

    If no Spotify token is available, returns:
      - HTTP 401
      - body:
        {
          "status": "unauthenticated",
          "message": "Spotify authorization required",
          "auth_url": "https://accounts.spotify.com/authorize?..."
        }
    """
    opts = PipelineOptions(
        refresh_tracks=req.refresh_tracks,
        force_external_refresh=req.force_external_refresh,
        refresh_classification=req.refresh_classification,
        apply_changes=req.apply_changes,
    )

    try:
        result = run_pipeline(opts)
        return result
    except SpotifyTokenMissing as e:
        auth_url = build_spotify_auth_url()
        raise HTTPException(
            status_code=401,
            detail={
                "status": "unauthenticated",
                "message": str(e) or "Spotify authorization required.",
                "auth_url": auth_url,
            },
        )
