"""Track sources for Spotify-backed pipelines.

This module defines small data structures to describe where tracks come from
(liked tracks or specific playlists).
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class TrackSourceType(str, Enum):
    """Type of track source used in the pipeline."""

    LIKED = "liked"
    PLAYLIST = "playlist"


@dataclass
class TrackSource:
    """Description of a track source for pipeline jobs.

    For liked tracks, source_type is "liked" and source_id may be None.
    For playlists, source_type is "playlist" and source_id is the playlist id.
    """

    source_type: TrackSourceType
    source_id: Optional[str] = None
    label: Optional[str] = None
