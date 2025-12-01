"""External feature enrichment for Spotify tracks.

This module implements a cache-driven enrichment pipeline that augments Spotify
tracks with additional metadata fetched from external services:

  - MusicBrainz: used to resolve a recording MBID for a given track
  - AcousticBrainz: used to retrieve high-level audio features for that MBID

The design is intentionally cache-first:
  - a local cache, indexed by Spotify track ID, is loaded at the beginning
  - only tracks missing from the cache (or all tracks when force_refresh=True)
    are queried against the external APIs
  - the cache is persisted incrementally as new entries are discovered

The main entrypoint, enrich_tracks_with_external_features(), encapsulates this
step-by-step logic and returns both the resolved external_features mapping and
the list of unmatched tracks, so that later pipeline stages can decide how to
handle tracks without external data.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple

import requests

from app.config import MUSICBRAINZ_USER_AGENT
from app.core import Track, log_info, log_progress, log_step
from app.pipeline.cache_manager import (
    load_external_features_cache,
    save_external_features_cache,
)

MUSICBRAINZ_API_BASE = "https://musicbrainz.org/ws/2"
ACOUSTICBRAINZ_API_BASE = "https://acousticbrainz.org/api/v1"

# Respect MusicBrainz guidelines: identify the app
MB_HEADERS = {
    "User-Agent": MUSICBRAINZ_USER_AGENT,
}


def _search_musicbrainz_recording(track: Track) -> Optional[str]:
    """
    Try to resolve a MusicBrainz recording MBID from track title + artist.
    Returns the MBID as a string or None if not found.
    """
    main_artist = track.artist.split(",")[0].strip() if track.artist else ""

    if not track.name or not main_artist:
        return None

    query = f'recording:"{track.name}" AND artist:"{main_artist}"'
    params = {
        "query": query,
        "fmt": "json",
        "limit": 5,
    }

    try:
        r = requests.get(
            f"{MUSICBRAINZ_API_BASE}/recording",
            headers=MB_HEADERS,
            params=params,
            timeout=10,
        )
        if not r.ok:
            return None
        data = r.json()
        recordings = data.get("recordings", [])
        if not recordings:
            return None

        mbid = recordings[0].get("id")
        return mbid
    except Exception:
        return None


def _fetch_acousticbrainz_highlevel(mbid: str) -> Optional[Dict]:
    """
    Fetch AcousticBrainz high-level features for a given MBID.
    Returns the parsed JSON or None if not available.
    """
    try:
        url = f"{ACOUSTICBRAINZ_API_BASE}/{mbid}/high-level"
        r = requests.get(url, headers=MB_HEADERS, timeout=10)
        if not r.ok:
            return None
        return r.json()
    except Exception:
        return None


def _process_track_external(t: Track) -> tuple[str, Optional[Dict]]:
    """
    Worker function for a single track:
    - try to find a MusicBrainz MBID
    - then fetch AcousticBrainz high-level features
    Returns (spotify_track_id, entry_or_None)
    """
    mbid = _search_musicbrainz_recording(t)
    if not mbid:
        return t.id, None

    hl = _fetch_acousticbrainz_highlevel(mbid)
    if not hl:
        return t.id, None

    entry = {
        "mbid": mbid,
        "highlevel": hl.get("highlevel", hl),
    }
    return t.id, entry


def _prepare_external_features_from_cache(
    tracks: List[Track],
    cache: Dict[str, Dict],
    force_refresh: bool,
) -> Tuple[Dict[str, Dict], List[Track]]:
    """
    Initialize the external_features dict from cache and determine which tracks
    still require external lookups.
    """
    external_features: Dict[str, Dict] = {}

    if not force_refresh:
        for track in tracks:
            if track.id in cache:
                external_features[track.id] = cache[track.id]

    if force_refresh:
        to_process = tracks
    else:
        to_process = [t for t in tracks if t.id not in cache]

    return external_features, to_process


def _process_missing_external_features(
    to_process: List[Track],
    cache: Dict[str, Dict],
    external_features: Dict[str, Dict],
) -> int:
    """
    Resolve external features for tracks missing in the cache, using a thread pool.

    Returns the number of tracks that were scheduled for processing.
    """
    total_to_process = len(to_process)
    if total_to_process == 0:
        return 0

    log_info(f"{total_to_process} tracks to resolve externally.")

    processed = 0
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_track = {
            executor.submit(_process_track_external, track): track
            for track in to_process
        }

        for future in as_completed(future_to_track):
            processed += 1
            log_progress(processed, total_to_process, prefix="  External lookup")

            try:
                track_id, entry = future.result()
            except Exception:
                # Any exception in a worker means this track is unmatched for now.
                continue

            if entry is None:
                continue

            cache[track_id] = entry
            external_features[track_id] = entry

            # Save cache to disk incrementally so we don't lose progress
            save_external_features_cache(cache)

    return total_to_process


def _build_unmatched_tracks(
    tracks: List[Track],
    external_features: Dict[str, Dict],
) -> List[Track]:
    """
    Compute the list of tracks for which we have no external features.
    """
    return [t for t in tracks if t.id not in external_features]


def enrich_tracks_with_external_features(
    tracks: List[Track],
    force_refresh: bool = False,
) -> Tuple[Dict[str, Dict], List[Track]]:
    """
    Pour chaque Track, essaie de récupérer des features externes (mood/genre/etc.)
    via MusicBrainz + AcousticBrainz.

    Caching :
      - cache indexé par ID Spotify
      - si force_refresh=False, on réutilise le cache et on ne fait des calls externes
        que pour les morceaux manquants
      - le cache est mis à jour au fur et à mesure

    Retourne:
      - external_features: dict[track_id] -> données externes
      - unmatched_tracks: liste des tracks sans données externes
    """
    log_step("Fetching external mood/genre features (MusicBrainz + AcousticBrainz)...")

    cache = load_external_features_cache()

    external_features, to_process = _prepare_external_features_from_cache(
        tracks=tracks,
        cache=cache,
        force_refresh=force_refresh,
    )

    if not to_process:
        log_info(
            f"Using existing external features cache; "
            f"{len(external_features)} tracks already have external data."
        )
        unmatched = _build_unmatched_tracks(tracks, external_features)
        return external_features, unmatched

    total_processed = _process_missing_external_features(
        to_process=to_process,
        cache=cache,
        external_features=external_features,
    )

    unmatched = _build_unmatched_tracks(tracks, external_features)

    log_info(
        f"External features available for {len(external_features)} tracks "
        f"(tracks processed: {total_processed})."
    )

    return external_features, unmatched
