from typing import Dict, List, Mapping

from app.core.models import Classification, Track
from app.pipeline.classifier import classify_tracks_rule_based


class Classifier:
    """Abstract classifier that assigns labels to tracks based on features."""

    id: str

    def run(
        self,
        tracks: List[Track],
        all_features: Mapping[str, Dict[str, dict]],
    ) -> Dict[str, Classification]:
        """
        Run the classifier for the given tracks.

        Parameters
        ----------
        tracks:
            List of tracks to classify.
        all_features:
            Mapping of provider_id -> {track_id -> features dict}.

        Returns
        -------
        Dict[str, Classification]
            Mapping from track_id to Classification.
        """
        raise NotImplementedError


class MoodClassifierV1(Classifier):
    """
    Classifier wrapper that delegates to classify_tracks_rule_based.

    It expects features produced by the acousticbrainz FeatureProvider, but if a
    different structure is passed, it will fall back to using the mapping as-is.
    """

    id = "mood_v1"

    def run(
        self,
        tracks: List[Track],
        all_features: Mapping[str, Dict[str, dict]],
    ) -> Dict[str, Classification]:
        # Preferred: look up features from the acousticbrainz provider.
        external_features: Dict[str, dict]

        provider_features = all_features.get("acousticbrainz")
        if isinstance(provider_features, dict):
            external_features = provider_features
        else:
            # Fallback: when a single flat mapping is provided instead of
            # a provider_id -> mapping structure.
            external_features = dict(provider_features or {})

        return classify_tracks_rule_based(
            tracks=tracks,
            external_features=external_features,
            refresh_existing=False,
        )


CLASSIFIERS: Dict[str, Classifier] = {
    MoodClassifierV1.id: MoodClassifierV1(),
}
