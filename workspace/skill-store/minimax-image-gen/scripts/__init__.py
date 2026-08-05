"""MiniMax image generation skill scripts.

Re-exports the public surface so callers can do
``from workspace.skills.minimax_image_gen.scripts import ImageGenerationClient``.
"""

from .image_client import (
    GenerationRequest,
    GenerationResult,
    ImageGenerationClient,
    ImageGenError,
)
from .validators import (
    ValidationError,
    normalize_aspect_ratio,
    validate_model,
    validate_prompt,
    validate_request,
)

__all__ = [
    "GenerationRequest",
    "GenerationResult",
    "ImageGenerationClient",
    "ImageGenError",
    "ValidationError",
    "normalize_aspect_ratio",
    "validate_model",
    "validate_prompt",
    "validate_request",
]