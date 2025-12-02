"""Public façade for the app.data package.

This module exposes cache loaders/savers and pipeline job persistence helpers
that are safe to import from other packages. Callers should use this façade
instead of importing from the internal cache or jobs modules directly.
"""

from .cache import (
    load_classification_cache,
    load_external_features_cache,
    load_tracks_cache,
    save_classification_cache,
    save_external_features_cache,
    save_tracks_cache,
)
from .enrichments import load_enrichments_cache, save_enrichments_cache
from .jobs import (
    PipelineJob,
    PipelineJobStatus,
    create_job,
    get_job,
    load_jobs,
    save_jobs,
    update_job,
)
from .repositories import ClassificationRepository, TracksRepository
from .rules import load_rules, save_rules

__all__ = [
    "load_tracks_cache",
    "save_tracks_cache",
    "load_external_features_cache",
    "save_external_features_cache",
    "load_classification_cache",
    "save_classification_cache",
    "load_enrichments_cache",
    "save_enrichments_cache",
    "load_rules",
    "save_rules",
    "PipelineJob",
    "PipelineJobStatus",
    "create_job",
    "get_job",
    "load_jobs",
    "save_jobs",
    "update_job",
    "TracksRepository",
    "ClassificationRepository",
]
