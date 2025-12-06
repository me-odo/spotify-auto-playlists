"""Public façade for the app.pipeline package.

This module exposes the high-level pipeline orchestration API, including cache
helpers, enrichment, classification, playlist building, diffing, application,
and job runner entrypoints. Other packages should import pipeline behaviour
from this façade instead of the internal pipeline submodules.
"""

from .cache_manager import (
    load_tracks_cache,
    save_classification_cache,
    save_tracks_cache,
)
from .classifier import classify_tracks_rule_based, load_classification_cache
from .external_features import (
    enrich_tracks_with_external_features,
    load_external_features_cache,
)
from .jobs_runner import run_step_for_job
from .orchestration import PipelineOptions, run_pipeline, run_pipeline_entrypoint
from .playlist_manager import (
    apply_target_playlists,
    build_rule_based_playlists,
    build_target_playlists,
    preview_playlist_diffs,
    sync_playlists,
)
from .providers import (
    FEATURE_PROVIDERS,
    FeatureProvider,
    get_feature_provider,
    list_feature_providers,
)
from .reporting import write_unmatched_report
from .rules_engine import build_enrichment_view, matches_rules
from .sources_manager import fetch_tracks_for_source

__all__ = [
    "PipelineOptions",
    "run_pipeline",
    "run_pipeline_entrypoint",
    "build_target_playlists",
    "sync_playlists",
    "preview_playlist_diffs",
    "apply_target_playlists",
    "build_rule_based_playlists",
    "classify_tracks_rule_based",
    "enrich_tracks_with_external_features",
    "load_classification_cache",
    "load_external_features_cache",
    "load_tracks_cache",
    "save_classification_cache",
    "save_tracks_cache",
    "write_unmatched_report",
    "run_step_for_job",
    "build_enrichment_view",
    "matches_rules",
    "fetch_tracks_for_source",
    "FeatureProvider",
    "FEATURE_PROVIDERS",
    "get_feature_provider",
    "list_feature_providers",
]
