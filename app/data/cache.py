from dataclasses import asdict
from typing import Dict, List

from app.config import (
    CLASSIFICATION_CACHE_FILE,
    EXTERNAL_FEATURES_CACHE_FILE,
    TRACKS_CACHE_FILE,
)
from app.core import Classification, Track, log_warning, read_json, write_json

# ---------- Tracks cache ----------


def load_tracks_cache() -> List[Track]:
    """
    Charge le cache des tracks (liked tracks Spotify) depuis JSON.
    Retourne une liste de Track.
    """
    data = read_json(TRACKS_CACHE_FILE, default=[])
    if not isinstance(data, list):
        log_warning("Tracks cache file is corrupted; ignoring it.")
        return []

    tracks: List[Track] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        tracks.append(
            Track(
                id=item.get("id"),
                name=item.get("name"),
                artist=item.get("artist"),
                album=item.get("album"),
                release_date=item.get("release_date"),
                added_at=item.get("added_at"),
                features=item.get("features", {}) or {},
            )
        )
    return tracks


def save_tracks_cache(tracks: List[Track]) -> None:
    """
    Sauvegarde la liste des tracks dans le cache JSON.
    """
    payload = [asdict(t) for t in tracks]
    write_json(TRACKS_CACHE_FILE, payload)


# ---------- External features cache ----------


def load_external_features_cache() -> Dict[str, Dict]:
    """
    Charge le cache des features externes (MusicBrainz/AcousticBrainz).
    """

    def _on_error(e: Exception) -> None:
        log_warning("External features cache file is corrupted; ignoring it.")

    data = read_json(EXTERNAL_FEATURES_CACHE_FILE, default={}, on_error=_on_error)
    if not isinstance(data, dict):
        log_warning("External features cache has invalid structure; using empty dict.")
        return {}
    return data


def save_external_features_cache(cache: Dict[str, Dict]) -> None:
    """
    Sauvegarde le cache des features externes.
    """
    write_json(EXTERNAL_FEATURES_CACHE_FILE, cache)


# ---------- Classification cache ----------


def load_classification_cache() -> Dict[str, Classification]:
    """
    Charge le cache de classification et reconstruit les objets Classification.
    Structure JSON attendue :
      {
        "track_id": {
          "mood": "chill",
          "genre": "pop",
          "year": 2020
        },
        ...
      }
    """
    data = read_json(CLASSIFICATION_CACHE_FILE, default={})
    if not isinstance(data, dict):
        log_warning("Classification cache file is corrupted; ignoring it.")
        return {}

    result: Dict[str, Classification] = {}
    for track_id, payload in data.items():
        if not isinstance(payload, dict):
            continue
        result[track_id] = Classification(
            mood=payload.get("mood", "unclassified"),
            genre=payload.get("genre"),
            year=payload.get("year"),
        )
    return result


def save_classification_cache(classifications: Dict[str, Classification]) -> None:
    """
    Sauvegarde le cache de classification sous forme JSON sérialisable.
    """
    payload = {
        track_id: {
            "mood": c.mood,
            "genre": c.genre,
            "year": c.year,
        }
        for track_id, c in classifications.items()
    }
    write_json(CLASSIFICATION_CACHE_FILE, payload)
