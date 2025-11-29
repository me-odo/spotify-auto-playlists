from dataclasses import asdict
import json
import os
from typing import List

from config import TRACKS_CACHE_FILE
from fs_utils import ensure_parent_dir
from models import Track


def load_tracks_cache() -> List[Track]:
    if not os.path.exists(TRACKS_CACHE_FILE):
        return []
    with open(TRACKS_CACHE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [Track(**item) for item in data]


def save_tracks_cache(tracks: List[Track]) -> None:
    ensure_parent_dir(TRACKS_CACHE_FILE)
    data = [asdict(t) for t in tracks]
    with open(TRACKS_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
