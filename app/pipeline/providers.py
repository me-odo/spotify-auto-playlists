from typing import Dict, List

from app.core import Track

from .external_features import enrich_tracks_with_external_features


class FeatureProvider:
    """Abstract provider of external features for a collection of tracks."""

    id: str

    def run(self, tracks: List[Track]) -> Dict[str, Dict]:
        """
        Resolve features for the given tracks and return a mapping:
            track_id -> provider-specific feature payload.

        Concrete providers must implement this method.
        """
        raise NotImplementedError


class AcousticBrainzProvider(FeatureProvider):
    """
    Feature provider backed by the existing MusicBrainz + AcousticBrainz
    enrichment logic from app.pipeline.external_features.
    """

    id = "acousticbrainz"

    def run(self, tracks: List[Track]) -> Dict[str, Dict]:
        external_features, _unmatched = enrich_tracks_with_external_features(
            tracks=tracks,
            force_refresh=False,
        )
        return external_features


FEATURE_PROVIDERS: Dict[str, FeatureProvider] = {
    AcousticBrainzProvider.id: AcousticBrainzProvider(),
}
