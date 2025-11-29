import json
import os
from dataclasses import asdict
from typing import List

from config import TRACKS_CACHE_FILE
from models import Track


def _ensure_dir(path: str) -> None:
    directory = os.path.dirname(path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)


def load_tracks_cache() -> List[Track]:
    if not os.path.exists(TRACKS_CACHE_FILE):
        return []
    with open(TRACKS_CACHE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [Track(**item) for item in data]


def save_tracks_cache(tracks: List[Track]) -> None:
    _ensure_dir(TRACKS_CACHE_FILE)
    data = [asdict(t) for t in tracks]
    with open(TRACKS_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
