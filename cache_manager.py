from dataclasses import asdict
from typing import List

from config import TRACKS_CACHE_FILE
from fs_utils import write_json, read_json
from models import Track


def load_tracks_cache() -> List[Track]:
    data = read_json(TRACKS_CACHE_FILE, default=[])
    return [Track(**item) for item in data]


def save_tracks_cache(tracks: List[Track]) -> None:
    data = [asdict(t) for t in tracks]
    write_json(TRACKS_CACHE_FILE, data)
