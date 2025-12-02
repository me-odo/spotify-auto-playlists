from typing import Dict, List

from fastapi import APIRouter, HTTPException

from app.core import log_info
from app.pipeline import (
    build_rule_based_playlists,
    build_target_playlists,
    load_classification_cache,
    load_tracks_cache,
)

from .schemas import (
    BuildResponse,
    PlaylistPreview,
    RuleBasedPlaylistPreview,
    RuleBasedPlaylistPreviewResponse,
    RuleBasedPreviewRequest,
)

router = APIRouter()


@router.get("/build", response_model=BuildResponse)
def build_playlists() -> BuildResponse:
    """
    Étape 4 : génération des playlists cibles.
    - AUCUN appel externe
    - Utilise uniquement les caches : tracks + classification
    """

    tracks = load_tracks_cache()
    if not tracks:
        raise HTTPException(
            status_code=400,
            detail="Tracks cache is empty. Run /pipeline/tracks first.",
        )

    classifications = load_classification_cache()
    if not classifications:
        raise HTTPException(
            status_code=400,
            detail="Classification cache is empty. Run /pipeline/classify first.",
        )

    # NOTE : build_target_playlists doit avoir la signature (tracks, classifications)
    playlists_mood, playlists_genre, playlists_year = build_target_playlists(
        tracks,
        classifications,
    )

    target_playlists: Dict[str, List[str]] = {}
    for source in (playlists_mood, playlists_genre, playlists_year):
        for name, ids in source.items():
            bucket = target_playlists.setdefault(name, [])
            for tid in ids:
                if tid not in bucket:
                    bucket.append(tid)

    previews = [
        PlaylistPreview(name=name, tracks_count=len(ids))
        for name, ids in target_playlists.items()
    ]

    log_info(f"Built {len(previews)} target playlists.")

    return BuildResponse(status="done", playlists=previews)


@router.post(
    "/playlists/preview-from-rules",
    response_model=RuleBasedPlaylistPreviewResponse,
)
def preview_playlists_from_rules(
    body: RuleBasedPreviewRequest,
) -> RuleBasedPlaylistPreviewResponse:
    """
    Preview rule-based playlists for an in-memory set of tracks and rules.

    The endpoint does not modify any persistent state.
    """
    # 1) Pydantic validation is handled automatically by FastAPI via the request body.
    rules = body.rules or []
    tracks_input = body.tracks or []

    # 2) Convert body.tracks into the format expected by the pipeline helper.
    pipeline_tracks = [
        {
            "track_id": t.track_id,
            "enrichment": t.enrichment or {},
        }
        for t in tracks_input
    ]

    # 3) Delegate rule evaluation to the pure pipeline helper.
    raw_playlists = build_rule_based_playlists(rules=rules, tracks=pipeline_tracks)

    # 4) Adapt the returned structures into API models.
    previews = [
        RuleBasedPlaylistPreview(
            rule_id=p["rule_id"],
            rule_name=p["rule_name"],
            track_ids=p["track_ids"],
            track_count=p["track_count"],
        )
        for p in raw_playlists
    ]

    return RuleBasedPlaylistPreviewResponse(playlists=previews)
