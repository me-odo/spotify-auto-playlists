from typing import Dict, List

from app.core.models import Classification, Track
from app.data.cache import (
    load_classification_cache as _load_classification_cache,
    load_external_features_cache as _load_external_features_cache,
    load_tracks_cache as _load_tracks_cache,
    save_classification_cache as _save_classification_cache,
    save_external_features_cache as _save_external_features_cache,
    save_tracks_cache as _save_tracks_cache,
)


def load_tracks_cache() -> List[Track]:
    return _load_tracks_cache()


def save_tracks_cache(tracks: List[Track]) -> None:
    _save_tracks_cache(tracks)


def load_external_features_cache() -> Dict[str, Dict]:
    return _load_external_features_cache()


def save_external_features_cache(cache: Dict[str, Dict]) -> None:
    _save_external_features_cache(cache)


def load_classification_cache() -> Dict[str, Classification]:
    return _load_classification_cache()


def save_classification_cache(classifications: Dict[str, Classification]) -> None:
    _save_classification_cache(classifications)


__all__ = [
    "load_tracks_cache",
    "save_tracks_cache",
    "load_external_features_cache",
    "save_external_features_cache",
    "load_classification_cache",
    "save_classification_cache",
]
