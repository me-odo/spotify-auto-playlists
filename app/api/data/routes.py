from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core import Classification, PlaylistRuleSet, RuleGroup, Track
from app.data import (
    ClassificationRepository,
    TracksRepository,
    load_enrichments_cache,
    load_rules,
    save_rules,
)
from app.pipeline import load_external_features_cache, matches_rules

router = APIRouter()

tracks_repository = TracksRepository()
classification_repository = ClassificationRepository()


class TrackInfo(BaseModel):
    id: str
    name: str
    artist: str
    album: str | None = None


class TracksResponse(BaseModel):
    tracks: List[TrackInfo]
    total: int


class UpdateClassificationRequest(BaseModel):
    labels: Dict[str, Any]


class RuleEvaluationRequest(BaseModel):
    rules: RuleGroup
    enrichment: Dict[str, Any]


class RuleValidationRequest(BaseModel):
    rules: RuleGroup


DEFAULT_CLASSIFIER_ID = "mood_v1"
DEFAULT_FEATURE_PROVIDER_ID = "acousticbrainz"


@router.get("/tracks", response_model=TracksResponse)
def get_tracks(
    limit: int = 200,
    offset: int = 0,
    include_features: bool = False,  # reserved for future use
) -> TracksResponse:
    """
    Return a paginated view of tracks from the tracks cache.

    The `include_features` flag is accepted for forward-compatibility but is
    currently not used to alter the response payload.
    """
    tracks: List[Track] = tracks_repository.load_tracks() or []
    total = len(tracks)

    if limit < 0 or offset < 0:
        raise HTTPException(
            status_code=400, detail="limit and offset must be non-negative."
        )

    slice_start = min(offset, total)
    slice_end = min(slice_start + limit, total)
    window = tracks[slice_start:slice_end]

    items: List[TrackInfo] = []
    for t in window:
        if not t.id:
            continue
        items.append(
            TrackInfo(
                id=t.id,
                name=t.name,
                artist=t.artist,
                album=t.album,
            )
        )

    return TracksResponse(tracks=items, total=total)


@router.get("/features/{provider_id}")
def get_features(provider_id: str) -> Dict[str, Dict]:
    """
    Return the cached features for the given provider, indexed by track id.

    If no cache exists for the provider, an empty mapping is returned.
    """
    if provider_id != DEFAULT_FEATURE_PROVIDER_ID:
        # Unknown provider ids simply return an empty mapping for now.
        return {}

    features = load_external_features_cache() or {}
    return features


def serialize_classification(classification: Classification) -> dict:
    """Convert a Classification object to a plain JSON-serializable dict."""
    return {
        "mood": classification.mood,
        "genre": classification.genre,
        "year": classification.year,
    }


@router.get("/classifications/{classifier_id}")
def get_classifications(classifier_id: str) -> Dict[str, Dict]:
    """
    Return the cached classifications for the given classifier id.

    For the current implementation, only the default classifier id is backed
    by the on-disk classification cache. Other ids return an empty mapping.
    """
    if classifier_id != DEFAULT_CLASSIFIER_ID:
        return {}

    cache = classification_repository.load_classifications(classifier_id) or {}
    # Expose a simple mapping track_id -> labels dict for the API.

    return {
        track_id: serialize_classification(classification)
        for track_id, classification in cache.items()
    }


