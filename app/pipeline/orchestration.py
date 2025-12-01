"""Orchestration helpers for the CLI pipeline entrypoint.

This module wires together all pipeline stages into the high-level
run_pipeline() function that is primarily used for command-line execution.

The HTTP API layer does not call run_pipeline() directly; instead it exposes
step-by-step endpoints (tracks, external features, classifications, playlists)
so the frontend can run and inspect each stage independently.

run_pipeline() remains useful for local CLI runs and integration-style tests,
where executing the whole pipeline in a single call is desirable.
"""

from dataclasses import dataclass
from typing import Any, Dict, List

from app.core import log_info, log_section, log_step, log_success
from app.core.models import Track
from app.spotify import (
    get_all_liked_tracks,
    get_current_user_id,
    get_user_playlists,
    load_spotify_token,
)

from .cache_manager import load_tracks_cache, save_tracks_cache
from .classifier import classify_tracks_rule_based
from .external_features import enrich_tracks_with_external_features
from .playlist_manager import build_target_playlists, sync_playlists


@dataclass
class PipelineOptions:
    refresh_tracks: bool = False
    force_external_refresh: bool = False
    refresh_classification: bool = False
    # apply_changes:
    #   - True  => apply changes to Spotify
    #   - False => PREVIEW only (no write)
    apply_changes: bool = False


def _load_tracks_for_pipeline(
    token_info: Dict, opts: PipelineOptions
) -> tuple[List[Track], bool]:
    cached_tracks = load_tracks_cache()
    tracks_refreshed = False

    if opts.refresh_tracks or not cached_tracks:
        if cached_tracks and opts.refresh_tracks:
            log_step("Refreshing liked tracks from Spotify (forced)...")
        else:
            log_step("Fetching liked tracks from Spotify (no local cache)...")

        tracks = get_all_liked_tracks(token_info)
        save_tracks_cache(tracks)
        tracks_refreshed = True
    else:
        log_step("Using cached liked tracks.")
        tracks = cached_tracks

    log_info(f"Pipeline will use {len(tracks)} liked tracks.")
    return tracks, tracks_refreshed


def run_pipeline(opts: PipelineOptions) -> Dict[str, Any]:
    log_section("Spotify auto-playlists (pipeline)")

    token_info = load_spotify_token()
    user_id = get_current_user_id(token_info)
    playlists_existing = get_user_playlists(token_info)

    tracks, tracks_refreshed = _load_tracks_for_pipeline(token_info, opts)

    external_features, unmatched_tracks = enrich_tracks_with_external_features(
        tracks,
        force_refresh=opts.force_external_refresh,
    )

    classifications = classify_tracks_rule_based(
        tracks=tracks,
        external_features=external_features,
        refresh_existing=opts.refresh_classification,
    )

    mood_counts: Dict[str, int] = {}
    for c in classifications.values():
        mood_counts[c.mood] = mood_counts.get(c.mood, 0) + 1

    playlists_mood, playlists_genre, playlists_year = build_target_playlists(
        tracks,
        classifications,
    )

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


def run_pipeline_entrypoint() -> None:
    """
    CLI-friendly entrypoint that runs the full pipeline once with safe defaults.

    It is intended for manual runs and local testing from the command line,
    without going through the HTTP API. Behaviour is controlled by
    PipelineOptions and uses preview-only settings (no writes to Spotify).
    """
    opts = PipelineOptions(
        refresh_tracks=False,
        force_external_refresh=False,
        refresh_classification=False,
        apply_changes=False,  # safe-by-default: preview only
    )
    run_pipeline(opts)
    log_success("Pipeline run finished (entrypoint).")
