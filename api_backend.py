from dataclasses import dataclass
from typing import Dict, Any, List

from cache_manager import load_tracks_cache, save_tracks_cache
from classifier import classify_tracks_rule_based, load_classification_cache
from external_features import enrich_tracks_with_external_features
from playlist_manager import build_target_playlists, sync_playlists
from spotify_client import (
    load_spotify_token,
    get_current_user_id,
    get_user_playlists,
    get_all_liked_tracks,
)
from models import Track
from cli_utils import print_step, print_info


@dataclass
class PipelineOptions:
    use_cli_auth: bool = False
    refresh_tracks: bool = False
    force_external_refresh: bool = False
    refresh_classification: bool = False
    apply_changes: bool = False  # False = preview, True = applique sur Spotify


def _load_tracks_for_pipeline(
    token_info: Dict, opts: PipelineOptions
) -> tuple[List[Track], bool]:
    """
    Charge les titres likés :
      - si refresh_tracks=True  → ignore le cache et refetch depuis Spotify
      - sinon → essaye le cache, et si vide → fetch depuis Spotify
    Retourne (tracks, tracks_refreshed)
    """
    cached_tracks = load_tracks_cache()
    tracks_refreshed = False

    if opts.refresh_tracks or not cached_tracks:
        if cached_tracks and opts.refresh_tracks:
            print_step(
                "Refreshing liked tracks from Spotify (forced by API options)..."
            )
        else:
            print_step("Fetching liked tracks from Spotify (no local cache)...")

        tracks = get_all_liked_tracks(token_info)
        save_tracks_cache(tracks)
        tracks_refreshed = True
    else:
        print_step("Using cached liked tracks (API pipeline).")
        tracks = cached_tracks

    print_info(f"Pipeline will use {len(tracks)} liked tracks.")
    return tracks, tracks_refreshed


def run_pipeline(opts: PipelineOptions) -> Dict[str, Any]:
    """
    Non-interactive orchestration of the full pipeline:
      - auth + user + playlists
      - tracks (with cache)
      - external features (MB/AcousticBrainz)
      - rule-based classification
      - build target playlists
      - sync playlists (preview or apply depending on opts.apply_changes)

    Returns a JSON-serializable dict with summary + diffs.
    """
    # 1) Auth + user + existing playlists
    print_step("Loading Spotify token (API pipeline)...")
    token_info = load_spotify_token(use_cli_auth=opts.use_cli_auth)

    print_step("Fetching current Spotify user (API pipeline)...")
    user_id = get_current_user_id(token_info)

    print_step("Fetching existing playlists from Spotify (API pipeline)...")
    playlists_existing = get_user_playlists(token_info)

    # 2) Liked tracks with cache
    tracks, tracks_refreshed = _load_tracks_for_pipeline(token_info, opts)

    # 3) External mood/genre features
    print_step("Fetching external mood/genre features (API pipeline)...")
    external_features, unmatched_tracks = enrich_tracks_with_external_features(
        tracks,
        force_refresh=opts.force_external_refresh,
    )

    # 4) Classification (rule-based)
    print_step("Classifying tracks (API pipeline)...")
    classifications = classify_tracks_rule_based(
        tracks=tracks,
        external_features=external_features,
        refresh_existing=opts.refresh_classification,
    )

    # Recompute mood counts (pour renvoyer dans la réponse JSON)
    mood_counts: Dict[str, int] = {}
    for c in classifications.values():
        mood_counts[c.mood] = mood_counts.get(c.mood, 0) + 1

    # 5) Build target playlists
    print_step("Building target playlists (API pipeline)...")
    playlists_mood, playlists_genre, playlists_year = build_target_playlists(
        tracks,
        classifications,
    )

    # 6) Sync playlists (preview or apply)
    print_step("Preparing playlist sync (API pipeline)...")
    track_map = {t.id: t for t in tracks}
    diffs = sync_playlists(
        token_info=token_info,
        user_id=user_id,
        playlists_existing=playlists_existing,
        playlists_mood=playlists_mood,
        playlists_genre=playlists_genre,
        playlists_year=playlists_year,
        track_map=track_map,
        apply_changes=opts.apply_changes,
    )

    playlists_with_changes = sum(1 for d in diffs if d["duplicates"] or d["new_to_add"])
    playlists_created = sum(
        1
        for d in diffs
        if d.get("playlist_id") is None and (d["duplicates"] or d["new_to_add"])
    )

    result: Dict[str, Any] = {
        "user_id": user_id,
        "total_tracks": len(tracks),
        "tracks_refreshed": tracks_refreshed,
        "external_features_count": len(external_features),
        "unmatched_count": len(unmatched_tracks),
        "moods": mood_counts,
        "playlists_with_changes": playlists_with_changes,
        "playlists_created": playlists_created,
        "diffs": diffs,
    }
    return result
