from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple

import requests

from app.config import EXTERNAL_FEATURES_CACHE_FILE, MUSICBRAINZ_USER_AGENT
from app.core import (
    Track,
    log_info,
    log_progress,
    log_step,
    log_warning,
    read_json,
    write_json,
)

MUSICBRAINZ_API_BASE = "https://musicbrainz.org/ws/2"
ACOUSTICBRAINZ_API_BASE = "https://acousticbrainz.org/api/v1"

# Respect MusicBrainz guidelines: identify the app
MB_HEADERS = {
    "User-Agent": MUSICBRAINZ_USER_AGENT,
}


def load_external_features_cache() -> Dict[str, Dict]:
    def _on_error(e: Exception) -> None:
        log_warning("External features cache file is corrupted; ignoring it.")

    return read_json(EXTERNAL_FEATURES_CACHE_FILE, default={}, on_error=_on_error)


def save_external_features_cache(cache: Dict[str, Dict]) -> None:
    write_json(EXTERNAL_FEATURES_CACHE_FILE, cache)


def _search_musicbrainz_recording(track: Track) -> Optional[str]:
    """
    Try to resolve a MusicBrainz recording MBID from track title + artist.
    Returns the MBID as a string or None if not found.
    """
    # simple strategy: use first artist in the list
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

        # naive: take the first recording
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

    # Parallel execution: only network calls happen in threads.
    # Cache updates happen in the main thread.
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
                # Not found / no data for this track
                continue

            # Update in-memory cache + external_features from main thread only
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
    For each Track, try to get external features (mood/genre/etc.) via:
      - MusicBrainz (recording search)
      - AcousticBrainz (high-level data)

    Caching logic:
      - cache is keyed by Spotify track ID
      - if force_refresh=False, we reuse cached entries and only call external APIs
        for tracks that are missing in the cache
      - cache is updated and saved to disk incrementally after each successful fetch

    Parallelism:
      - external lookups are done in parallel (ThreadPoolExecutor)
      - shared state (cache, external_features) is only modified from the main thread,
        based on worker results → no concurrent writes, no race conditions.
    """
    log_step("Fetching external mood/genre features (MusicBrainz + AcousticBrainz)...")

    # Load existing cache from disk
    cache = load_external_features_cache()

    # Use cached data when possible, and identify tracks that still need work
    external_features, to_process = _prepare_external_features_from_cache(
        tracks=tracks,
        cache=cache,
        force_refresh=force_refresh,
    )

    # If nothing to process, we only rely on cache
    if not to_process:
        log_info(
            f"Using existing external features cache; "
            f"{len(external_features)} tracks already have external data."
        )
        unmatched = _build_unmatched_tracks(tracks, external_features)
        return external_features, unmatched

    # Resolve missing external features in parallel
    total_processed = _process_missing_external_features(
        to_process=to_process,
        cache=cache,
        external_features=external_features,
    )

    # Final log: build unmatched list (tracks with no external data at all)
    unmatched = _build_unmatched_tracks(tracks, external_features)

    log_info(
        f"External features available for {len(external_features)} tracks "
        f"(tracks processed: {total_processed})."
    )

    return external_features, unmatched
