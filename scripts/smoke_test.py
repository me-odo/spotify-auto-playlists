#!/usr/bin/env python3
"""
Smoke test for the spotify-auto-playlists backend.

It runs through:
- auth
- synchronous pipeline steps
- /data API (tracks, features, classifications, patch)
- async pipeline jobs API (/pipeline/{step}/run-async, /pipeline/jobs, /pipeline/jobs/{id})

Run with:
    make smoke
"""

import json
import sys
import time
from typing import Any, Dict, Optional

import requests

BASE_URL = "http://localhost:8888"

# Keep these ids in sync with the backend defaults
DEFAULT_CLASSIFIER_ID = "mood_v1"
DEFAULT_FEATURE_PROVIDER_ID = "acousticbrainz"

JOB_POLL_TIMEOUT_SECONDS = 60
JOB_POLL_INTERVAL_SECONDS = 2.0


def call(method: str, path: str, **kwargs) -> Dict[str, Any]:
    """Helper to call the API and print concise output."""
    url = f"{BASE_URL}{path}"
    print(f"\n=== {method.upper()} {path} ===")
    try:
        resp = requests.request(method, url, timeout=30, **kwargs)
    except Exception as e:  # noqa: BLE001
        print(f"❌ Request failed: {e}")
        sys.exit(1)

    print(f"Status: {resp.status_code}")

    if resp.status_code >= 400:
        print("❌ Error response:")
        print(resp.text)
        sys.exit(1)

    try:
        data = resp.json()
    except Exception:  # noqa: BLE001
        print("❌ Non-JSON response:")
        print(resp.text)
        sys.exit(1)

    # Print compact JSON preview
    snippet = json.dumps(data, indent=2)[:500]
    print(snippet)
    if len(snippet) == 500:
        print("…(truncated)…")

    return data


def poll_job(
    job_id: str, timeout_seconds: int = JOB_POLL_TIMEOUT_SECONDS
) -> Dict[str, Any]:
    """Poll a job until it reaches a terminal state or timeout."""
    deadline = time.time() + timeout_seconds
    last_status: Optional[str] = None

    while time.time() < deadline:
        job = call("get", f"/pipeline/jobs/{job_id}")
        status = job.get("status")
        last_status = status
        print(f"Job {job_id} status: {status}")

        if status in {"done", "error"}:
            return job

        time.sleep(JOB_POLL_INTERVAL_SECONDS)

    print(
        f"❌ Job {job_id} did not reach a terminal state in time "
        f"(last status={last_status})."
    )
    sys.exit(1)


def test_multi_source_tracks_fetch() -> None:
    """End-to-end test for multi-source track fetching and aggregation."""
    print("\n=== POST /pipeline/tracks/fetch-sources (liked source) ===")

    body = {
        "sources": [
            {
                "source_type": "liked",
                "source_id": None,
                "label": "Liked tracks (smoke_test)",
            }
        ]
    }
    response = call("post", "/pipeline/tracks/fetch-sources", json=body)

    jobs = response.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        print(
            "❌ /pipeline/tracks/fetch-sources did not return a non-empty 'jobs' list."
        )
        sys.exit(1)

    job = jobs[0]
    job_id = job.get("id")
    if not isinstance(job_id, str) or not job_id:
        print("❌ Job from /pipeline/tracks/fetch-sources is missing a valid 'id'.")
        sys.exit(1)

    metadata = job.get("metadata") or {}
    source_type = metadata.get("source_type")
    if source_type != "liked":
        print("❌ Expected job metadata.source_type='liked', " f"got {source_type!r}.")
        sys.exit(1)

    finished = poll_job(job_id)
    payload = finished.get("payload") or {}

    source = payload.get("source") or {}
    tracks = payload.get("tracks") or []

    if source.get("source_type") != "liked":
        print(
            "❌ Job payload.source.source_type is not 'liked'. "
            f"(got={source.get('source_type')!r})"
        )
        sys.exit(1)

    if not isinstance(tracks, list):
        print("❌ Job payload.tracks is not a list.")
        sys.exit(1)

    print("ℹ️ fetch_tracks job returned " f"{len(tracks)} tracks for liked source.")

    print("\n=== GET /pipeline/tracks/aggregate ===")
    aggregate = call("get", "/pipeline/tracks/aggregate")
    agg_tracks = aggregate.get("tracks")
    agg_sources = aggregate.get("sources")

    if not isinstance(agg_tracks, list):
        print("❌ /pipeline/tracks/aggregate returned a non-list 'tracks' field.")
        sys.exit(1)

    if not isinstance(agg_sources, list) or not agg_sources:
        print(
            "❌ /pipeline/tracks/aggregate returned an invalid or empty 'sources' list."
        )
        sys.exit(1)

    print(
        "ℹ️ aggregate endpoint returned "
        f"{len(agg_tracks)} tracks and {len(agg_sources)} sources."
    )