@router.patch("/classifications/{classifier_id}/{track_id}")
def patch_classification(
    classifier_id: str,
    track_id: str,
    body: UpdateClassificationRequest,
) -> Dict[str, Any]:
    """
    Update the classification entry for a given classifier and track id.

    The body must contain a `labels` object whose keys correspond to fields
    on the underlying Classification model (for example: mood, genre, year).

    The classification cache is updated and the resulting entry is returned.
    """
    if classifier_id != DEFAULT_CLASSIFIER_ID:
        raise HTTPException(status_code=404, detail="Unknown classifier id.")

    cache = classification_repository.load_classifications(classifier_id) or {}
    labels = body.labels or {}

    existing = cache.get(track_id)
    if existing is None:
        # Create a new Classification instance using provided labels, with a
        # safe default for required fields.
        mood = (labels.get("mood") or "unclassified").lower()
        genre = labels.get("genre")
        year = labels.get("year")
        classification = Classification(mood=mood, genre=genre, year=year)
    else:
        classification = existing
        for key, value in labels.items():
            if hasattr(classification, key):
                setattr(classification, key, value)

    cache[track_id] = classification
    classification_repository.save_classifications(classifier_id, cache)

    return {
        "classifier_id": classifier_id,
        "track_id": track_id,
        "labels": serialize_classification(classification),
    }


@router.get("/enrichments")
def get_enrichments() -> Dict[str, List[Dict[str, Any]]]:
    """
    Return unified track enrichments indexed by track id.

    The response is a JSON object:
      {
        "track_id": [
          { "source": "...", "version": "...", "timestamp": "...", "categories": {...} },
          ...
        ],
        ...
      }

    If no enrichments exist, an empty mapping {} is returned.
    """
    cache = load_enrichments_cache() or {}

    result: Dict[str, List[Dict[str, Any]]] = {}
    for track_id, entries in cache.items():
        items: List[Dict[str, Any]] = []
        if isinstance(entries, list):
            for entry in entries:
                if hasattr(entry, "dict"):
                    # TrackEnrichment (or similar Pydantic model)
                    items.append(entry.dict())
                elif isinstance(entry, dict):
                    items.append(dict(entry))
        if items:
            result[str(track_id)] = items

    return result


@router.get("/rules")
def get_rules() -> List[Dict[str, Any]]:
    """
    Return stored playlist rules as a JSON list.

    The response is a list of PlaylistRuleSet-like dicts. Each object contains
    at least 'id' and 'name' fields. It is acceptable to return an empty list
    when no rules are defined.
    """
    rules = load_rules() or []

    result: List[Dict[str, Any]] = []
    for rule in rules:
        if hasattr(rule, "dict"):
            data = rule.dict()
        elif isinstance(rule, dict):
            data = dict(rule)
        else:
            continue

        # Ensure id and name are always present for frontend / smoke tests.
        if "id" in data and "name" in data:
            result.append(data)
        else:
            # Skip malformed entries without required keys.
            continue

    return result


@router.post("/rules")
def upsert_rule(rule: PlaylistRuleSet) -> Dict[str, Any]:
    """
    Create or update a playlist rule.

    - If a rule with the same id exists, it is replaced (upsert semantics).
    - Otherwise, the new rule is appended.
    - The saved rule is returned as a JSON object.
    """
    existing_rules = load_rules() or []

    updated_rules: List[PlaylistRuleSet] = []
    found = False
    for existing in existing_rules:
        if existing.id == rule.id:
            updated_rules.append(rule)
            found = True
        else:
            updated_rules.append(existing)

    if not found:
        updated_rules.append(rule)

    save_rules(updated_rules)

    # Return the rule as a plain dict; this includes at least "id" and "name".
    return rule.dict()


@router.post("/rules/evaluate")
def evaluate_rules(body: RuleEvaluationRequest) -> Dict[str, bool]:
    """
    Evaluate a RuleGroup against a simple enrichment mapping.

    The response is a JSON object:
      { "matches": true | false }
    """
    result = matches_rules(body.enrichment, body.rules)
    # Ensure a strict boolean for the 'matches' field.
    return {"matches": bool(result)}


@router.post("/rules/validate")
def validate_rules(body: RuleValidationRequest) -> Dict[str, bool]:
    """
    Validate a RuleGroup definition.

    - Relies on Pydantic validation for structure.
    - Performs a dry evaluation against an empty enrichment mapping.
    - Returns { "valid": true } when validation succeeds.
    """
    # Dry run; any internal error here would indicate an invalid rule structure.
    _ = matches_rules({}, body.rules)
    return {"valid": True}
