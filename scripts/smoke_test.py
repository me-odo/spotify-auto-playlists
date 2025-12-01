#!/usr/bin/env python3
"""
Simple smoke test for the spotify-auto-playlists backend.

It runs through the main pipeline steps and the /data API to ensure
that the backend still behaves correctly between sprints.

Run with:
    make smoke
"""

import json
import sys
from typing import Any, Dict

import requests

BASE_URL = "http://localhost:8888"

# Keep these ids in sync with the backend defaults
DEFAULT_CLASSIFIER_ID = "mood_v1"
DEFAULT_FEATURE_PROVIDER_ID = "acousticbrainz"


def call(method: str, path: str, **kwargs) -> Dict[str, Any]:
    """Helper to call the API and print concise output."""
    url = f"{BASE_URL}{path}"
    print(f"\n=== {method.upper()} {path} ===")
    try:
        resp = requests.request(method, url, timeout=30, **kwargs)
    except Exception as e:
        print(f"❌ Request failed: {e}")
        sys.exit(1)

    print(f"Status: {resp.status_code}")

    if resp.status_code >= 400:
        print("❌ Error response:")
        print(resp.text)
        sys.exit(1)

    try:
        data = resp.json()
    except Exception:
        print("❌ Non-JSON response:")
        print(resp.text)
        sys.exit(1)

    # Print compact JSON preview
    snippet = json.dumps(data, indent=2)[:500]
    print(snippet)
    if len(snippet) == 500:
        print("…(truncated)…")

    return data


def main() -> None:
    print("📀 Smoke Test: spotify-auto-playlists backend\n")

    # --- AUTH ---
    call("get", "/auth/status")

    # --- PIPELINE STEPS ---
    call("get", "/pipeline/health")
    call("get", "/pipeline/tracks")
    call("get", "/pipeline/external")
    call("get", "/pipeline/classify")
    call("get", "/pipeline/build")
    call("get", "/pipeline/diff")

    print("\nSkipping /pipeline/apply (destructive) unless explicitly enabled.")
    # Example if you ever want to test apply in a controlled environment:
    # call("post", "/pipeline/apply", json={"playlists": []})

    # --- DATA API: TRACKS ---
    tracks_response = call("get", "/data/tracks")
    tracks = tracks_response.get("tracks", []) or []
    total_tracks = tracks_response.get("total", 0)
    print(f"\nℹ️  /data/tracks returned {len(tracks)} items (total={total_tracks}).")

    # Choose a track_id for classification tests if available
    track_id_for_patch = None
    if tracks:
        track_id_for_patch = tracks[0].get("id")
        print(f"Using track id for classification patch: {track_id_for_patch}")
    else:
        print(
            "No tracks available from /data/tracks; PATCH classification test will be skipped."
        )

    # --- DATA API: FEATURES ---
    features_path = f"/data/features/{DEFAULT_FEATURE_PROVIDER_ID}"
    features_response = call("get", features_path)
    print(
        f"\nℹ️  /data/features/{DEFAULT_FEATURE_PROVIDER_ID} returned "
        f"{len(features_response)} track entries."
    )

    # --- DATA API: CLASSIFICATIONS (GET) ---
    classifications_path = f"/data/classifications/{DEFAULT_CLASSIFIER_ID}"
    classifications_response = call("get", classifications_path)
    print(
        f"\nℹ️  /data/classifications/{DEFAULT_CLASSIFIER_ID} returned "
        f"{len(classifications_response)} track entries."
    )

    # --- DATA API: CLASSIFICATIONS (PATCH) ---
    if track_id_for_patch:
        patch_path = (
            f"/data/classifications/{DEFAULT_CLASSIFIER_ID}/{track_id_for_patch}"
        )
        print(f"\n🔧 Patching classification for track {track_id_for_patch} …")
        patch_body = {
            "labels": {
                # It is safe to override mood/genre/year for smoke testing.
                "mood": "smoke_test",
                "genre": "smoke",
                "year": 2000,
            }
        }
        patched = call("patch", patch_path, json=patch_body)
        print("\nℹ️  PATCH result:")
        print(json.dumps(patched, indent=2)[:500])
    else:
        print("\n⏭  Skipping PATCH classification test (no track id available).")

    print("\n✅ Smoke test completed successfully.\n")


if __name__ == "__main__":
    main()
