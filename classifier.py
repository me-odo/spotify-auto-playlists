import json
import os
from typing import Dict, List

from config import CLASSIFICATION_CACHE_FILE
from models import Track, Classification
from cli_utils import print_progress_bar


def _ensure_classif_dir() -> None:
    directory = os.path.dirname(CLASSIFICATION_CACHE_FILE)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)


def load_classification_cache() -> Dict[str, Dict]:
    if CLASSIFICATION_CACHE_FILE and os.path.exists(CLASSIFICATION_CACHE_FILE):
        with open(CLASSIFICATION_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_classification_cache(cache: Dict[str, Dict]) -> None:
    if not CLASSIFICATION_CACHE_FILE:
        return
    _ensure_classif_dir()
    with open(CLASSIFICATION_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def classify_tracks(
    tracks: List[Track],
    refresh_existing: bool = False,
) -> Dict[str, Classification]:
    """
    Simple classification without AI:
    - put all tracks into a single 'all' category.
    - still uses a cache in case we later extend this logic.
    """
    cache = load_classification_cache()

    if refresh_existing:
        print("↻ Refreshing classification cache (simple 'all' mode).")
        cache = {}

    classifications: Dict[str, Classification] = {}

    to_process = tracks
    total = len(to_process)
    print("Classifying tracks (simple 'all' mode)...")

    for idx, t in enumerate(to_process, start=1):
        if not refresh_existing and t.id in cache:
            c_dict = cache[t.id]
            classifications[t.id] = Classification(
                mood=c_dict["mood"],
                genre_macro=c_dict["genre_macro"],
                extra=c_dict.get("extra", {}),
            )
        else:
            c = Classification(
                mood="all",
                genre_macro="all",
                extra={"note": "dummy classification without AI"},
            )
            classifications[t.id] = c
            cache[t.id] = {
                "mood": c.mood,
                "genre_macro": c.genre_macro,
                "extra": c.extra,
            }

        if total > 0:
            print_progress_bar(idx, total, prefix="  Classifying")

    save_classification_cache(cache)
    print(f"\n→ Classification done for {len(classifications)} tracks (all -> 'all').")
    return classifications
