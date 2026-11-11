"""Telegram Ads target/placement engine for TMADS."""

from .compatibility import (
    TARGET_TYPE_LABELS_FA,
    default_placement_for_target,
    placement_choices_for_target,
    resolve_api_placement,
    validate_target_placement,
)
from .builders import build_input_target
from .validators import (
    StudioValidationResult,
    validate_studio_config,
    validate_submission_ready,
)

__all__ = [
    "TARGET_TYPE_LABELS_FA",
    "build_input_target",
    "default_placement_for_target",
    "placement_choices_for_target",
    "resolve_api_placement",
    "StudioValidationResult",
    "validate_studio_config",
    "validate_submission_ready",
    "validate_target_placement",
]
