# Spotify Auto-Playlists

Automatically generate and maintain mood-based Spotify playlists from your liked tracks.

This project fetches your saved tracks, enriches them with external audio features (via MusicBrainz/AcousticBrainz), classifies them into moods (workout, chill, sleep, etc.), and keeps a set of Spotify playlists in sync.

The application is designed primarily as a **backend service**:
- A reusable **pipeline** module (`app.pipeline`) that orchestrates all steps.
- A **FastAPI** application exposing a `/run` endpoint to trigger the pipeline.

A Python entrypoint script is optional and not required for normal usage; the recommended way to run the pipeline is through the API.

---

## Features

- Fetch all your **liked tracks** from Spotify.
- Enrich tracks with **external audio features** using:
  - MusicBrainz recording search
  - AcousticBrainz high-level descriptors
- Classify tracks into **moods** using a simple rule-based model:
  - `workout`, `party`, `cleaning`, `focus`, `chill`, `sleep`, `unclassified`
- Build **target playlists**:
  - `Auto – All` (all liked tracks)
  - `Auto – Mood – Workout`, `Auto – Mood – Chill`, etc.
- Compute **incremental diffs** against existing playlists:
  - Detect duplicates inside playlists
  - Determine which new tracks should be added
  - Write human-readable `.diff` files to `app/cache/diffs/`
- Apply **incremental updates** to Spotify playlists (optional):
  - Remove duplicates
  - Add only new tracks
- Persist data and avoid re-fetching:
  - Track cache
  - External feature cache
  - Classification cache
  - Spotify token cache
- Structured, readable logging using Python’s `logging` module via a central `spotify_auto_playlists` logger.

---

## High-Level Architecture

### Packages

- `app/config.py`  
  Central configuration and constants (paths, Spotify credentials, scopes, playlist name prefixes, etc.).

- `app/core/`  
  Cross-cutting utilities and core domain types:
  - `logging_config.py` → `configure_logging()`
  - `logging_utils.py` → `log_info`, `log_step`, `log_section`, etc.
  - `fs_utils.py` → JSON and filesystem helpers
  - `models.py` → `Track`, `Classification`

  All public utilities are re-exported via the `app.core` facade.

- `app/spotify/`  
  Spotify API integration:
  - `auth.py` → Authorization Code flow using a local HTTP server + browser (`load_spotify_token`, `get_current_user_id`, `spotify_headers`, etc.)
  - `tracks.py` → Fetch all liked tracks (`get_all_liked_tracks`)
  - `playlists.py` → List playlists, create playlists, set or incrementally update playlist tracks

  Public functions are re-exported via the `app.spotify` facade.

- `app/pipeline/`  
  Orchestration and domain logic:
  - `orchestration.py` → `PipelineOptions`, `run_pipeline()`, `run_pipeline_entrypoint()`
  - `cache_manager.py` → load/save track cache
  - `external_features.py` → MusicBrainz + AcousticBrainz integration, external features cache
  - `classifier.py` → rule-based mood classification using external features
  - `playlist_manager.py` → build target playlists, compute diffs, sync to Spotify, write `.diff` files
  - `reporting.py` → write markdown reports for unmatched tracks

  All public functions are re-exported via the `app.pipeline` facade.

- `app/api/`  
  FastAPI application:
  - `fastapi_app.py` → defines the FastAPI `app` instance and REST endpoints
  - `__init__.py` → re-exports `app`

- `api_main.py`  
  Uvicorn entrypoint that:
  - Configures logging
  - Exposes the FastAPI `app`

---

## Data & Cache Locations

By default, everything is stored relative to the `app` package directory:

- Cache directory:  
  `app/cache/`

- Files:
  - `tracks.json` → cached liked tracks
  - `external_features.json` → external mood/genre features
  - `track_classification_cache.json` → cached mood classifications
  - `spotify_token.json` → Spotify OAuth token (access + refresh)

- Diffs directory:  
  `app/cache/diffs/`  
  Contains `.diff` files describing per-playlist changes before applying updates.

- Reports directory:  
  `app/reports/`  
  Can be used for markdown reports (e.g. unmatched tracks in `reporting.py`).

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/your-user/spotify-auto-playlists.git
cd spotify-auto-playlists
```

### 2. Create and activate a virtual environment (recommended)

```bash
python -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate
```

### 3. Install dependencies

Create a `requirements.txt` (or use the one provided in the repo) with at least:

```text
fastapi
uvicorn
python-dotenv
requests
```

Then install:

```bash
pip install -r requirements.txt
```

---

## Configuration

The application reads configuration from environment variables, typically via a `.env` file at the project root.

Example `.env`:

```env
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback

# Optional: User agent for MusicBrainz / AcousticBrainz
MUSICBRAINZ_USER_AGENT=spotify-auto-playlists/0.1 (your-email@example.com)
```

### Spotify application setup

1. Go to the Spotify Developer Dashboard.
2. Create an app (or reuse an existing one).
3. Add `http://127.0.0.1:8888/callback` as a **Redirect URI** in the app settings.
4. Copy:
   - Client ID → `SPOTIFY_CLIENT_ID`
   - Client Secret → `SPOTIFY_CLIENT_SECRET`