def test_enrichments_endpoint() -> None:
    """Basic non-regression test for the unified enrichments API."""
    print("\n=== GET /data/enrichments ===")

    enrichments = call("get", "/data/enrichments")

    # The endpoint must return a JSON object (mapping track_id -> list of enrichments).
    if not isinstance(enrichments, dict):
        print("❌ /data/enrichments did not return a JSON object (dict).")
        sys.exit(1)

    # If there is at least one entry, validate that the value is a list.
    items = list(enrichments.items())
    if items:
        sample_track_id, sample_entries = items[0]
        if not isinstance(sample_entries, list):
            print(
                "❌ /data/enrichments value for track "
                f"{sample_track_id!r} is not a list."
            )
            sys.exit(1)

    print(
        "ℹ️ /data/enrichments returned "
        f"{len(enrichments)} tracks with enrichment entries."
    )


def test_rules_endpoint() -> None:
    """Basic non-regression test for playlist rules API."""
    print("\n=== GET /data/rules ===")

    rules = call("get", "/data/rules")

    # The endpoint must return a JSON array (list of rule definitions).
    if not isinstance(rules, list):
        print("❌ /data/rules did not return a JSON list.")
        sys.exit(1)

    if rules:
        sample = rules[0]
        if not isinstance(sample, dict):
            print("❌ /data/rules first item is not a JSON object (dict).")
            sys.exit(1)

        missing = [key for key in ("id", "name") if key not in sample]
        if missing:
            print(
                "❌ /data/rules items are missing required keys: "
                f"{', '.join(sorted(missing))}."
            )
            sys.exit(1)

    print(f"ℹ️ /data/rules returned {len(rules)} rule definition(s).")


def test_rules_write_and_read() -> None:
    """Functional test for creating and reading playlist rules."""
    print("\n=== POST /data/rules (create smoke_test rule) ===")

    rule_id = "smoke_test_rule"
    body = {
        "id": rule_id,
        "name": "Smoke Test Rule",
        "description": "Rule created by scripts/smoke_test.py",
        "enabled": True,
        "target_playlist_id": None,
        "rules": {
            "operator": "and",
            "conditions": [
                {
                    "field": "mood",
                    "operator": "eq",
                    "value": "smoke_test_mood",
                }
            ],
        },
    }

    created = call("post", "/data/rules", json=body)

    # The POST must return a JSON object with at least id and name.
    if not isinstance(created, dict):
        print("❌ POST /data/rules did not return a JSON object.")
        sys.exit(1)

    for key in ("id", "name"):
        if key not in created:
            print(f"❌ POST /data/rules response is missing key: {key!r}.")
            sys.exit(1)

    if created["id"] != rule_id:
        print(
            "❌ POST /data/rules returned a rule with unexpected id "
            f"(expected={rule_id!r}, got={created['id']!r})."
        )
        sys.exit(1)

    print("\n=== GET /data/rules (verify persistence) ===")
    rules = call("get", "/data/rules")

    if not isinstance(rules, list):
        print("❌ /data/rules did not return a JSON list.")
        sys.exit(1)

    matching = [r for r in rules if isinstance(r, dict) and r.get("id") == rule_id]

    if not matching:
        print(
            "❌ /data/rules does not contain the rule created by "
            "POST /data/rules (id='smoke_test_rule')."
        )
        sys.exit(1)

    print(f"ℹ️ /data/rules contains {len(matching)} rule(s) with id={rule_id!r}.")


