from fastapi import FastAPI

from app.core import configure_logging

from .auth import router as auth_router
from .pipeline import router as pipeline_router

configure_logging()

app = FastAPI(
    title="Spotify Auto-Playlists API",
    version="0.2.0",
    description="Backend API for mood-based Spotify auto playlists.",
)

# Routes regroupées
app.include_router(pipeline_router, tags=["pipeline"])
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(auth_router, prefix="/auth", tags=["auth"])
