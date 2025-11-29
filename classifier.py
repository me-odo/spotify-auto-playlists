import json
import os
from typing import Dict, List

from config import CLASSIFICATION_CACHE_FILE
from models import Track, Classification


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
    features_by_id: Dict[str, Dict],
    refresh_existing: bool = False,
) -> Dict[str, Classification]:
    """
    Version simplifiée SANS IA :
    - met tous les titres dans une catégorie 'all'
    - permet quand même d'utiliser un cache sur le principe.
    """
    cache = load_classification_cache()

    if refresh_existing:
        print("↻ Refresh du cache de classification (mode simple 'all').")
        cache = {}

    # On pourrait utiliser features_by_id plus tard, mais pour l'instant on s'en fiche
    for t in tracks:
        # On ne fait rien de spécial avec les features actuellement
        t.features = features_by_id.get(t.id, {})

    classifications: Dict[str, Classification] = {}

    for t in tracks:
        if not refresh_existing and t.id in cache:
            c_dict = cache[t.id]
            classifications[t.id] = Classification(
                mood=c_dict["mood"],
                genre_macro=c_dict["genre_macro"],
                extra=c_dict.get("extra", {}),
            )
            continue

        # Classification "dummy" : tout dans 'all'
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

    # On sauve le cache à la fin
    save_classification_cache(cache)

    return classifications
