import json
import os
import time
import webbrowser
from typing import Dict, List
from collections import Counter

import requests

from config import (
    SPOTIFY_CLIENT_ID,
    SPOTIFY_CLIENT_SECRET,
    SPOTIFY_REDIRECT_URI,
    SPOTIFY_AUTH_URL,
    SPOTIFY_TOKEN_URL,
    SPOTIFY_API_BASE,
    SCOPES,
)
from models import Track
from cli_utils import print_progress_bar


def get_spotify_token() -> Dict:
    """
    Simplified auth code flow:
    - open browser with auth URL
    - user pastes the "code" parameter from redirect URL
    """
    from urllib.parse import urlencode

    auth_query_parameters = {
        "response_type": "code",
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "scope": " ".join(SCOPES),
        "client_id": SPOTIFY_CLIENT_ID,
    }
    url_args = urlencode(auth_query_parameters)
    auth_url = f"{SPOTIFY_AUTH_URL}/?{url_args}"
    print("Open the following URL in a browser and authorize the application:")
    print(auth_url)
    try:
        webbrowser.open(auth_url)
    except Exception:
        pass

    auth_code = input("Paste the 'code' parameter from the redirect URL here: ").strip()

    token_data = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "client_id": SPOTIFY_CLIENT_ID,
        "client_secret": SPOTIFY_CLIENT_SECRET,
    }

    r = requests.post(SPOTIFY_TOKEN_URL, data=token_data)
    r.raise_for_status()
    token_info = r.json()
    token_info["timestamp"] = int(time.time())
    with open("spotify_token.json", "w", encoding="utf-8") as f:
        json.dump(token_info, f, ensure_ascii=False, indent=2)
    return token_info


def refresh_spotify_token(refresh_token: str) -> Dict:
    token_data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": SPOTIFY_CLIENT_ID,
        "client_secret": SPOTIFY_CLIENT_SECRET,
    }
    r = requests.post(SPOTIFY_TOKEN_URL, data=token_data)
    r.raise_for_status()
    token_info = r.json()
    token_info["refresh_token"] = refresh_token
    token_info["timestamp"] = int(time.time())
    with open("spotify_token.json", "w", encoding="utf-8") as f:
        json.dump(token_info, f, ensure_ascii=False, indent=2)
    return token_info


def load_spotify_token() -> Dict:
    if os.path.exists("spotify_token.json"):
        with open("spotify_token.json", "r", encoding="utf-8") as f:
            token_info = json.load(f)
    else:
        token_info = get_spotify_token()

    now = int(time.time())
    expires_in = token_info.get("expires_in", 3600)
    if now - token_info.get("timestamp", 0) > expires_in - 60:
        token_info = refresh_spotify_token(token_info["refresh_token"])
    return token_info


def spotify_headers(token_info: Dict) -> Dict:
    return {"Authorization": f"Bearer {token_info['access_token']}"}


def get_current_user_id(token_info: Dict) -> str:
    r = requests.get(f"{SPOTIFY_API_BASE}/me", headers=spotify_headers(token_info))
    r.raise_for_status()
    return r.json()["id"]


def get_all_liked_tracks(token_info: Dict) -> List[Track]:
    print("Fetching liked tracks from Spotify...")

    headers = spotify_headers(token_info)
    limit = 50
    url = f"{SPOTIFY_API_BASE}/me/tracks"
    params = {"limit": limit}

    tracks: List[Track] = []

    # --- First request: to get TOTAL count ---
    r = requests.get(url, headers=headers, params=params)
    r.raise_for_status()
    data = r.json()

    total = data.get("total", 0)
    if total == 0:
        print("→ No liked tracks found.")
        return []

    total_pages = (total + limit - 1) // limit  # ceil(total / limit)

    # Process first page immediately
    items = data.get("items", [])
    for item in items:
        t = item["track"]
        tracks.append(
            Track(
                id=t["id"],
                name=t["name"],
                artist=", ".join(a["name"] for a in t["artists"]),
                album=t["album"]["name"],
                release_date=t["album"].get("release_date"),
                added_at=item.get("added_at"),
                features={},
            )
        )

    print_progress_bar(1, total_pages, prefix="  Fetching pages")
    next_url = data.get("next")

    # --- Loop on remaining pages ---
    current_page = 1
    while next_url:
        current_page += 1
        r = requests.get(next_url, headers=headers)
        r.raise_for_status()
        data = r.json()

        items = data.get("items", [])
        for item in items:
            t = item["track"]
            tracks.append(
                Track(
                    id=t["id"],
                    name=t["name"],
                    artist=", ".join(a["name"] for a in t["artists"]),
                    album=t["album"]["name"],
                    release_date=t["album"].get("release_date"),
                    added_at=item.get("added_at"),
                    features={},
                )
            )

        print_progress_bar(current_page, total_pages, prefix="  Fetching pages")
        next_url = data.get("next")

    print(f"\n→ {len(tracks)} liked tracks fetched.")
    return tracks


