from typing import List

from fastapi import APIRouter, HTTPException

from app.core import log_info, log_step
from app.spotify import (
    SpotifyTokenMissing,
    build_spotify_auth_url,
    list_user_playlists,
    load_spotify_token,
)

from .schemas import PlaylistSummary, PlaylistSummaryList

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


@router.get("/playlists")
def get_spotify_playlists():
    """
    List the current user's Spotify playlists.

    This endpoint requires a valid Spotify token.
    Returns a list of objects with at least 'id' and 'name'.
    """
    try:
        token_info = load_spotify_token()
    except SpotifyTokenMissing as e:
        _raise_unauth(e)

    log_step("Fetching Spotify playlists for current user...")
    raw_playlists = list_user_playlists(token_info)
    log_info(f"Spotify playlists: {len(raw_playlists)} playlists found.")

    # Always return a list of dicts with at least 'id' and 'name'
    return [
        {"id": p["id"], "name": p["name"]}
        for p in raw_playlists
        if "id" in p and "name" in p
    ]
