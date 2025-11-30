import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict
from urllib.parse import urlencode, urlparse, parse_qs

import requests

from app.config import (
    SPOTIFY_CLIENT_ID,
    SPOTIFY_CLIENT_SECRET,
    SPOTIFY_REDIRECT_URI,
    SPOTIFY_AUTH_URL,
    SPOTIFY_TOKEN_URL,
    SPOTIFY_API_BASE,
    SCOPES,
    SPOTIFY_TOKEN_FILE,
)
from app.core.cli_utils import print_step, print_info, print_warning
from app.core.fs_utils import write_json, read_json


class _SpotifyAuthHandler(BaseHTTPRequestHandler):
    authorization_code: str | None = None

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        code = qs.get("code", [None])[0]
        _SpotifyAuthHandler.authorization_code = code

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            b"<html><body><h1>Spotify authorization complete</h1>"
            b"<p>You can close this window and return to the application.</p>"
            b"</body></html>"
        )

    def log_message(self, format, *args):
        return


def _run_local_http_server_for_auth(timeout: int = 180) -> str:
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

    try:
        webbrowser.open(auth_url)
    except Exception:
        pass

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
    try:
        webbrowser.open(auth_url)
    except Exception:
        pass

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


def get_spotify_token() -> Dict:
    """
    Get a new Spotify access/refresh token via authorization code flow.

    Default behaviour:
      - try local HTTP server + browser flow
      - if it fails, fall back to CLI copy/paste flow.
    """
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


def load_spotify_token() -> Dict:
    """
    Load Spotify token from cache, or perform auth flow if missing/expired.
    """
    token_info = read_json(SPOTIFY_TOKEN_FILE, default=None)
    if token_info is None:
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
