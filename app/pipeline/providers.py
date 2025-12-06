from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from app.core import Track

from .external_features import enrich_tracks_with_external_features


class FeatureProvider(ABC):
    """
    Abstract provider of features for a collection of tracks.

    Each provider exposes:
      - id      : stable identifier (e.g. "acousticbrainz")
      - type    : provider type ("external", "local", ...)
      - version : optional version string for the provider implementation

    Concrete providers must implement `run()` to return a mapping:
        track_id -> provider-specific feature payload (plain dicts).
    """

    id: str
    type: str = "external"
    version: Optional[str] = None

    @abstractmethod
    def run(self, tracks: List[Track]) -> Dict[str, Dict]:
        """
        Resolve features for the given tracks and return a mapping:
            track_id -> provider-specific feature payload.
        """
        raise NotImplementedError


class AcousticBrainzProvider(FeatureProvider):
    """
    Feature provider backed by the existing MusicBrainz + AcousticBrainz
    enrichment logic from app.pipeline.external_features.

    This provider delegates all I/O and caching to `enrich_tracks_with_external_features`
    and only exposes the final external_features mapping.
    """

    id = "acousticbrainz"
    type = "external"
    version = "v1"

    def run(self, tracks: List[Track]) -> Dict[str, Dict]:
        external_features, _unmatched = enrich_tracks_with_external_features(
            tracks=tracks,
            force_refresh=False,
        )
        return external_features


FEATURE_PROVIDERS: Dict[str, FeatureProvider] = {
    AcousticBrainzProvider.id: AcousticBrainzProvider(),
}


def get_feature_provider(provider_id: str) -> FeatureProvider:
    """
    Return the registered FeatureProvider for the given identifier.

    Raises KeyError if the provider_id is unknown.
    """
    return FEATURE_PROVIDERS[provider_id]


def list_feature_providers() -> List[Dict[str, str]]:
    """
    Return a lightweight description of all registered feature providers.

    Each entry is a plain dict with:
      - id      : provider id
      - type    : provider type
      - version : provider version (empty string if not set)
    """
    providers: List[Dict[str, str]] = []
    for provider in FEATURE_PROVIDERS.values():
        providers.append(
            {
                "id": provider.id,
                "type": provider.type,
                "version": provider.version or "",
            }
        )
    return providers
