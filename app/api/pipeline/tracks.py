from fastapi import APIRouter, HTTPException

from app.core import log_info, log_step
from app.pipeline import load_tracks_cache, save_tracks_cache
from app.spotify import (
    SpotifyTokenMissing,
    build_spotify_auth_url,
    get_all_liked_tracks,
    load_spotify_token,
)

from .schemas import TracksResponse

router = APIRouter()


def _raise_unauth(e: SpotifyTokenMissing) -> None:
    raise HTTPException(
        status_code=401,
        detail={
            "status": "unauthenticated",
            "message": str(e) or "Spotify authorization required.",
            "auth_url": build_spotify_auth_url(),
        },
    )


@router.get("/tracks", response_model=TracksResponse)
def get_tracks(force_refresh: bool = False) -> TracksResponse:
    """
    Étape 1 : récupération des liked tracks.
    - Utilise le cache si présent
    - Sinon va chercher sur Spotify
    """

    try:
        token_info = load_spotify_token()
    except SpotifyTokenMissing as e:
        _raise_unauth(e)

    cached_tracks = load_tracks_cache()
    tracks = cached_tracks
    refreshed = False

    if force_refresh or not cached_tracks:
        if cached_tracks and force_refresh:
            log_step("Refreshing liked tracks from Spotify (forced)...")
        else:
            log_step("Fetching liked tracks from Spotify...")
        tracks = get_all_liked_tracks(token_info)
        save_tracks_cache(tracks)
        refreshed = True

    log_info(f"Tracks step: {len(tracks)} tracks (refreshed={refreshed}).")

    return TracksResponse(
        status="done",
        tracks_count=len(tracks),
        from_cache=not refreshed,
        fetched_from_spotify=len(tracks) if refreshed else 0,
    )
