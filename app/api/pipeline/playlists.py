from typing import Dict, List

from fastapi import APIRouter, HTTPException

from app.core.logging_utils import log_info
from app.pipeline.cache_manager import load_classification_cache, load_tracks_cache
from app.pipeline.playlist_manager import build_target_playlists

from .schemas import BuildResponse, PlaylistPreview

router = APIRouter()


@router.get("/build", response_model=BuildResponse)
def build_playlists() -> BuildResponse:
    """
    Étape 4 : génération des playlists cibles.
    - AUCUN appel externe
    - Utilise uniquement les caches : tracks + classification
    """

    tracks = load_tracks_cache()
    if not tracks:
        raise HTTPException(
            status_code=400,
            detail="Tracks cache is empty. Run /pipeline/tracks first.",
        )

    classifications = load_classification_cache()
    if not classifications:
        raise HTTPException(
            status_code=400,
            detail="Classification cache is empty. Run /pipeline/classify first.",
        )

    # NOTE : build_target_playlists doit avoir la signature (tracks, classifications)
    playlists_mood, playlists_genre, playlists_year = build_target_playlists(
        tracks,
        classifications,
    )

    target_playlists: Dict[str, List[str]] = {}
    for source in (playlists_mood, playlists_genre, playlists_year):
        for name, ids in source.items():
            bucket = target_playlists.setdefault(name, [])
            for tid in ids:
                if tid not in bucket:
                    bucket.append(tid)

    previews = [
        PlaylistPreview(name=name, tracks_count=len(ids))
        for name, ids in target_playlists.items()
    ]

    log_info(f"Built {len(previews)} target playlists.")

    return BuildResponse(status="done", playlists=previews)