---

## Authentication Flow

The first time you trigger the pipeline (either from the API or from a custom script):

1. The backend opens your browser to Spotify’s authorization URL (or logs the URL if the browser cannot be opened automatically).
2. You log in to Spotify (if needed) and authorize the app.
3. Spotify redirects to `http://127.0.0.1:8888/callback`.
4. The local HTTP server running inside the backend captures the `code` parameter and exchanges it for an access/refresh token.
5. Tokens are cached in `spotify_token.json`.
6. On subsequent runs:
   - The cached token is reused.
   - If the access token is expired, it is automatically refreshed using the refresh token.

All the related logic lives in `app/spotify/auth.py`.

---

## Running the FastAPI Server

The FastAPI application is defined in `app/api/fastapi_app.py` and exposed in `api_main.py`.

### Start the server (development)

```bash
uvicorn api_main:app --reload
```

By default, this starts on `http://127.0.0.1:8000`.

### Interactive docs (Swagger / OpenAPI)

FastAPI provides automatic interactive API docs:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

You can use these to manually trigger the pipeline while you are building a frontend.

---

## API Reference

### `GET /health`

Simple health check endpoint.

**Response:**

```json
{
  "status": "ok"
}
```

---

### `POST /run`

Trigger the full pipeline in **non-interactive** mode.

**Request body:**

```json
{
  "refresh_tracks": false,
  "force_external_refresh": false,
  "refresh_classification": false,
  "apply_changes": false
}
```

- `refresh_tracks`  
  - `true`: always refresh liked tracks from Spotify  
  - `false`: reuse cached tracks if available

- `force_external_refresh`  
  - `true`: ignore external features cache and refetch from MusicBrainz/AcousticBrainz  
  - `false`: reuse cached external features when possible

- `refresh_classification`  
  - `true`: recompute mood classification for all tracks  
  - `false`: reuse cached classifications when available

- `apply_changes`  
  - `true`: apply incremental changes to Spotify playlists  
  - `false`: preview-only (generate diffs, log, but do not write to Spotify)

**Example response (simplified):**

```json
{
  "user_id": "spotify_user_id",
  "total_tracks": 1234,
  "tracks_refreshed": true,
  "external_features_count": 987,
  "unmatched_count": 247,
  "moods": {
    "chill": 300,
    "workout": 150,
    "party": 120,
    "sleep": 80,
    "focus": 90,
    "cleaning": 60,
    "unclassified": 434
  },
  "playlists_with_changes": 4,
  "playlists_created": 2,
  "diffs": [
    {
      "name": "Auto – Mood – Chill",
      "playlist_id": "spotify_playlist_id_or_null",
      "existing_ids": ["track_id_1", "track_id_2", "..."],
      "target_ids": ["track_id_1", "track_id_3", "..."],
      "duplicates": ["track_id_2"],
      "new_to_add": ["track_id_3"]
    }
  ]
}
```

The `diffs` array mirrors the `.diff` files written to `app/cache/diffs/`.

---

## Using the Pipeline as a Library (Optional)

You can also call the pipeline directly from your own Python code, for example in tests or scripts:

```python
from app.core import configure_logging
from app.pipeline import PipelineOptions, run_pipeline

if __name__ == "__main__":
    configure_logging()

    opts = PipelineOptions(
        refresh_tracks=True,
        force_external_refresh=False,
        refresh_classification=False,
        apply_changes=False,  # keep False for preview-only
    )

    result = run_pipeline(opts)
    print(result)
```

This does **not** provide any interactive CLI flow; it is just a thin wrapper around the same backend pipeline used by the API.

---

## Logging

Logging is configured via:

- `app/core/logging_config.py` → `configure_logging()`
- `app/core/logging_utils.py` → helper functions used across the codebase

Typical log messages include:

- High-level sections: `=== Spotify auto-playlists (pipeline) ===`
- Steps: `→ Fetching liked tracks from Spotify...`
- Info: counts, cache reuse, etc.
- Warnings: external API issues, corrupted cache files
- Progress: e.g. `Fetching pages 3/25 (12.0%)`

The same logging configuration is used for both the FastAPI/uvicorn server and any custom Python scripts.

---

## Development Notes

- Public APIs are exposed via **facades**:
  - `app.core` (logging, filesystem, models)
  - `app.spotify` (Spotify integration)
  - `app.pipeline` (orchestration and domain logic)
  - `app.api` (FastAPI app)
- Internal modules (`logging_utils`, `fs_utils`, etc.) can still be imported directly, but the preferred pattern is to go through the package-level facades.
- The rule-based mood model is intentionally simple and transparent. You can swap it for a more advanced ML-based classifier later.

---

## Next Steps / Ideas

- Build a **frontend** (web UI) to:
  - Visualize the pipeline (tracks, moods, diff previews)
  - Let users choose which playlists to sync
  - Edit playlist contents before applying changes
- Integrate a **remote AI classifier** to refine mood classification.
- Add more playlist strategies:
  - Genre-based
  - Year-based
  - Hybrid rules (time of day, BPM ranges, etc.)
- Improve error handling / retries for external APIs.

---

## License

MIT (or any other license you choose).
