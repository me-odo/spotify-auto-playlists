import time
from typing import Dict
from urllib.parse import urlencode

import requests

from app.config import (
    SCOPES,
    SPOTIFY_API_BASE,
    SPOTIFY_AUTH_URL,
    SPOTIFY_CLIENT_ID,
    SPOTIFY_CLIENT_SECRET,
    SPOTIFY_REDIRECT_URI,
    SPOTIFY_TOKEN_FILE,
    SPOTIFY_TOKEN_URL,
)
from app.core import log_info, log_warning, read_json, write_json


class SpotifyAuthError(Exception):
    """Base error for Spotify auth."""


class SpotifyTokenMissing(SpotifyAuthError):
    """Raised when no token is available and user must authorize."""


def build_spotify_auth_url() -> str:
    """
    Build the Spotify /authorize URL that the frontend (or user)
    should open in a browser to start the OAuth flow.
    """
    params = {
        "response_type": "code",
        "client_id": SPOTIFY_CLIENT_ID,
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "scope": " ".join(SCOPES),
    }
    return f"{SPOTIFY_AUTH_URL}?{urlencode(params)}"


def exchange_code_for_token(code: str) -> Dict:
    """
    Exchange an authorization code (from /auth/callback) for an access/refresh token.
    Persist the token to SPOTIFY_TOKEN_FILE.
    """
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
    log_info("Spotify token obtained and stored.")
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
    # Spotify peut ne pas renvoyer à nouveau un refresh_token : on garde l'ancien
    token_info["refresh_token"] = refresh_token
    token_info["timestamp"] = int(time.time())
    write_json(SPOTIFY_TOKEN_FILE, token_info)
    log_info("Spotify access token refreshed.")
    return token_info


def load_spotify_token() -> Dict:
    """
    Load Spotify token from cache, or raise SpotifyTokenMissing if absent.

    - No more automatic browser open / local HTTP server.
    - The API layer is responsible for detecting SpotifyTokenMissing and
      returning a 401 with an auth_url to the client.
    """
    token_info = read_json(SPOTIFY_TOKEN_FILE, default=None)
    if token_info is None:
        log_warning("No Spotify token found in cache.")
        raise SpotifyTokenMissing("No Spotify token available.")

    now = int(time.time())
    expires_in = token_info.get("expires_in", 3600)
    if now - token_info.get("timestamp", 0) > expires_in - 60:
        log_info("Spotify access token expired. Refreshing...")
        if "refresh_token" not in token_info:
            log_warning("No refresh_token available – re-authorization required.")
            raise SpotifyTokenMissing("No valid refresh token available.")
        token_info = refresh_spotify_token(token_info["refresh_token"])
    return token_info


def spotify_headers(token_info: Dict) -> Dict:
    return {"Authorization": f"Bearer {token_info['access_token']}"}


def get_current_user_id(token_info: Dict) -> str:
    r = requests.get(f"{SPOTIFY_API_BASE}/me", headers=spotify_headers(token_info))
    r.raise_for_status()
    return r.json()["id"]
