from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel


class TracksResponse(BaseModel):
    step: str = "tracks"
    status: str
    tracks_count: int
    from_cache: bool
    fetched_from_spotify: int


class ExternalResponse(BaseModel):
    step: str = "external"
    status: str
    total_tracks: int
    enriched: int
    unmatched: int


class ClassifyStats(BaseModel):
    tracks_processed: int
    moods: Dict[str, int]


class ClassifyResponse(BaseModel):
    step: str = "classify"
    status: str
    stats: ClassifyStats


class PlaylistPreview(BaseModel):
    name: str
    tracks_count: int


class BuildResponse(BaseModel):
    step: str = "build"
    status: str
    playlists: List[PlaylistPreview]


class TrackInfo(BaseModel):
    id: str
    name: str
    artist: str
    album: Optional[str] = None


class PlaylistDiff(BaseModel):
    name: str
    playlist_id: Optional[str] = None
    existing_ids: List[str]
    target_ids: List[str]
    duplicates: List[str]
    new_to_add: List[str]

    existing_tracks: List[TrackInfo]
    target_tracks: List[TrackInfo]
    duplicates_tracks: List[TrackInfo]
    new_to_add_tracks: List[TrackInfo]


class DiffResponse(BaseModel):
    step: str = "diff"
    status: str
    playlists: List[PlaylistDiff]


class PlaylistApplyPayload(BaseModel):
    name: str
    playlist_id: Optional[str] = None
    target_ids: List[str]


class ApplyRequest(BaseModel):
    playlists: List[PlaylistApplyPayload]


class ApplyResult(BaseModel):
    name: str
    playlist_id: str
    target_count: int


class ApplyResponse(BaseModel):
    step: str = "apply"
    status: str
    results: List[ApplyResult]


class PipelineJobStatus(str, Enum):
    pending = "pending"
    running = "running"
    done = "done"
    error = "error"


class PipelineJobResponse(BaseModel):
    id: str
    step: str
    status: PipelineJobStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    progress: Optional[float] = None
    message: Optional[str] = None
    payload: Optional[dict] = None
    metadata: Optional[dict] = None


class PipelineJobListResponse(BaseModel):
    jobs: List[PipelineJobResponse]
