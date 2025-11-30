from collections import Counter
from http.server import BaseHTTPRequestHandler, HTTPServer
import platform
import requests
import subprocess
import time
import threading
from typing import Dict, List
from urllib.parse import urlencode, urlparse, parse_qs


from cli_utils import (
    print_step,
    print_info,
    print_progress_bar,
    print_warning,
)
from config import (
    SPOTIFY_CLIENT_ID,
    SPOTIFY_CLIENT_SECRET,
    SPOTIFY_REDIRECT_URI,
    SPOTIFY_AUTH_URL,
    SPOTIFY_TOKEN_URL,
    SPOTIFY_API_BASE,
    SCOPES,
    SPOTIFY_TOKEN_FILE,
)
from fs_utils import write_json, read_json
from models import Track


def _try_open_browser(url: str) -> None:
    """
    Try to open a URL in the system browser without printing anything
    to the current terminal (stdout/stderr are suppressed).
    """
    try:
        system = platform.system()
        if system == "Darwin":
            cmd = ["open", url]
        elif system == "Windows":
            cmd = ["cmd", "/c", "start", "", url]
        else:
            # Linux / other Unix – use xdg-open
            cmd = ["xdg-open", url]

        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        # If this fails, the user still has the URL printed in the terminal
        pass


class _SpotifyAuthHandler(BaseHTTPRequestHandler):
    """
    Simple HTTP handler that captures the 'code' query parameter from
    the redirect URI and stores it on the class.
    """

    authorization_code: str | None = None

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        code = qs.get("code", [None])[0]

        # Log what we actually received (for debugging)
        print_info(f"Auth callback received: path={parsed.path}, has_code={bool(code)}")

        if code:
            _SpotifyAuthHandler.authorization_code = code
            message = (
                "<h1>Spotify authorization complete</h1>"
                "<p>You can close this window and return to the application.</p>"
            )
        else:
            message = (
                "<h1>Spotify authorization callback</h1>"
                "<p>No authorization code was found in the URL.</p>"
                "<p>If you opened this URL manually, please close this window and "
                "let the Spotify login page redirect you here automatically.</p>"
            )

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(message.encode("utf-8"))

    def log_message(self, format, *args):
        # Silence default HTTP server logging in the console
        return


def _run_local_http_server_for_auth(timeout: int = 180) -> str:
    """
    Start a local HTTP server on the host/port defined in SPOTIFY_REDIRECT_URI,
    wait for a single request with a 'code' query parameter, then return it.
    Raises TimeoutError if nothing arrives within `timeout` seconds.
    """
    parsed = urlparse(SPOTIFY_REDIRECT_URI)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 8888

    _SpotifyAuthHandler.authorization_code = None
    httpd = HTTPServer((host, port), _SpotifyAuthHandler)

    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    try:
        start = time.time()
        while time.time() - start < timeout:
            if _SpotifyAuthHandler.authorization_code:
                return _SpotifyAuthHandler.authorization_code
            time.sleep(0.2)
    finally:
        httpd.shutdown()
        httpd.server_close()

    raise TimeoutError("Timed out waiting for Spotify authorization.")


def _get_spotify_token_local_server() -> Dict:
    auth_query_parameters = {
        "response_type": "code",
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "scope": " ".join(SCOPES),
        "client_id": SPOTIFY_CLIENT_ID,
    }
    url_args = urlencode(auth_query_parameters)
    auth_url = f"{SPOTIFY_AUTH_URL}/?{url_args}"

    print_step("Opening browser for Spotify authorization...")
    print_info(
        f"If your browser does not open automatically, copy/paste this URL manually:\n{auth_url}"
    )

    _try_open_browser(auth_url)

    code = _run_local_http_server_for_auth(timeout=180)

    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "client_id": SPOTIFY_CLIENT_ID,
        "client_secret": SPOTIFY_CLIENT_SECRET,
    }

    r = requests.post(SPOTIFY_TOKEN_URL, data=token_data)
    r.raise_for_status()
    token_info = r.json()
    token_info["timestamp"] = int(time.time())
    write_json(SPOTIFY_TOKEN_FILE, token_info)
    return token_info


def _get_spotify_token_cli() -> Dict:
    """
    Legacy CLI-based flow:
      - print auth URL
      - user manually copies browser redirect `code` back into the terminal.
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

    print_step("Open the following URL in a browser and authorize the application:")
    print_info(auth_url)
    _try_open_browser(auth_url)

    auth_code = input(
        "→ Paste the 'code' parameter from the redirect URL here: "
    ).strip()

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
    write_json(SPOTIFY_TOKEN_FILE, token_info)
    return token_info


def get_spotify_token(use_cli_auth: bool = False) -> Dict:
    """
    Get a new Spotify access/refresh token via authorization code flow.

    If use_cli_auth is False (default):
      - start a local HTTP server on SPOTIFY_REDIRECT_URI (localhost)
      - open the browser to the Spotify auth URL
      - capture the ?code=... automatically with the local server

    If anything goes wrong with the local server flow, or if use_cli_auth=True,
    we fall back to the classic CLI-based copy/paste flow.
    """
    if use_cli_auth:
        return _get_spotify_token_cli()

    try:
        return _get_spotify_token_local_server()
    except Exception as e:
        print_warning(
            f"Automatic browser authorization failed ({e}). Falling back to CLI flow."
        )
        return _get_spotify_token_cli()


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
    write_json(SPOTIFY_TOKEN_FILE, token_info)
    return token_info


def load_spotify_token(use_cli_auth: bool = False) -> Dict:
    """
    Load Spotify token from cache, or perform auth flow if missing/expired.

    If use_cli_auth=True, the initial auth will use the CLI copy/paste flow.
    Otherwise, it will try the local HTTP server + browser flow first.
    """
    token_info = read_json(SPOTIFY_TOKEN_FILE, default=None)
    if token_info is None:
        token_info = get_spotify_token(use_cli_auth=use_cli_auth)

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
    print_step("Fetching liked tracks from Spotify...")
    tracks: List[Track] = []
    url = f"{SPOTIFY_API_BASE}/me/tracks"
    params = {"limit": 50}
    headers = spotify_headers(token_info)

    page = 0
    total = None

    while url:
        page += 1
        r = requests.get(url, headers=headers, params=params)
        r.raise_for_status()
        data = r.json()
        if total is None:
            total = data.get("total", 0)

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
        url = data.get("next")
        params = None  # next URL already includes params

        if total:
            estimated_pages = (total + 49) // 50
            print_progress_bar(page, estimated_pages, prefix="  Fetching pages")

    print_info(f"{len(tracks)} liked tracks fetched.")
    return tracks


def get_user_playlists(token_info: Dict) -> List[Dict]:
    playlists = []
    url = f"{SPOTIFY_API_BASE}/me/playlists"
    headers = spotify_headers(token_info)
    params = {"limit": 50}

    while url:
        r = requests.get(url, headers=headers, params=params)
        r.raise_for_status()
        data = r.json()
        playlists.extend(data["items"])
        url = data.get("next")
        params = None

    print_info(f"{len(playlists)} playlists found.")
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
