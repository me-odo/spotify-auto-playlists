from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
import requests
from typing import Dict, List, Tuple, Optional

from cli_utils import (
    print_step,
    print_info,
    print_warning,
    print_progress_bar,
)
from config import (
    EXTERNAL_FEATURES_CACHE_FILE,
    MUSICBRAINZ_USER_AGENT,
)
from fs_utils import ensure_parent_dir
from models import Track


MUSICBRAINZ_API_BASE = "https://musicbrainz.org/ws/2"
ACOUSTICBRAINZ_API_BASE = "https://acousticbrainz.org/api/v1"

# Respect MusicBrainz guidelines: identify the app
MB_HEADERS = {
    "User-Agent": MUSICBRAINZ_USER_AGENT,
}


def load_external_features_cache() -> Dict[str, Dict]:
    if not os.path.exists(EXTERNAL_FEATURES_CACHE_FILE):
        return {}
    with open(EXTERNAL_FEATURES_CACHE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_external_features_cache(cache: Dict[str, Dict]) -> None:
    ensure_parent_dir(EXTERNAL_FEATURES_CACHE_FILE)
    with open(EXTERNAL_FEATURES_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


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
    print_step(
        "Fetching external mood/genre features (MusicBrainz + AcousticBrainz)..."
    )

    # Load existing cache from disk
    cache = load_external_features_cache()
    external_features: Dict[str, Dict] = {}

    # Start by using everything we already have in cache (unless we truly want full refresh)
    if not force_refresh:
        for t in tracks:
            if t.id in cache:
                external_features[t.id] = cache[t.id]

    # Determine which tracks still need external lookups
    if force_refresh:
        to_process = tracks
    else:
        to_process = [t for t in tracks if t.id not in cache]

    total_to_process = len(to_process)

    if total_to_process == 0:
        print_info(
            f"Using existing external features cache; "
            f"{len(external_features)} tracks already have external data."
        )
        # Tracks that still have no external data are unmatched
        unmatched = [t for t in tracks if t.id not in external_features]
        return external_features, unmatched

    print_info(f"{total_to_process} tracks to resolve externally.")

    # Parallel execution: only network calls happen in threads.
    # Cache updates happen in the main thread.
    processed = 0
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_track = {
            executor.submit(_process_track_external, t): t for t in to_process
        }

        for future in as_completed(future_to_track):
            processed += 1
            print_progress_bar(processed, total_to_process, prefix="  External lookup")

            try:
                track_id, entry = future.result()
            except Exception:
                # Any exception in a worker means this track is unmatched for now
                # We'll mark it as unmatched later.
                continue

            if entry is None:
                # Not found / no data for this track
                continue

            # Update in-memory cache + external_features from main thread only
            cache[track_id] = entry
            external_features[track_id] = entry

            # Save cache to disk incrementally so we don't lose progress
            save_external_features_cache(cache)

    # Final log: build unmatched list (tracks with no external data at all)
    unmatched: List[Track] = [t for t in tracks if t.id not in external_features]

    print_info(
        f"External features available for {len(external_features)} tracks "
        f"(tracks processed: {total_to_process})."
    )
    if unmatched:
        print_warning(f"External features missing for {len(unmatched)} tracks.")

    return external_features, unmatched
