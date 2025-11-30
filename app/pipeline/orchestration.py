from dataclasses import dataclass
from typing import Dict, Any, List

from app.pipeline.cache_manager import load_tracks_cache, save_tracks_cache
from app.pipeline.classifier import (
    classify_tracks_rule_based,
)
from app.pipeline.external_features import enrich_tracks_with_external_features
from app.pipeline.playlist_manager import build_target_playlists, sync_playlists
from app.pipeline.reporting import write_unmatched_report
from app.spotify.auth import load_spotify_token, get_current_user_id
from app.spotify.tracks import get_all_liked_tracks
from app.spotify.playlists import get_user_playlists
from app.core.cli_utils import (
    print_step,
    print_info,
    print_header,
    print_success,
)
from app.core.models import Track


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
            print_step("Refreshing liked tracks from Spotify (forced)...")
        else:
            print_step("Fetching liked tracks from Spotify (no local cache)...")

        tracks = get_all_liked_tracks(token_info)
        save_tracks_cache(tracks)
        tracks_refreshed = True
    else:
        print_step("Using cached liked tracks.")
        tracks = cached_tracks

    print_info(f"Pipeline will use {len(tracks)} liked tracks.")
    return tracks, tracks_refreshed


def run_pipeline(opts: PipelineOptions) -> Dict[str, Any]:
    print_header("Spotify auto-playlists (API pipeline)")

    token_info = load_spotify_token()
    user_id = get_current_user_id(token_info)
    playlists_existing = get_user_playlists(token_info)

    tracks, tracks_refreshed = _load_tracks_for_pipeline(token_info, opts)

    external_features, unmatched_tracks = enrich_tracks_with_external_features(
        tracks,
        force_refresh=opts.force_external_refresh,
    )
    if unmatched_tracks:
        report_path = write_unmatched_report(
            unmatched_tracks,
            filename="unmatched_external_features.md",
        )
        print_info(
            f"External features missing for {len(unmatched_tracks)} tracks. "
            f"Report: {report_path}"
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


def run_cli_pipeline() -> None:
    """
    Simple CLI runner around the pipeline.
    No interactive prompts: behaviour is fully controlled by PipelineOptions.
    """
    opts = PipelineOptions(
        refresh_tracks=False,
        force_external_refresh=False,
        refresh_classification=False,
        apply_changes=False,  # safe-by-default: preview only
    )
    run_pipeline(opts)
    print_success("Pipeline run finished (CLI helper).")
