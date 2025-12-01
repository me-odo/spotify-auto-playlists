from typing import Any, Dict, List

from app.core import Track

from .cache import (
    load_classification_cache,
    load_tracks_cache,
    save_classification_cache,
    save_tracks_cache,
)


class TracksRepository:
    """Repository for reading and writing the tracks cache."""

    def load_tracks(self) -> List[Track] | List[Dict[str, Any]]:
        """Load tracks from the JSON-backed cache without changing their structure."""

        tracks = load_tracks_cache() or []
        return tracks

    def save_tracks(self, tracks: Any) -> None:
        """Persist tracks to the JSON-backed cache."""

        save_tracks_cache(tracks)


class ClassificationRepository:
    """Repository for reading and writing classification cache entries."""

    def load_classifications(self, classifier_id: str) -> Dict[str, Any]:
        """Load classifications for the given classifier id.

        The underlying storage is a single JSON cache; the classifier id is
        validated by callers at the API layer and does not change where data
        is stored.
        """

        cache = load_classification_cache() or {}
        return cache

    def save_classifications(
        self,
        classifier_id: str,
        data: Dict[str, Any],
    ) -> None:
        """Persist classifications for the given classifier id."""

        save_classification_cache(data)
