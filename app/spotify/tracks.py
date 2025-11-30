import requests
from typing import Dict, List


from app.core.cli_utils import (
    print_step,
    print_info,
    print_progress_bar,
)
from app.spotify.auth import spotify_headers
from app.config import (
    SPOTIFY_API_BASE,
)
from app.core.models import Track


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
