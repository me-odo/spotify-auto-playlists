import json
import os
from typing import Any, Dict, List

from app.config import CACHE_DIR
from app.core import TrackEnrichment, read_json, write_json

ENRICHMENTS_FILE = os.path.join(CACHE_DIR, "enrichments.json")


def load_enrichments_cache() -> Dict[str, List[TrackEnrichment]]:
    """
    Load the unified track enrichment cache from JSON.

    The on-disk structure is:
      {
        "track_id": [
          { "source": "...", "version": "...", "timestamp": "...", "categories": {...} },
          ...
        ],
        ...
      }
    """
    data = read_json(ENRICHMENTS_FILE, default={})
    if not isinstance(data, dict):
        return {}

    result: Dict[str, List[TrackEnrichment]] = {}
    for track_id, raw_entries in data.items():
        if not isinstance(raw_entries, list):
            continue
        entries: List[TrackEnrichment] = []
        for item in raw_entries:
            if not isinstance(item, dict):
                continue
            try:
                entries.append(TrackEnrichment(**item))
            except Exception:
                # Ignore malformed entries
                continue
        if entries:
            result[str(track_id)] = entries

    return result


def save_enrichments_cache(
    enrichments: Dict[str, List[TrackEnrichment]],
) -> None:
    """
    Persist the enrichment cache to JSON using plain dicts.
    """
    payload: Dict[str, List[Dict[str, Any]]] = {}
    for track_id, entries in enrichments.items():
        serialised: List[Dict[str, Any]] = []
        for entry in entries:
            if isinstance(entry, TrackEnrichment):
                # Ensure datetime and other complex types are JSON-serialisable.
                if hasattr(entry, "model_dump"):
                    # Pydantic v2 style
                    serialised.append(entry.model_dump(mode="json"))
                else:
                    # Pydantic v1 style
                    serialised.append(json.loads(entry.json()))
            elif isinstance(entry, dict):
                serialised.append(dict(entry))
            else:
                # Best-effort: skip unsupported entry types instead of failing.
                continue
        if serialised:
            payload[str(track_id)] = serialised

    write_json(ENRICHMENTS_FILE, payload)