def get_audio_features(token_info: Dict, track_ids: List[str]) -> Dict[str, Dict]:
    """
    Fetch /audio-features in batches of 100 IDs.
    If Spotify returns an error (403, etc.), we log and continue without features.
    """
    print("Fetching audio features from Spotify...")
    headers = spotify_headers(token_info)
    features_by_id: Dict[str, Dict] = {}

    if not track_ids:
        print("No track IDs provided for audio features.")
        return features_by_id

    total_batches = (len(track_ids) + 99) // 100

    for batch_index in range(total_batches):
        start = batch_index * 100
        end = start + 100
        batch = track_ids[start:end]
        ids_param = ",".join(batch)
        url = f"{SPOTIFY_API_BASE}/audio-features"
        r = requests.get(url, headers=headers, params={"ids": ids_param})

        if r.status_code == 403:
            print("⚠ Spotify returned 403 Forbidden on /audio-features.")
            try:
                print("Spotify response:", r.text)
            except Exception:
                pass
            print(
                "Continuing without audio features. Classification will use only title/artist/album."
            )
            return {}

        if not r.ok:
            print(
                f"⚠ Error calling /audio-features (status {r.status_code}). Batch ignored."
            )
            try:
                print("Spotify response:", r.text)
            except Exception:
                pass
            continue

        data = r.json()
        for f in data.get("audio_features", []):
            if f and f.get("id"):
                features_by_id[f["id"]] = f

        print_progress_bar(
            batch_index + 1, total_batches, prefix="  Audio features batches"
        )

    print(f"\n→ Audio features fetched for {len(features_by_id)} tracks.")
    return features_by_id


def get_user_playlists(token_info: Dict) -> List[Dict]:
    print("Fetching existing playlists from Spotify...")
    playlists = []
    url = f"{SPOTIFY_API_BASE}/me/playlists"
    headers = spotify_headers(token_info)
    params = {"limit": 50}

    while url:
        r = requests.get(url, headers=headers, params=params)
        r.raise_for_status()
        data = r.json()
        playlists.extend(data["items"])
        url = data["next"]
        params = None  # next URL already includes params

    print(f"→ {len(playlists)} playlists found.")
    return playlists


def find_or_create_playlist(
    token_info: Dict,
    user_id: str,
    name: str,
    existing_playlists: List[Dict],
) -> str:
    headers = spotify_headers(token_info)

    # Search existing playlists
    for p in existing_playlists:
        if p["name"] == name:
            return p["id"]

    # Create playlist
    url = f"{SPOTIFY_API_BASE}/users/{user_id}/playlists"
    payload = {
        "name": name,
        "public": False,
        "description": "Playlist automatically generated by script (mood/genre/year).",
    }
    r = requests.post(url, headers=headers, json=payload)
    r.raise_for_status()
    playlist = r.json()
    existing_playlists.append(playlist)
    print(f"Playlist created: {name}")
    return playlist["id"]


