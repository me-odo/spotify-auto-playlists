from typing import Dict, List

from app.config import CLASSIFICATION_CACHE_FILE
from app.core.cli_utils import (
    print_info,
    print_step,
    print_progress_bar,
)
from app.core.fs_utils import write_json, read_json
from app.core.models import Track, Classification


def load_classification_cache() -> Dict[str, Dict]:
    if not CLASSIFICATION_CACHE_FILE:
        return {}
    return read_json(CLASSIFICATION_CACHE_FILE, default={})


def save_classification_cache(cache: Dict[str, Dict]) -> None:
    if not CLASSIFICATION_CACHE_FILE:
        return
    write_json(CLASSIFICATION_CACHE_FILE, cache)


def _get_prob(highlevel: Dict, feature: str, label: str) -> float:
    """
    Safely read probability highlevel[feature]["all"][label].
    Returns 0.0 if anything is missing.
    """
    try:
        return float(highlevel[feature]["all"][label])
    except Exception:
        return 0.0


def _infer_mood_from_highlevel(highlevel: Dict) -> str:
    """
    Simple rule-based mood inference from AcousticBrainz highlevel data.
    Returns one of:
      "workout", "party", "cleaning", "focus", "chill", "sleep", "unclassified"
    """
    d_dance = _get_prob(highlevel, "danceability", "danceable")
    m_aggr = _get_prob(highlevel, "mood_aggressive", "aggressive")
    m_relax = _get_prob(highlevel, "mood_relaxed", "relaxed")
    m_happy = _get_prob(highlevel, "mood_happy", "happy")
    m_party = _get_prob(highlevel, "mood_party", "party")

    # 1) Workout: very danceable + somewhat aggressive
    if d_dance >= 0.6 and m_aggr >= 0.4:
        return "workout"

    # 2) Party: danceable + party mood
    if d_dance >= 0.6 and m_party >= 0.5:
        return "party"

    # 3) Cleaning: medium/high danceability, happy, not too aggressive
    if 0.4 <= d_dance < 0.7 and m_happy >= 0.5 and m_aggr < 0.4:
        return "cleaning"

    # 4) Focus: relaxed, not very danceable, not aggressive
    if m_relax >= 0.5 and d_dance < 0.5 and m_aggr < 0.3:
        return "focus"

    # 5) Chill: relaxed, not too danceable
    if m_relax >= 0.4 and d_dance < 0.7:
        return "chill"

    # 6) Sleep: very relaxed, low danceability, almost no aggression
    if m_relax >= 0.7 and d_dance < 0.3 and m_aggr < 0.2:
        return "sleep"

    return "unclassified"


def classify_tracks_rule_based(
    tracks: List[Track],
    external_features: Dict[str, Dict],
    refresh_existing: bool = False,
) -> Dict[str, Classification]:
    """
    Rule-based classification using AcousticBrainz highlevel features.
    For each track:
      - if external features exist -> infer a mood (workout/party/.../unclassified)
      - else -> mood = "unclassified"

    Uses the same classification cache as before, keyed by track.id.
    """
    cache = load_classification_cache()

    if refresh_existing:
        print_info("Refreshing classification cache (rule-based mood model).")
        cache = {}

    classifications: Dict[str, Classification] = {}
    total = len(tracks)

    print_step("Classifying tracks (rule-based mood model)...")

    for idx, t in enumerate(tracks, start=1):
        if not t.id:
            continue

        # 1) If not refreshing and we have a cached classification, reuse it
        if not refresh_existing and t.id in cache:
            c_dict = cache[t.id]
            classifications[t.id] = Classification(
                mood=c_dict.get("mood", "unclassified"),
                genre_macro=c_dict.get("genre_macro", "all"),
                extra=c_dict.get("extra", {}),
            )
        else:
            # 2) Compute new classification
            features_entry = external_features.get(t.id)
            if features_entry and isinstance(features_entry, dict):
                highlevel = features_entry.get("highlevel", {})
                mood = _infer_mood_from_highlevel(highlevel)
                has_external = True
            else:
                mood = "unclassified"
                highlevel = {}
                has_external = False

            c = Classification(
                mood=mood,
                genre_macro="all",
                extra={
                    "source": "rule_based_acousticbrainz",
                    "has_external_features": has_external,
                },
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

    # Optional: small summary per mood
    mood_counts: Dict[str, int] = {}
    for c in classifications.values():
        mood_counts[c.mood] = mood_counts.get(c.mood, 0) + 1

    print_info("Classification done.")
    print_info("Tracks per mood:")
    for mood, count in sorted(mood_counts.items(), key=lambda x: x[0]):
        print_info(f"    {mood}: {count}")

    return classifications