def main() -> None:
    print("📀 Smoke Test: spotify-auto-playlists backend\n")

    # --- AUTH ---
    call("get", "/auth/status")

    # --- PIPELINE STEPS (synchronous) ---
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
            "No tracks available from /data/tracks; PATCH classification test "
            "will be skipped."
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

        # Behavioural assertions for TDD-style safety
        required_keys = {"classifier_id", "track_id", "labels"}
        missing_keys = [key for key in required_keys if key not in patched]
        if missing_keys:
            print(
                "❌ PATCH classification response is missing required keys: "
                f"{', '.join(sorted(missing_keys))}."
            )
            sys.exit(1)

        labels = patched.get("labels") or {}
        mood = labels.get("mood")
        if mood != "smoke_test":
            print(
                "❌ PATCH classification did not persist the expected mood "
                f"(got={mood!r})."
            )
            sys.exit(1)
    else:
        print("\n⏭  Skipping PATCH classification test (no track id available).")

    # --- DATA API: ENRICHMENTS ---
    test_enrichments_endpoint()

    # --- DATA API: PLAYLIST RULES ---
    test_rules_endpoint()

    # --- DATA API: PLAYLIST RULES (write & read) ---
    test_rules_write_and_read()

    # --- ASYNC PIPELINE JOBS (legacy step=tracks) ---
    print("\n🚀 Testing legacy async job: step=tracks")

    step = "tracks"
    job_start_response = call("post", f"/pipeline/{step}/run-async")
    job_id = job_start_response.get("id")
    job_step = job_start_response.get("step")

    if not job_id:
        print("❌ /pipeline/{step}/run-async did not return a job id.")
        sys.exit(1)

    print(f"Started legacy async job: id={job_id}, step={job_step}")

    final_job = poll_job(job_id)
    final_status = final_job.get("status")
    print(f"\nℹ️  Legacy job final status: {final_status}")

    if final_status != "done":
        print(f"❌ Legacy async job {job_id} failed with status={final_status}")
        sys.exit(1)

    # Ensure legacy job appears in job list
    jobs_list = call("get", "/pipeline/jobs")
    jobs = jobs_list.get("jobs", []) or []
    job_ids = {job.get("id") for job in jobs}
    print(f"\nℹ️  /pipeline/jobs returned {len(jobs)} jobs (including legacy).")

    if job_id not in job_ids:
        print(f"❌ Legacy job {job_id} not present in /pipeline/jobs.")
        sys.exit(1)

    print("✅ Legacy async job pipeline verified.\n")

    # -------------------------------------------------------------------------
    # --- MULTI-SOURCE FETCH: async track retrieval + aggregation  ---
    # -------------------------------------------------------------------------

    print("\n🚀 Testing multi-source async track fetch (new pipeline)…")

    # 1) Define sources (only liked tracks for now)
    sources_payload = {
        "sources": [
            {"source_type": "liked", "source_id": None, "label": "Liked tracks"}
        ]
    }

    # 2) Launch fetch jobs
    fetch_response = call(
        "post", "/pipeline/tracks/fetch-sources", json=sources_payload
    )
    fetch_jobs = fetch_response.get("jobs", [])

    if not fetch_jobs:
        print("❌ /pipeline/tracks/fetch-sources returned no jobs.")
        sys.exit(1)

    print(f"Started {len(fetch_jobs)} fetch jobs.")

    # 3) Poll each fetch job
    completed_jobs = []
    for job in fetch_jobs:
        j_id = job.get("id")
        j_step = job.get("step")
        j_meta = job.get("metadata", {})

        if not j_id:
            print("❌ A fetch job is missing its job id.")
            sys.exit(1)

        print(f"\nPolling fetch job: id={j_id}, step={j_step}, meta={j_meta}")

        final = poll_job(j_id)
        status = final.get("status")
        payload = final.get("payload") or {}

        if status != "done":
            print(f"❌ Fetch job {j_id} failed (status={status}).")
            sys.exit(1)

        # Validate payload structure
        if "tracks" not in payload:
            print(f"❌ Fetch job {j_id} payload missing 'tracks'.")
            sys.exit(1)

        if "source" not in payload:
            print(f"❌ Fetch job {j_id} payload missing 'source'.")
            sys.exit(1)

        completed_jobs.append(final)

    print("\nℹ️ All fetch jobs completed successfully.")

    # 4) Test final aggregation endpoint
    agg = call("get", "/pipeline/tracks/aggregate")

    if "tracks" not in agg:
        print("❌ /pipeline/tracks/aggregate response missing 'tracks'.")
        sys.exit(1)

    if "sources" not in agg:
        print("❌ /pipeline/tracks/aggregate response missing 'sources'.")
        sys.exit(1)

    print(
        f"\nℹ️ Aggregation OK: {len(agg['tracks'])} tracks, {len(agg['sources'])} sources."
    )
    print("✅ Multi-source async fetch pipeline verified.\n")

    print("\n🎉 Smoke test completed successfully.\n")


if __name__ == "__main__":
    main()
