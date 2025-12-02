from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.core import log_info
from app.data import (
    PipelineJob as DataPipelineJob,
    PipelineJobStatus as DataPipelineJobStatus,
    create_job,
    load_jobs,
)
from app.spotify import (
    SpotifyTokenMissing,
    TrackSource,
    TrackSourceType,
    build_spotify_auth_url,
    load_spotify_token,
)

from .jobs import _job_to_response, _run_job_background
from .schemas import PipelineJobListResponse

router = APIRouter()


class TrackSourcePayload(BaseModel):
    """Request payload describing a logical track source."""

    source_type: TrackSourceType
    source_id: Optional[str] = None
    label: Optional[str] = None


class FetchSourcesRequest(BaseModel):
    """Request body for /pipeline/tracks/fetch-sources."""

    sources: List[TrackSourcePayload]


def _raise_unauth(e: SpotifyTokenMissing) -> None:
    """Translate SpotifyTokenMissing into an HTTP 401 with auth_url details."""
    raise HTTPException(
        status_code=401,
        detail={
            "status": "unauthenticated",
            "message": str(e) or "Spotify authorization required.",
            "auth_url": build_spotify_auth_url(),
        },
    )


@router.post("/tracks/fetch-sources", response_model=PipelineJobListResponse)
def fetch_tracks_for_sources(
    body: FetchSourcesRequest,
    background_tasks: BackgroundTasks,
) -> PipelineJobListResponse:
    """
    Launch one async fetch_tracks job per requested source.

    Each job:
      - has step="fetch_tracks"
      - carries metadata describing the logical source
      - will produce a payload with:
          {
            "step": "fetch_tracks",
            "status": "done",
            "source": {...},
            "tracks": [...serialized Track...],
          }
    """

    # Early auth check so we fail fast instead of queueing doomed jobs.
    try:
        load_spotify_token()
    except SpotifyTokenMissing as e:
        _raise_unauth(e)

    jobs: List[DataPipelineJob] = []

    for src in body.sources:
        track_source = TrackSource(
            source_type=src.source_type,
            source_id=src.source_id,
            label=src.label,
        )

        metadata: Dict[str, Any] = {
            "source_type": track_source.source_type.value,
            "source_id": track_source.source_id,
            "source_label": track_source.label,
        }

        job = create_job(step="fetch_tracks", metadata=metadata)
        background_tasks.add_task(_run_job_background, job.id)
        jobs.append(job)

        log_info(
            "Created fetch_tracks job "
            f"id={job.id} source_type={metadata['source_type']} "
            f"source_id={metadata['source_id']!r} label={metadata['source_label']!r}"
        )

    return PipelineJobListResponse(jobs=[_job_to_response(j) for j in jobs])


@router.get("/tracks/aggregate")
def aggregate_tracks() -> Dict[str, List[Dict[str, Any]]]:
    """
    Aggregate results from all completed fetch_tracks jobs.

    - Filters jobs with step == "fetch_tracks" and status == "done".
    - Combines and deduplicates tracks by their "id" field.
    - Returns a list of distinct sources found in job metadata/payload.
    """
    jobs_dict = load_jobs()

    aggregated_tracks: List[Dict[str, Any]] = []
    aggregated_sources: List[Dict[str, Any]] = []

    seen_track_ids: set[str] = set()
    seen_sources: set[Tuple[Optional[str], Optional[str], Optional[str]]] = set()

    for job in jobs_dict.values():
        if job.step != "fetch_tracks" or job.status != DataPipelineJobStatus.DONE:
            continue

        payload = job.payload or {}
        job_tracks = payload.get("tracks") or []
        if isinstance(job_tracks, list):
            for item in job_tracks:
                if not isinstance(item, dict):
                    continue
                track_id = item.get("id")
                if not track_id or track_id in seen_track_ids:
                    continue
                seen_track_ids.add(track_id)
                aggregated_tracks.append(item)

        # Prefer explicit job.metadata, fall back to payload["source"] if needed.
        meta = job.metadata or {}
        if not meta:
            source_payload = payload.get("source") or {}
            meta = {
                "source_type": source_payload.get("source_type"),
                "source_id": source_payload.get("source_id"),
                "source_label": source_payload.get("source_label"),
            }

        source_type = meta.get("source_type")
        source_id = meta.get("source_id")
        source_label = meta.get("source_label")

        key = (source_type, source_id, source_label)
        if source_type and key not in seen_sources:
            seen_sources.add(key)
            aggregated_sources.append(
                {
                    "source_type": source_type,
                    "source_id": source_id,
                    "source_label": source_label,
                }
            )

    return {
        "tracks": aggregated_tracks,
        "sources": aggregated_sources,
    }
