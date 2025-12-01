from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import os
from typing import Any, Dict, Optional

from app.config import CACHE_DIR
from app.core import read_json, write_json

JOBS_FILE = os.path.join(CACHE_DIR, "pipeline_jobs.json")


class PipelineJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


@dataclass
class PipelineJob:
    id: str
    step: str
    status: PipelineJobStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    progress: Optional[float] = None
    message: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None


def _serialize_job(job: PipelineJob) -> Dict[str, Any]:
    return {
        "id": job.id,
        "step": job.step,
        "status": job.status.value,
        "created_at": job.created_at.isoformat(),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "progress": job.progress,
        "message": job.message,
        "payload": job.payload,
    }


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO datetime string and normalize it to UTC-aware.

    This prevents mixing naive and aware datetimes when sorting jobs.
    """
    if not value:
        return None

    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        # Assume previous jobs were stored as UTC without explicit tz info.
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _deserialize_job(data: Dict[str, Any]) -> PipelineJob:
    created_at = _parse_dt(data["created_at"])
    started_at = _parse_dt(data.get("started_at"))
    finished_at = _parse_dt(data.get("finished_at"))

    # Fallback safety: created_at should never be None
    if created_at is None:
        created_at = datetime.now(timezone.utc)

    status_value = data.get("status", PipelineJobStatus.PENDING.value)
    status = PipelineJobStatus(status_value)

    return PipelineJob(
        id=data["id"],
        step=data["step"],
        status=status,
        created_at=created_at,
        started_at=started_at,
        finished_at=finished_at,
        progress=data.get("progress"),
        message=data.get("message"),
        payload=data.get("payload"),
    )


def load_jobs() -> Dict[str, PipelineJob]:
    raw = read_json(JOBS_FILE, default={})
    if not isinstance(raw, dict):
        return {}

    jobs: Dict[str, PipelineJob] = {}
    for job_id, payload in raw.items():
        if not isinstance(payload, dict):
            continue
        payload = dict(payload)
        payload.setdefault("id", job_id)
        try:
            job = _deserialize_job(payload)
        except Exception:
            # Ignore malformed entries
            continue
        jobs[job.id] = job
    return jobs


def save_jobs(jobs: Dict[str, PipelineJob]) -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)
    serialised = {job_id: _serialize_job(job) for job_id, job in jobs.items()}
    write_json(JOBS_FILE, serialised)


def create_job(step: str) -> PipelineJob:
    from uuid import uuid4

    jobs = load_jobs()
    now = datetime.now(timezone.utc)

    job = PipelineJob(
        id=str(uuid4()),
        step=step,
        status=PipelineJobStatus.PENDING,
        created_at=now,
        started_at=None,
        finished_at=None,
        progress=None,
        message=None,
        payload=None,
    )

    # Persist the new job
    jobs[job.id] = job
    save_jobs(jobs)

    return job


def get_job(job_id: str) -> Optional[PipelineJob]:
    jobs = load_jobs()
    return jobs.get(job_id)


def update_job(job: PipelineJob) -> None:
    jobs = load_jobs()
    jobs[job.id] = job
    save_jobs(jobs)


__all__ = [
    "PipelineJobStatus",
    "PipelineJob",
    "load_jobs",
    "save_jobs",
    "create_job",
    "get_job",
    "update_job",
]
