from typing import Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.logging_utils import log_info, log_step
from app.core.models import Classification
from app.pipeline.cache_manager import load_external_features_cache, load_tracks_cache
from app.pipeline.classifier import classify_tracks_rule_based

router = APIRouter()


class ClassifyStats(BaseModel):
    tracks_processed: int
    moods: Dict[str, int]


class ClassifyResponse(BaseModel):
    step: str = "classify"
    status: str
    stats: ClassifyStats


@router.get("/classify", response_model=ClassifyResponse)
def classify(refresh: bool = False) -> ClassifyResponse:
    """
    Étape 3 : classification rule-based.
    - NE refait aucun fetch externe
    - Utilise tracks + external_features du cache
    - La fonction métier gère le cache classification
    """

    tracks = load_tracks_cache()
    if not tracks:
        raise HTTPException(
            status_code=400,
            detail="Tracks cache is empty. Run /pipeline/tracks first.",
        )

    external_features = load_external_features_cache()
    if not external_features:
        raise HTTPException(
            status_code=400,
            detail="External features cache is empty. Run /pipeline/external first.",
        )

    log_step("Classify step...")

    classifications: Dict[str, Classification] = classify_tracks_rule_based(
        tracks=tracks,
        external_features=external_features,
        refresh_existing=refresh,
    )

    mood_counts: Dict[str, int] = {}
    for c in classifications.values():
        mood_counts[c.mood] = mood_counts.get(c.mood, 0) + 1

    log_info(f"Classification done for {len(classifications)} tracks.")

    return ClassifyResponse(
        status="done",
        stats=ClassifyStats(
            tracks_processed=len(classifications),
            moods=mood_counts,
        ),
    )
