from typing import Dict, List

from app.core import Track
from app.pipeline import FEATURE_PROVIDERS, get_feature_provider


def _make_track(track_id: str) -> Track:
    """
    Helper to build a minimal Track instance for testing providers.
    """
    return Track(
        id=track_id,
        name=f"Track {track_id}",
        artist="Test Artist",
        album="Test Album",
        release_date=None,
        added_at=None,
        features={},
    )


def test_feature_providers_registry_contains_acousticbrainz() -> None:
    assert "acousticbrainz" in FEATURE_PROVIDERS

    provider = get_feature_provider("acousticbrainz")

    assert provider.id == "acousticbrainz"
    assert provider.type == "external"
    assert provider.version == "v1"


def test_acousticbrainz_provider_delegates_to_external_features(monkeypatch) -> None:
    calls: Dict[str, object] = {}

    def fake_enrich_tracks_with_external_features(
        tracks: List[Track],
        force_refresh: bool = False,
    ):
        # Record the arguments so we can assert on them later.
        calls["tracks"] = tracks
        calls["force_refresh"] = force_refresh
        # Return a deterministic external_features mapping and empty unmatched list.
        return {"t1": {"mood": "chill"}}, []

    # Patch the provider module to avoid any real external I/O.
    monkeypatch.setattr(
        "app.pipeline.providers.enrich_tracks_with_external_features",
        fake_enrich_tracks_with_external_features,
        raising=True,
    )

    tracks = [_make_track("t1"), _make_track("t2")]

    provider = get_feature_provider("acousticbrainz")
    result = provider.run(tracks)

    # The provider must return exactly the external_features mapping from the delegate.
    assert result == {"t1": {"mood": "chill"}}

    # The delegate must have been called with all tracks and force_refresh=False.
    assert "tracks" in calls
    assert "force_refresh" in calls
    called_tracks = calls["tracks"]
    assert isinstance(called_tracks, list)
    assert {t.id for t in called_tracks} == {"t1", "t2"}
    assert calls["force_refresh"] is False
