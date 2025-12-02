from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.data import (
    PipelineJob as DataPipelineJob,
    PipelineJobStatus as DataPipelineJobStatus,
    create_job,
    get_job,
    load_jobs,
    update_job,
)
from app.pipeline import run_step_for_job
from app.spotify import TrackSource, TrackSourceType

from .schemas import PipelineJobListResponse, PipelineJobResponse, PipelineJobStatus

router = APIRouter()

_VALID_STEPS = {"tracks", "external", "classify", "build", "diff", "apply"}


def _job_to_response(job: DataPipelineJob) -> PipelineJobResponse:
    return PipelineJobResponse(
        id=job.id,
        step=job.step,
        status=PipelineJobStatus(job.status.value),
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        progress=job.progress,
        message=job.message,
        payload=job.payload,
        metadata=job.metadata,
    )


def _run_job_background(job_id: str) -> None:
    job = get_job(job_id)
    if job is None:
        return

    job.status = DataPipelineJobStatus.RUNNING
    job.started_at = datetime.now(timezone.utc)
    job.progress = 0.0
    job.message = None
    update_job(job)

    try:
        payload = run_step_for_job(job.step)
        job.payload = payload
        job.progress = 1.0
        job.status = DataPipelineJobStatus.DONE
        job.finished_at = datetime.now(timezone.utc)
    except Exception as exc:  # noqa: BLE001
        job.status = DataPipelineJobStatus.ERROR
        job.message = str(exc)
        job.finished_at = datetime.now(timezone.utc)
    finally:
        update_job(job)


@router.post("/{step}/run-async", response_model=PipelineJobResponse)
def run_step_async(step: str, background_tasks: BackgroundTasks) -> PipelineJobResponse:
    """
    Create a new pipeline job for the given step and run it in the background.
    """
    if step not in _VALID_STEPS:
        raise HTTPException(
            status_code=400, detail=f"Unsupported pipeline step: {step!r}"
        )

    metadata = None
    if step == "tracks":
        # For the tracks step, record the logical source of tracks in job metadata.
        source = TrackSource(
            source_type=TrackSourceType.LIKED,
            source_id=None,
            label="Liked tracks",
        )
        metadata = {
            "source_type": source.source_type.value,
            "source_id": source.source_id,
            "source_label": source.label,
        }

    job = create_job(step=step, metadata=metadata)
    background_tasks.add_task(_run_job_background, job.id)
    return _job_to_response(job)


@router.get("/jobs", response_model=PipelineJobListResponse)
def list_jobs() -> PipelineJobListResponse:
    """
    List all known pipeline jobs.
    """
    jobs_dict = load_jobs()
    jobs_sorted: List[DataPipelineJob] = sorted(
        jobs_dict.values(), key=lambda j: j.created_at
    )
    return PipelineJobListResponse(jobs=[_job_to_response(j) for j in jobs_sorted])


@router.get("/jobs/{job_id}", response_model=PipelineJobResponse)
def get_job_detail(job_id: str) -> PipelineJobResponse:
    """
    Retrieve a single pipeline job by id.
    """

    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return _job_to_response(job)
