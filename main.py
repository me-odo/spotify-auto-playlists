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
    classify_tracks,
    load_classification_cache,
)
from models import Track
from playlist_manager import build_target_playlists, sync_playlists
from external_features import enrich_tracks_with_external_features
from reporting import write_unmatched_report


def get_tracks_with_cache(token_info) -> list[Track]:
    """
    Returns tracks (list of Track).
    Uses local cache and optionally refreshes from Spotify.
    """
    cached_tracks = load_tracks_cache()
    if cached_tracks:
        print(f"Found {len(cached_tracks)} tracks in local cache.")
        answer = (
            input("Do you want to refresh them from Spotify? [Y/n] ").strip().lower()
        )
        if answer in ("n", "no"):
            print("→ Using local cached tracks (no Spotify request).")
            return cached_tracks
        print("→ Refreshing tracks from Spotify...")

    tracks = get_all_liked_tracks(token_info)
    save_tracks_cache(tracks)
    return tracks


def ask_refresh_classification_decision() -> bool:
    """
    Regarde le cache local de classification.
    Si des titres existent déjà en cache, demande à l'utilisateur
    s'il veut les rafraîchir.
    Retourne True si on doit rafraîchir, False sinon.
    """
    cache = load_classification_cache()
    if not cache:
        # Pas de cache existant, rien à demander
        return False

    count = len(cache)
    print(f"Found {count} titles locally in classification cache.")
    answer = input("Do you want to refresh ALL classifications? [Y/n] ").strip().lower()

    if answer in ("n", "no", "non"):
        print(
            "→ Using existing classification cache; only new titles will be classified."
        )
        return False

    print("→ Classification cache will be refreshed; all titles will be reclassified.")
    return True


def main() -> None:
    # 0) Basic config check
    if not (SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET):
        print(
            "⚠ Please set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in the .env file."
        )
        return

    # 1) Auth + user + existing playlists
    token_info = load_spotify_token()
    user_id = get_current_user_id(token_info)
    playlists_existing = get_user_playlists(token_info)

    # 2) Liked tracks with local cache
    tracks = get_tracks_with_cache(token_info)

    # 3) External mood/genre features (MusicBrainz + AcousticBrainz)
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
        print(f"External features: {len(unmatched_tracks)} tracks unmatched.")
        print(f"→ See report: {report_path}")
    else:
        print("All tracks have external mood/genre features.")

    # 5) Classification (using external features only)
    refresh_classification = ask_refresh_classification_decision()
    classifications = classify_tracks(
        tracks=tracks,
        refresh_existing=refresh_classification,
    )

    # 6) Build target playlists from classifications
    playlists_mood, playlists_genre, playlists_year = build_target_playlists(
        tracks,
        classifications,
    )

    # 7) Sync playlists with preview & .diff files
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

    print("✅ Synchronization complete!")


if __name__ == "__main__":
    main()
