from typing import Dict, List

from app.core import Classification, log_info, log_step
from app.spotify import (
    SpotifyTokenMissing,
    get_all_liked_tracks,
    get_user_playlists,
    load_spotify_token,
)

from .cache_manager import (
    load_classification_cache,
    load_external_features_cache,
    load_tracks_cache,
    save_tracks_cache,
)
from .classifier import classify_tracks_rule_based
from .external_features import enrich_tracks_with_external_features
from .playlist_manager import build_target_playlists, preview_playlist_diffs

SUPPORTED_STEPS = {"tracks", "external", "classify", "build", "diff", "apply"}


def _run_tracks_step() -> Dict:
    """Run the tracks step synchronously and return summary stats."""
    try:
        token_info = load_spotify_token()
    except SpotifyTokenMissing as e:
        # Let the caller handle authentication errors.
        raise e

    cached_tracks = load_tracks_cache()
    tracks = cached_tracks
    refreshed = False

    if not cached_tracks:
        log_step("Fetching liked tracks from Spotify (no local cache)...")
    else:
        log_step("Using cached liked tracks.")
    # We deliberately do not expose a force_refresh flag here; jobs always
    # behave like the default synchronous endpoint (no forced refresh).

    if not cached_tracks:
        tracks = get_all_liked_tracks(token_info)
        save_tracks_cache(tracks)
        refreshed = True

    log_info(f"Tracks job: {len(tracks)} tracks (refreshed={refreshed}).")

    return {
        "step": "tracks",
        "status": "done",
        "tracks_count": len(tracks),
        "from_cache": not refreshed,
        "fetched_from_spotify": len(tracks) if refreshed else 0,
    }


def _run_external_step() -> Dict:
    """Run the external enrichment step and return basic counts."""
    tracks = load_tracks_cache()
    if not tracks:
        raise RuntimeError("Tracks cache is empty. Run the tracks step first.")

    log_step("External features job...")

    external_features, unmatched_tracks = enrich_tracks_with_external_features(
        tracks=tracks,
        force_refresh=False,
    )

    log_info(
        f"External job: {len(external_features)} entries, "
        f"{len(unmatched_tracks)} unmatched.",
    )

    return {
        "step": "external",
        "status": "done",
        "total_tracks": len(tracks),
        "enriched": len(external_features),
        "unmatched": len(unmatched_tracks),
    }


def _run_classify_step() -> Dict:
    """Run the classification step and return mood distribution."""
    tracks = load_tracks_cache()
    if not tracks:
        raise RuntimeError("Tracks cache is empty. Run the tracks step first.")

    external_features = load_external_features_cache()
    if not external_features:
        raise RuntimeError(
            "External features cache is empty. Run the external step first."
        )

    log_step("Classify job...")

    classifications: Dict[str, Classification] = classify_tracks_rule_based(
        tracks=tracks,
        external_features=external_features,
        refresh_existing=False,
    )

    mood_counts: Dict[str, int] = {}
    for c in classifications.values():
        mood_counts[c.mood] = mood_counts.get(c.mood, 0) + 1

    log_info(f"Classification job done for {len(classifications)} tracks.")

    return {
        "step": "classify",
        "status": "done",
        "tracks_processed": len(classifications),
        "moods": mood_counts,
    }


def _run_build_step() -> Dict:
    """Run the build playlists step and return playlist counts."""
    tracks = load_tracks_cache()
    if not tracks:
        raise RuntimeError("Tracks cache is empty. Run the tracks step first.")

    classifications = load_classification_cache()
    if not classifications:
        raise RuntimeError(
            "Classification cache is empty. Run the classify step first."
        )

    playlists_mood, playlists_genre, playlists_year = build_target_playlists(
        tracks,
        classifications,
    )

    target_playlists: Dict[str, List[str]] = {}
    for source in (playlists_mood, playlists_genre, playlists_year):
        for name, ids in source.items():
            bucket = target_playlists.setdefault(name, [])
            for tid in ids:
                if tid not in bucket:
                    bucket.append(tid)

    log_info(f"Build job: {len(target_playlists)} target playlists.")

    return {
        "step": "build",
        "status": "done",
        "playlists_count": len(target_playlists),
        "playlist_names": list(target_playlists.keys()),
    }


def _run_diff_step() -> Dict:
    """Run the diff computation step and return the number of playlists diffed."""
    try:
        token_info = load_spotify_token()
    except SpotifyTokenMissing as e:
        raise e

    tracks = load_tracks_cache()
    if not tracks:
        raise RuntimeError("Tracks cache is empty. Run the tracks step first.")

    classifications = load_classification_cache()
    if not classifications:
        raise RuntimeError(
            "Classification cache is empty. Run the classify step first."
        )

    playlists_existing = get_user_playlists(token_info)

    playlists_mood, playlists_genre, playlists_year = build_target_playlists(
        tracks,
        classifications,
    )

    log_step("Diff job: computing playlist diffs (preview)...")
    diffs_raw = preview_playlist_diffs(
        token_info=token_info,
        playlists_existing=playlists_existing,
        playlists_mood=playlists_mood,
        playlists_genre=playlists_genre,
        playlists_year=playlists_year,
    )

    log_info(f"Diff job: {len(diffs_raw)} playlists analyzed.")

    return {
        "step": "diff",
        "status": "done",
        "playlists_count": len(diffs_raw),
    }


def _run_apply_step() -> Dict:
    """
    Run the apply step.

    The current synchronous /pipeline/apply endpoint expects an explicit
    payload from the frontend, so there is no meaningful way to run this
    step without additional input. For now we expose a clear error.
    """
    raise RuntimeError(
        "Async apply step is not supported without an explicit playlist payload."
    )


def run_step_for_job(step: str) -> Dict:
    """
    Execute the given pipeline step synchronously and return a lightweight payload.

    Supported steps:
      - tracks
      - external
      - classify
      - build
      - diff
      - apply (currently raises a clear error)

    The returned dict is intended to be stored on a PipelineJob payload field
    so that the frontend can inspect basic job results (counts, simple stats).
    """
    if step not in SUPPORTED_STEPS:
        raise ValueError(f"Unsupported pipeline step: {step!r}")

    if step == "tracks":
        return _run_tracks_step()
    if step == "external":
        return _run_external_step()
    if step == "classify":
        return _run_classify_step()
    if step == "build":
        return _run_build_step()
    if step == "diff":
        return _run_diff_step()
    if step == "apply":
        return _run_apply_step()

    # This line should not be reachable due to the SUPPORTED_STEPS guard.
    raise ValueError(f"Unsupported pipeline step: {step!r}")
