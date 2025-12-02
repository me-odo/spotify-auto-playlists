"""Public façade for the app.core package.

This module exposes logging helpers, filesystem utilities, and base models
that are safe to import from other packages. Callers should import these
cross-cutting concerns from this façade instead of the internal submodules.
"""

from .fs_utils import ensure_dir, ensure_parent_dir, read_json, write_json
from .logging_config import configure_logging
from .logging_utils import (
    log_error,
    log_info,
    log_progress,
    log_section,
    log_step,
    log_success,
    log_warning,
)
from .models import Classification, Track, TrackEnrichment
from .rules import (
    ConditionOperator,
    LogicalOperator,
    PlaylistRuleSet,
    RuleCondition,
    RuleGroup,
)

__all__ = [
    "configure_logging",
    "log_section",
    "log_info",
    "log_step",
    "log_success",
    "log_warning",
    "log_error",
    "log_progress",
    "ensure_parent_dir",
    "ensure_dir",
    "write_json",
    "read_json",
    "Track",
    "Classification",
    "TrackEnrichment",
    "ConditionOperator",
    "LogicalOperator",
    "RuleCondition",
    "RuleGroup",
    "PlaylistRuleSet",
]
