"""MiniMax video generation skill scripts.

Re-exports the public surface so callers can do
``from workspace.skills.minimax_video_gen.scripts import VideoGenerationClient``.
"""

from .video_client import (
    VideoGenerationClient,
    VideoGenerationRequest,
    VideoGenerationResult,
    VideoTaskStatus,
    VideoGenerationError,
    ConfigError,
    ApiError,
    TransportError,
)
from .validators import (
    ValidationError,
    SUPPORTED_MODELS,
    SUPPORTED_RESOLUTIONS,
    SUPPORTED_RATIOS,
    SUPPORTED_STATUSES,
    validate_request,
    normalize_ratio,
    validate_prompt,
)

__all__ = [
    "VideoGenerationClient",
    "VideoGenerationRequest",
    "VideoGenerationResult",
    "VideoTaskStatus",
    "VideoGenerationError",
    "ConfigError",
    "ApiError",
    "TransportError",
    "ValidationError",
    "SUPPORTED_MODELS",
    "SUPPORTED_RESOLUTIONS",
    "SUPPORTED_RATIOS",
    "SUPPORTED_STATUSES",
    "validate_request",
    "normalize_ratio",
    "validate_prompt",
]