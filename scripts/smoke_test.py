#!/usr/bin/env python3
"""
Simple smoke test for the spotify-auto-playlists backend.

It runs through the pipeline steps sequentially to ensure
that the API is responding without crashes between sprints.

Run with:
    make smoke
"""

import json
import sys
from typing import Any, Dict

import requests

BASE_URL = "http://localhost:8888"


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


def main():
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
    # Example if you ever want to test apply:
    # call("post", "/pipeline/apply", json={"playlists": []})

    print("\n✅ Smoke test completed successfully.\n")


if __name__ == "__main__":
    main()
