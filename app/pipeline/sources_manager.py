from typing import Any, Dict, List

from app.core import Track
from app.spotify import (
    TrackSource,
    TrackSourceType,
    get_all_liked_tracks,
    get_playlist_tracks,
)


def fetch_tracks_for_source(
    token_info: Dict[str, Any], source: TrackSource
) -> List[Track]:
    """Fetch tracks for a given TrackSource using the Spotify Web API.

    For liked tracks, this delegates to get_all_liked_tracks.
    For playlists, this calls get_playlist_tracks to obtain track ids and converts
    them into minimal Track objects so that downstream code can treat all items
    as Track instances.

    The playlist branch intentionally does not attempt to resolve full track
    metadata for each id to keep the implementation lightweight; only the track
    id is guaranteed to be populated. Other fields are left empty or null.
    """
    if source.source_type == TrackSourceType.LIKED:
        return get_all_liked_tracks(token_info)

    if source.source_type == TrackSourceType.PLAYLIST:
        if not source.source_id:
            # Defensive check: playlist sources should always carry a playlist id.
            return []

        track_ids = get_playlist_tracks(token_info, source.source_id)
        tracks: List[Track] = []
        for track_id in track_ids:
            if not track_id:
                continue
            tracks.append(
                Track(
                    id=track_id,
                    name="",
                    artist="",
                    album="",
                    release_date=None,
                    added_at=None,
                    features={},
                )
            )
        return tracks

    raise ValueError(f"Unsupported TrackSourceType: {source.source_type!r}")
