from fastapi import FastAPI

from app.api.auth.routes import router as auth_router
from app.api.data.routes import router as data_router
from app.api.pipeline.classify import router as pipeline_classify_router
from app.api.pipeline.diff import router as pipeline_diff_router
from app.api.pipeline.external import router as pipeline_external_router
from app.api.pipeline.health import router as pipeline_health_router
from app.api.pipeline.jobs import router as jobs_router
from app.api.pipeline.playlists import router as pipeline_playlists_router
from app.api.pipeline.tracks import router as pipeline_tracks_router
from app.core import configure_logging

configure_logging()

app = FastAPI(
    title="Spotify Auto-Playlists API",
    version="0.4.0",
    description="Backend API for mood-based Spotify auto playlists.",
)

# Pipeline routes
app.include_router(pipeline_health_router, prefix="/pipeline", tags=["pipeline"])
app.include_router(pipeline_tracks_router, prefix="/pipeline", tags=["pipeline"])
app.include_router(pipeline_external_router, prefix="/pipeline", tags=["pipeline"])
app.include_router(pipeline_classify_router, prefix="/pipeline", tags=["pipeline"])
app.include_router(pipeline_playlists_router, prefix="/pipeline", tags=["pipeline"])
app.include_router(pipeline_diff_router, prefix="/pipeline", tags=["pipeline"])
app.include_router(jobs_router, prefix="/pipeline", tags=["pipeline-jobs"])

# Data routes
app.include_router(data_router, prefix="/data", tags=["data"])

# Auth routes
app.include_router(auth_router, prefix="/auth", tags=["auth"])