def set_playlist_tracks(
    token_info: Dict, playlist_id: str, track_ids: List[str]
) -> None:
    """
    Replace playlist contents with a given set of tracks.
    - Remove all existing tracks in batches of 100.
    - Add new tracks (deduplicated) in batches of 100.
    """
    headers = spotify_headers(token_info)

    # 1) Fetch all current items
    url_items = f"{SPOTIFY_API_BASE}/playlists/{playlist_id}/tracks"
    params = {"fields": "items(track(uri)),next"}
    uris_to_remove: List[str] = []

    while url_items:
        r = requests.get(url_items, headers=headers, params=params)
        r.raise_for_status()
        data = r.json()
        for item in data.get("items", []):
            track = item.get("track")
            if track and track.get("uri"):
                uris_to_remove.append(track["uri"])
        url_items = data.get("next")
        params = None  # next URL already includes params

    # 2) Remove all existing tracks in batches of 100
    url_remove = f"{SPOTIFY_API_BASE}/playlists/{playlist_id}/tracks"
    while uris_to_remove:
        batch = uris_to_remove[:100]
        uris_to_remove = uris_to_remove[100:]
        body = {"tracks": [{"uri": u} for u in batch]}
        r = requests.delete(url_remove, headers=headers, json=body)
        r.raise_for_status()

    # 3) Deduplicate track_ids while preserving order
    seen = set()
    unique_ids: List[str] = []
    for tid in track_ids:
        if tid and tid not in seen:
            seen.add(tid)
            unique_ids.append(tid)

    if not unique_ids:
        return

    # 4) Add new tracks in batches of 100
    uris = [f"spotify:track:{tid}" for tid in unique_ids]
    url_add = f"{SPOTIFY_API_BASE}/playlists/{playlist_id}/tracks"
    for i in range(0, len(uris), 100):
        batch = uris[i : i + 100]
        r = requests.post(url_add, headers=headers, json={"uris": batch})
        r.raise_for_status()


def get_playlist_tracks(token_info: Dict, playlist_id: str) -> List[str]:
    """
    Return the list of track IDs for a given playlist.
    """
    headers = spotify_headers(token_info)
    url = f"{SPOTIFY_API_BASE}/playlists/{playlist_id}/tracks"
    params = {"fields": "items(track(id)),next"}
    track_ids: List[str] = []

    while url:
        r = requests.get(url, headers=headers, params=params)
        r.raise_for_status()
        data = r.json()
        for item in data.get("items", []):
            track = item.get("track")
            if track and track.get("id"):
                track_ids.append(track["id"])
        url = data.get("next")
        params = None  # next URL already includes params

    return track_ids


def incremental_update_playlist(
    token_info: Dict, playlist_id: str, target_ids: List[str]
) -> None:
    """
    Incrementally update a playlist:
      - remove existing duplicates
      - add only tracks that are not already present

    ⚠ Does NOT remove tracks that are present but not in target_ids.
    """
    headers = spotify_headers(token_info)

    # 1) Fetch current playlist state
    existing_ids = get_playlist_tracks(token_info, playlist_id)
    counts = Counter(existing_ids)

    # 2) Detect duplicates (tracks with count > 1)
    duplicates = [tid for tid, c in counts.items() if c > 1]

    # 3) Remove duplicated tracks entirely
    if duplicates:
        url_remove = f"{SPOTIFY_API_BASE}/playlists/{playlist_id}/tracks"
        tracks_to_remove = [{"uri": f"spotify:track:{tid}"} for tid in duplicates]
        # Remove in batches of 100
        while tracks_to_remove:
            batch = tracks_to_remove[:100]
            tracks_to_remove = tracks_to_remove[100:]
            r = requests.delete(url_remove, headers=headers, json={"tracks": batch})
            r.raise_for_status()

    # 4) Recompute conceptual state after duplicate removal
    existing_set = set(existing_ids) - set(duplicates)
    target_set = set(target_ids)

    # 5) Tracks to add = those in target but not already present
    to_add = list(target_set - existing_set)

    if not to_add:
        print(
            "  Nothing to add (playlist already up to date, ignoring removed duplicates)."
        )
        return

    # 6) Add new tracks
    uris = [f"spotify:track:{tid}" for tid in to_add]
    url_add = f"{SPOTIFY_API_BASE}/playlists/{playlist_id}/tracks"
    for i in range(0, len(uris), 100):
        batch = uris[i : i + 100]
        r = requests.post(url_add, headers=headers, json={"uris": batch})
        r.raise_for_status()
