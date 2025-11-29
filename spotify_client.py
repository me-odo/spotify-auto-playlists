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
    print("Ouvrir l'URL suivante dans un navigateur et autoriser l'application :")
    print(auth_url)
    try:
        webbrowser.open(auth_url)
    except Exception:
        pass

    auth_code = input(
        "Collez ici le paramètre 'code' de l'URL de redirection : "
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
    print("Récupération des titres likés…")
    tracks: List[Track] = []
    url = f"{SPOTIFY_API_BASE}/me/tracks"
    params = {"limit": 50}
    headers = spotify_headers(token_info)

    while url:
        r = requests.get(url, headers=headers, params=params)
        r.raise_for_status()
        data = r.json()
        for item in data["items"]:
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
        url = data["next"]

    print(f"→ {len(tracks)} titres likés récupérés.")
    return tracks


def get_audio_features(token_info: Dict, track_ids: List[str]) -> Dict[str, Dict]:
    """
    Appelle /audio-features avec des batchs de 100 IDs.
    Si Spotify renvoie une erreur (403, etc.), on loggue et on continue sans features.
    """
    print("Récupération des audio features…")
    headers = spotify_headers(token_info)
    features_by_id: Dict[str, Dict] = {}

    if not track_ids:
        return features_by_id

    for i in range(0, len(track_ids), 100):
        batch = track_ids[i : i + 100]
        ids_param = ",".join(batch)
        url = f"{SPOTIFY_API_BASE}/audio-features"
        r = requests.get(url, headers=headers, params={"ids": ids_param})

        # Si 403 → on log une fois et on arrête proprement la récupération des features
        if r.status_code == 403:
            print("⚠️ Spotify renvoie 403 Forbidden sur /audio-features.")
            try:
                print("Réponse Spotify :", r.text)
            except Exception:
                pass
            print(
                "On continue sans audio features ; la classification IA utilisera seulement titre/artiste/album."
            )
            return {}  # on sort directement, sans faire raise_for_status

        # Autres erreurs éventuelles : on log et on ignore juste ce batch
        if not r.ok:
            print(
                f"⚠️ Erreur lors de l'appel /audio-features (status {r.status_code}). Batch ignoré."
            )
            try:
                print("Réponse Spotify :", r.text)
            except Exception:
                pass
            continue

        data = r.json()
        for f in data.get("audio_features", []):
            if f and f.get("id"):
                features_by_id[f["id"]] = f

    return features_by_id


def get_user_playlists(token_info: Dict) -> List[Dict]:
    print("Récupération des playlists existantes…")
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

    print(f"→ {len(playlists)} playlists trouvées.")
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
        "description": "Playlist générée automatiquement par script (mood/genre/year).",
    }
    r = requests.post(url, headers=headers, json=payload)
    r.raise_for_status()
    playlist = r.json()
    existing_playlists.append(playlist)
    print(f"Playlist créée : {name}")
    return playlist["id"]


def set_playlist_tracks(
    token_info: Dict, playlist_id: str, track_ids: List[str]
) -> None:
    """
    Remplace le contenu d'une playlist par un set de titres donné.
    - Supprime tous les titres existants par batchs de 100.
    - Ajoute les nouveaux titres (sans doublons) par batchs de 100.
    """
    headers = spotify_headers(token_info)

    # 1) Récupérer tous les items actuels
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
        params = None  # déjà dans l'URL "next"

    # 2) Supprimer tous les titres existants par batchs de 100
    url_remove = f"{SPOTIFY_API_BASE}/playlists/{playlist_id}/tracks"
    while uris_to_remove:
        batch = uris_to_remove[:100]
        uris_to_remove = uris_to_remove[100:]
        body = {"tracks": [{"uri": u} for u in batch]}
        r = requests.delete(url_remove, headers=headers, json=body)
        r.raise_for_status()

    # 3) Dédupliquer les track_ids en conservant l'ordre
    seen = set()
    unique_ids: List[str] = []
    for tid in track_ids:
        if tid and tid not in seen:
            seen.add(tid)
            unique_ids.append(tid)

    if not unique_ids:
        return

    # 4) Ajouter les nouveaux titres par batchs de 100
    uris = [f"spotify:track:{tid}" for tid in unique_ids]
    url_add = f"{SPOTIFY_API_BASE}/playlists/{playlist_id}/tracks"
    for i in range(0, len(uris), 100):
        batch = uris[i : i + 100]
        r = requests.post(url_add, headers=headers, json={"uris": batch})
        r.raise_for_status()


def get_playlist_tracks(token_info: Dict, playlist_id: str) -> List[str]:
    """
    Retourne la liste des track IDs d'une playlist donnée.
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
        params = None  # déjà dans l'URL "next"

    return track_ids


def incremental_update_playlist(
    token_info: Dict, playlist_id: str, target_ids: List[str]
) -> None:
    """
    Met à jour une playlist de manière incrémentale :
      - supprime les doublons existants
      - ajoute uniquement les titres absents

    ⚠️ Ne supprime PAS les titres qui sont présents mais pas dans target_ids.
    """
    headers = spotify_headers(token_info)

    # 1) Récupérer l'état actuel de la playlist
    existing_ids = get_playlist_tracks(token_info, playlist_id)
    counts = Counter(existing_ids)

    # 2) Détecter les doublons (titres présents > 1 fois)
    duplicates = [tid for tid, c in counts.items() if c > 1]

    # 3) Supprimer complètement les titres dupliqués
    if duplicates:
        url_remove = f"{SPOTIFY_API_BASE}/playlists/{playlist_id}/tracks"
        tracks_to_remove = [{"uri": f"spotify:track:{tid}"} for tid in duplicates]
        # suppression par batchs de 100
        while tracks_to_remove:
            batch = tracks_to_remove[:100]
            tracks_to_remove = tracks_to_remove[100:]
            r = requests.delete(url_remove, headers=headers, json={"tracks": batch})
            r.raise_for_status()

    # 4) Recalcule de l'état (conceptuel) après suppression des doublons
    #    (les doublons ont été totalement retirés de la playlist)
    existing_set = set(existing_ids) - set(duplicates)

    target_set = set(target_ids)

    # 5) Titres à ajouter = tous ceux qui sont dans la cible mais pas déjà présents
    to_add = list(target_set - existing_set)

    if not to_add:
        print(
            "  Rien à ajouter (playlist déjà à jour, sans compter les doublons supprimés)."
        )
        return

    # 6) Ajout des nouveaux titres
    uris = [f"spotify:track:{tid}" for tid in to_add]
    url_add = f"{SPOTIFY_API_BASE}/playlists/{playlist_id}/tracks"
    for i in range(0, len(uris), 100):
        batch = uris[i : i + 100]
        r = requests.post(url_add, headers=headers, json={"uris": batch})
        r.raise_for_status()
