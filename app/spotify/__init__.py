"""Public façade for the app.spotify package.

This module exposes the high-level Spotify Web API integration: authentication,
track retrieval, and playlist management helpers that are safe to import from
other packages. Callers should import these symbols from this façade instead
of the internal auth, tracks, or playlists modules.
"""

from .auth import (
    SpotifyAuthError,
    SpotifyTokenMissing,
    build_spotify_auth_url,
    exchange_code_for_token,
    get_current_user_id,
    load_spotify_token,
    refresh_spotify_token,
    spotify_headers,
)
from .playlists import (
    find_or_create_playlist,
    get_playlist_tracks,
    get_user_playlists,
    incremental_update_playlist,
    list_user_playlists,
    set_playlist_tracks,
)
from .sources import TrackSource, TrackSourceType
from .tracks import get_all_liked_tracks

__all__ = [
    "build_spotify_auth_url",
    "exchange_code_for_token",
    "refresh_spotify_token",
    "load_spotify_token",
    "spotify_headers",
    "get_current_user_id",
    "SpotifyAuthError",
    "SpotifyTokenMissing",
    "get_all_liked_tracks",
    "get_user_playlists",
    "find_or_create_playlist",
    "get_playlist_tracks",
    "set_playlist_tracks",
    "incremental_update_playlist",
    "list_user_playlists",
    "TrackSource",
    "TrackSourceType",
]
