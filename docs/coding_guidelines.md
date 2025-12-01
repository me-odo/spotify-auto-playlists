# Purpose
This document defines the coding, architecture, and import guidelines for the **spotify-auto-playlists** project.

# Architecture Overview
The project is organised into a small set of focused packages:

- `app.core`: cross-cutting infrastructure such as filesystem helpers, logging utilities, and base models.
- `app.data`: local persistence and caches for tracks, external features, classifications, and jobs.
- `app.spotify`: integration with the Spotify Web API, including authentication, tracks, and playlists.
- `app.pipeline`: pipeline business logic, including enrichment, classification, playlist building, reporting, and the jobs runner.
- `app.api`: FastAPI application and routers exposing HTTP endpoints under `/auth`, `/pipeline`, and `/data`.

These responsibilities must stay aligned with the existing codebase; changes to responsibilities should be done in explicit, well-scoped refactors.

# Import Policy
Imports must follow these rules to keep the architecture clear and stable:

- Inside a package, use relative imports:

  ```python
  from .module import some_function
  from .submodule import SomeClass
  ```

- For cross-package imports, always use the public façade of the target package instead of deep internal paths. For example:

  ```python
  from app.core import log_info, write_json, Track
  from app.data import load_tracks_cache, save_tracks_cache
  from app.pipeline import run_step_for_job, build_target_playlists
  from app.spotify import get_all_liked_tracks
  ```

- Never import from deep internal modules of another package when a façade exists (for example, avoid `from app.core.fs_utils import write_json` or `from app.spotify.tracks import get_all_liked_tracks` in favour of the façade imports above).

- When adding new cross-package functionality, first expose the public symbol via the appropriate façade, then update calling code to import from that façade.

# Public Facades
The following modules act as public façades and are the only supported entry points for their packages:

- `app.core`
- `app.data`
- `app.pipeline`
- `app.spotify`

Code outside these packages must only depend on them through these façades. Internal module layouts are implementation details and may change as long as the façade contract stays stable.

Whenever a new public function, class, or constant is introduced inside one of these packages and is meant to be used from other packages, the corresponding façade must be updated to re-export it. Call sites must then import the symbol from the façade, not from the internal module.

# Module Responsibilities
Each module (file) should have a clear and focused responsibility. Examples:

- Request/response schemas live in schema modules.
- Route handlers live in router modules.
- Low-level utilities (filesystem, logging, base models) live under `app.core`.
- Persistence and cache logic lives under `app.data`.
- Spotify Web API integration lives under `app.spotify`.
- Pipeline orchestration and business rules live under `app.pipeline`.

Avoid "god modules" that mix unrelated concerns (for example, combining API routes, persistence details, and long-running jobs in the same file). When a module grows too large or mixes responsibilities, plan a dedicated, well-scoped refactor to move or split code, and keep the public behaviour stable.

# Comments, Docstrings and Tests
All comments and docstrings in this project must be written in English.

`scripts/smoke_test.py` is the main functional non-regression test for the system. Whenever public behaviour changes (for example, new required fields in responses, new pipeline steps, or changed side effects), the smoke test must be reviewed and updated accordingly to reflect the new expected behaviour.

New functionality should include appropriate tests (unit, integration, or functional) to guard against regressions and to document expected behaviour.