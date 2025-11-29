import json
import os
from dataclasses import asdict
from typing import Dict, List, Tuple

from config import TRACKS_CACHE_FILE, FEATURES_CACHE_FILE
from models import Track
from spotify_client import get_audio_features


def _ensure_dir(path: str) -> None:
    directory = os.path.dirname(path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)


# -------------------------
# 1) Cache des tracks
# -------------------------


def load_tracks_cache() -> List[Track]:
    if not os.path.exists(TRACKS_CACHE_FILE):
        return []
    with open(TRACKS_CACHE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [Track(**item) for item in data]


def save_tracks_cache(tracks: List[Track]) -> None:
    _ensure_dir(TRACKS_CACHE_FILE)
    data = [asdict(t) for t in tracks]
    with open(TRACKS_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# -------------------------
# 2) Cache des audio features
# -------------------------


def load_features_cache() -> Dict[str, Dict]:
    if not os.path.exists(FEATURES_CACHE_FILE):
        return {}
    with open(FEATURES_CACHE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_features_cache(features: Dict[str, Dict]) -> None:
    _ensure_dir(FEATURES_CACHE_FILE)
    with open(FEATURES_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(features, f, ensure_ascii=False, indent=2)


def get_features_for_tracks_with_cache(
    token_info: Dict,
    tracks: List[Track],
    tracks_refreshed: bool,
) -> Dict[str, Dict]:
    """
    - Charge le cache des audio features.
    - Si les tracks n'ont PAS été rafraîchies et qu'un cache existe :
        → on réutilise le cache tel quel (pas de nouvel appel Spotify).
    - Si les tracks ont été rafraîchies :
        → on peut rafraîchir complètement ou compléter seulement les IDs manquants.
    """
    existing_features = load_features_cache()
    track_ids = [t.id for t in tracks if t.id]

    if not existing_features:
        # Pas de cache → on doit aller chercher les features
        print("No audio features cache found. Fetching audio features from Spotify…")
        new_features = get_audio_features(token_info, track_ids)
        save_features_cache(new_features)
        return new_features

    if not tracks_refreshed:
        # Tracks pas rafraîchies + cache existant -> on réutilise tel quel
        print(
            f"Found {len(existing_features)} audio features locally. "
            "Tracks cache not refreshed, so we reuse them."
        )
        return existing_features

    # Ici : tracks ont été rafraîchies ET on a déjà un cache de features
    print(f"Found {len(existing_features)} audio features locally.")
    answer = (
        input("Do you want to refresh audio features for all tracks? [Y/n] ")
        .strip()
        .lower()
    )

    if answer in ("n", "no", "non"):
        print("→ Keeping existing audio features; fetching only missing ones.")
        missing_ids = [tid for tid in track_ids if tid not in existing_features]
        if missing_ids:
            print(f"Fetching audio features for {len(missing_ids)} missing tracks…")
            extra = get_audio_features(token_info, missing_ids)
            merged = {**existing_features, **extra}
        else:
            merged = existing_features
        save_features_cache(merged)
        return merged

    # Refresh complet
    print("→ Refreshing audio features for all tracks.")
    new_features = get_audio_features(token_info, track_ids)
    save_features_cache(new_features)
    return new_features
