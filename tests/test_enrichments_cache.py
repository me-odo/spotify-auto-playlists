from datetime import datetime
import json
from pathlib import Path
from typing import Dict, List

from app.core import TrackEnrichment
from app.data import load_enrichments_cache, save_enrichments_cache


def test_enrichments_cache_roundtrip(tmp_path: Path, monkeypatch) -> None:
    cache_path = tmp_path / "enrichments.json"
    monkeypatch.setattr(
        "app.data.enrichments.ENRICHMENTS_FILE",
        str(cache_path),
        raising=False,
    )

    enrichments: Dict[str, List[TrackEnrichment]] = {
        "track1": [
            TrackEnrichment(
                source="test_source",
                version="v1",
                timestamp=datetime(2025, 1, 1, 12, 0, 0),
                categories={"mood": "chill", "energy": "low"},
            )
        ]
    }

    save_enrichments_cache(enrichments)
    loaded = load_enrichments_cache()

    assert "track1" in loaded
    track_entries = loaded["track1"]
    assert isinstance(track_entries, list)
    assert len(track_entries) == 1

    entry = track_entries[0]
    assert isinstance(entry, TrackEnrichment)
    assert entry.categories["mood"] == "chill"
    assert entry.categories["energy"] == "low"


def test_enrichments_cache_skips_invalid_entries(tmp_path: Path, monkeypatch) -> None:
    cache_path = tmp_path / "enrichments_invalid.json"
    monkeypatch.setattr(
        "app.data.enrichments.ENRICHMENTS_FILE",
        str(cache_path),
        raising=False,
    )

    valid_entry = {
        "source": "valid_source",
        "version": "v1",
        "timestamp": datetime(2025, 1, 1, 12, 0, 0).isoformat(),
        "categories": {"mood": "chill"},
    }

    data = {
        # Valid list with one good entry and several invalid ones
        "track_valid": [
            valid_entry,
            123,  # non-dict entry
            {
                "source": "no_categories",
                "timestamp": datetime(2025, 1, 1, 13, 0, 0).isoformat(),
            },
        ],
        # Not a list at all: should be skipped entirely
        "track_not_list": {"foo": "bar"},
        # List of dicts with invalid shapes: all should be skipped
        "track_invalid_list": [
            {
                "source": "missing_categories",
                "timestamp": datetime(2025, 1, 1, 14, 0, 0).isoformat(),
            },
            {"categories": {"mood": "x"}},  # missing source / timestamp
        ],
    }

    cache_path.write_text(json.dumps(data), encoding="utf-8")

    loaded = load_enrichments_cache()

    # Only the valid track with a single valid TrackEnrichment should remain
    assert set(loaded.keys()) == {"track_valid"}
    entries = loaded["track_valid"]
    assert isinstance(entries, list)
    assert len(entries) == 1

    entry = entries[0]
    assert isinstance(entry, TrackEnrichment)
    assert entry.categories["mood"] == "chill"
