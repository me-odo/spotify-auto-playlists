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
    get_features_for_tracks_with_cache,
)
from classifier import (
    classify_tracks,
    load_classification_cache,
)
from playlist_manager import build_target_playlists, sync_playlists


def get_tracks_with_cache(token_info) -> tuple[list, bool]:
    """
    Returns (tracks, tracks_refreshed)
    - tracks: list of Track
    - tracks_refreshed: True if we fetched liked tracks from Spotify again.
    """
    cached_tracks = load_tracks_cache()
    if cached_tracks:
        print(f"Found {len(cached_tracks)} tracks in local cache.")
        answer = (
            input("Do you want to refresh them from Spotify? [Y/n] ").strip().lower()
        )
        if answer in ("n", "no"):
            print("→ Using local cached tracks (no Spotify request).")
            return cached_tracks, False
        print("→ Refreshing tracks from Spotify...")

    tracks = get_all_liked_tracks(token_info)
    save_tracks_cache(tracks)
    return tracks, True


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


def main():
    if not (SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET):
        print(
            "⚠ Please set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in the .env file."
        )
        return

    token_info = load_spotify_token()
    user_id = get_current_user_id(token_info)

    # 1) Cache des tracks
    tracks, tracks_refreshed = get_tracks_with_cache(token_info)

    # 2) Cache des audio features
    features_by_id = get_features_for_tracks_with_cache(
        token_info, tracks, tracks_refreshed
    )

    # 3) Cache des classifications (GPT)
    refresh_classif = ask_refresh_classification_decision()
    classifications = classify_tracks(
        tracks, features_by_id, refresh_existing=refresh_classif
    )

    playlists_existing = get_user_playlists(token_info)

    playlists_mood, playlists_genre, playlists_year = build_target_playlists(
        tracks, classifications
    )
    track_map = {t.id: t for t in tracks}

    sync_playlists(
        token_info,
        user_id,
        playlists_existing,
        playlists_mood,
        playlists_genre,
        playlists_year,
        track_map,
    )

    print("✓ Synchronization complete!")


if __name__ == "__main__":
    main()
