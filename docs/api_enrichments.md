# Enrichments API

This document describes the HTTP endpoints related to track enrichments.

The enrichments system aggregates information from different providers (external APIs,
future LLM-based enrichers, and manual annotations) into a unified JSON-backed cache.

## Data model

Unified enrichments are represented as `TrackEnrichment` objects:

```python
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel

class TrackEnrichment(BaseModel):
    source: str
    version: Optional[str] = None
    timestamp: datetime
    categories: Dict[str, Any]
```

- `source`: logical source name (e.g. `"external_features"`, `"llm_v1"`, `"manual"`).
- `version`: optional version of the enrichment process.
- `timestamp`: when the enrichment was computed.
- `categories`: flat key/value mapping of enrichment fields:
  - Examples: `{"mood": "happy", "energy": 0.8, "genre": "rock"}`.

The on-disk cache is a JSON file:

```json
{
  "track_id": [
    {
      "source": "external_features",
      "version": "v1",
      "timestamp": "...",
      "categories": { "mood": "dark", "energy": 0.7 }
    }
  ]
}
```

## Storage helpers

Located in `app/data/enrichments.py` and exported via `app.data`:

```python
from app.data import load_enrichments_cache, save_enrichments_cache
```

- `load_enrichments_cache() -> Dict[str, List[TrackEnrichment]]`
- `save_enrichments_cache(mapping)` – atomic JSON write of the enrichment map.

## Enrichment from external features

When the `external_features` pipeline step runs (MusicBrainz / AcousticBrainz side),
it not only updates the external-features cache but also populates the unified enrichment
cache.

The helper `_update_enrichment_cache_from_external()`:

- loads existing enrichments,
- for each track id, appends a new `TrackEnrichment` with:
  - `source = "external_features"`,
  - `version = "v1"`,
  - `timestamp = now`,
  - `categories = external_features_for_track`,
- writes back via `save_enrichments_cache()`.

This ensures that every time external features are enriched, they are also available in
the unified enrichment view.

## HTTP API – GET /data/enrichments

### Endpoint

- **Method**: `GET`
- **Path**: `/data/enrichments`
- **Tags**: `data`

### Behaviour

Returns a JSON object mapping `track_id` to a list of enrichment entries. The response is
always a plain JSON structure (no Pydantic-specific fields):

```json
{
  "track_id_1": [
    {
      "source": "external_features",
      "version": "v1",
      "timestamp": "2024-01-01T12:00:00Z",
      "categories": {
        "mood": "energetic",
        "energy": 0.9
      }
    }
  ],
  "track_id_2": []
}
```

If no enrichments exist, the endpoint returns an empty object `{}`.

### Semantics

- The endpoint is read-only and safe to call frequently.
- It is designed for frontend consumption to:
  - highlight which tracks have been enriched,
  - display enrichment sources,
  - allow users to filter on enrichment status.
- The smoke test validates:
  - that the response is a JSON object,
  - if any entries exist, each value is a list.

## Future extensions

Planned enrichment sources:

- Local LLM-based enrichers (embedding similarity, local classification).
- Remote LLM-based enrichers (OpenAI, etc.).
- Manual enrichment from the UI (user edits).

All future enrichments will be funnelled through the same `TrackEnrichment` model and
`enrichments.json` file so that the rules engine can operate on a unified view.
