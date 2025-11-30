import sys

from config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET
from spotify_client import (
    load_spotify_token,
    get_current_user_id,
    get_all_liked_tracks,
    get_user_playlists,
)
from cache_manager import (
    load_tracks_cache,
    save_tracks_cache,
)
from classifier import (
    classify_tracks_rule_based,
    load_classification_cache,
)
from cli_utils import (
    print_error,
    print_header,
    print_info,
    print_step,
    print_success,
    print_warning,
)
from external_features import enrich_tracks_with_external_features
from models import Track
from playlist_manager import build_target_playlists, sync_playlists
from reporting import write_unmatched_report


def get_tracks_with_cache(token_info) -> list[Track]:
    """
    Returns tracks (list of Track).
    Uses local cache and optionally refreshes from Spotify.
    """
    cached_tracks = load_tracks_cache()
    if cached_tracks:
        print_info(f"Found {len(cached_tracks)} tracks in local cache.")
        answer = (
            input("→ Do you want to refresh them from Spotify? [Y/n] ").strip().lower()
        )
        if answer in ("n", "no"):
            print_step("Using local cached tracks (no Spotify request).")
            return cached_tracks
        print_step("Refreshing tracks from Spotify...")

    tracks = get_all_liked_tracks(token_info)
    save_tracks_cache(tracks)
    return tracks


def ask_refresh_classification_decision() -> bool:
    """
    Look at local classification cache.
    If entries exist, ask user whether to refresh them.
    Returns True if we should refresh all classifications, False otherwise.
    """
    cache = load_classification_cache()
    if not cache:
        return False

    count = len(cache)
    print_info(f"Found {count} tracks in local classification cache.")
    answer = (
        input(
            "→ Do you want to recompute ALL classifications from scratch (ignore cache)? [Y/n] "
        )
        .strip()
        .lower()
    )

    if answer in ("n", "no"):
        print_step(
            "Keeping existing classifications; only new tracks will be classified."
        )
        return False

    print_step("All classifications will be recomputed from scratch.")
    return True


def main(use_cli_auth: bool = False) -> None:
    # 0) Basic config check
    if not (SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET):
        print_error(
            "Please set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in the .env file."
        )
        return

    print_header("Spotify auto-playlists")

    # 1) Auth + user + existing playlists
    print_step("Loading Spotify token...")
    token_info = load_spotify_token(use_cli_auth=use_cli_auth)

    print_step("Fetching current Spotify user...")
    user_id = get_current_user_id(token_info)

    print_step("Fetching existing playlists from Spotify...")
    playlists_existing = get_user_playlists(token_info)

    # 2) Liked tracks with local cache
    print_header("Liked tracks")
    tracks = get_tracks_with_cache(token_info)

    # 3) External mood/genre features (MusicBrainz + AcousticBrainz)
    print_header("External mood/genre features")
    external_features, unmatched_tracks = enrich_tracks_with_external_features(
        tracks,
        force_refresh=False,
    )

    # 4) Report for tracks without external data
    if unmatched_tracks:
        report_path = write_unmatched_report(
            unmatched_tracks,
            filename="unmatched_external_features.md",
        )
        print_warning(f"External features missing for {len(unmatched_tracks)} tracks.")
        print_step(f"See report: {report_path}")
    else:
        print_success("All tracks have external mood/genre features.")

    # 5) Classification (rule-based)
    print_header("Classification")
    refresh_classification = ask_refresh_classification_decision()
    classifications = classify_tracks_rule_based(
        tracks=tracks,
        external_features=external_features,
        refresh_existing=refresh_classification,
    )

    # 6) Build target playlists from classifications
    print_header("Building target playlists")
    playlists_mood, playlists_genre, playlists_year = build_target_playlists(
        tracks,
        classifications,
    )

    # 7) Sync playlists with preview & .diff files
    print_header("Syncing playlists to Spotify")
    track_map = {t.id: t for t in tracks}
    sync_playlists(
        token_info=token_info,
        user_id=user_id,
        playlists_existing=playlists_existing,
        playlists_mood=playlists_mood,
        playlists_genre=playlists_genre,
        playlists_year=playlists_year,
        track_map=track_map,
    )

    print_success("Synchronization complete!")


if __name__ == "__main__":
    use_cli_auth = "--cli-auth" in sys.argv
    main(use_cli_auth=use_cli_auth)
