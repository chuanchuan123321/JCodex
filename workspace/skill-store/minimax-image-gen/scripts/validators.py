"""Parameter validators for the MiniMax image generation skill.

Centralizes the rules from the official docs so the CLI and library share
the same checks.

References:
- https://platform.minimaxi.com/docs/api-reference/image-generation-t2i
- https://platform.minimax.io/docs/api-reference/image-generation-t2i
"""

from __future__ import annotations

import re
from typing import Iterable, Optional

# -- Enumerations --------------------------------------------------------------

SUPPORTED_MODELS = ("image-01", "image-01-live")
CHINA_ONLY_MODELS = ("image-01-live",)
INTERNATIONAL_HOST_MARKERS = ("minimax.io",)

SUPPORTED_ASPECT_RATIOS = (
    "1:1",
    "16:9",
    "4:3",
    "3:2",
    "2:3",
    "3:4",
    "9:16",
    "21:9",
)

# 21:9 is image-01 only per the China docs.
RATIO_21_9 = "21:9"

SUPPORTED_RESPONSE_FORMATS = ("url", "base64")
DEFAULT_RESPONSE_FORMAT = "url"

MAX_PROMPT_LENGTH = 1500
MIN_N = 1
MAX_N = 9
DEFAULT_N = 1

MIN_DIMENSION = 512
MAX_DIMENSION = 2048

# -- Errors --------------------------------------------------------------------


class ValidationError(ValueError):
    """Raised when a request parameter fails validation."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(f"{field}: {message}")
        self.field = field
        self.message = message


# -- Helpers -------------------------------------------------------------------


def normalize_aspect_ratio(value: Optional[str]) -> Optional[str]:
    """Return the canonical aspect-ratio string, or ``None`` if not provided."""
    if value is None:
        return None
    candidate = value.strip().lower().replace("x", ":").replace("／", ":")
    candidate = re.sub(r"\s+", "", candidate)
    if ":" not in candidate:
        # Tolerate "16,9" or "16 9".
        candidate = candidate.replace(",", ":")
        candidate = re.sub(r"[^0-9:]", "", candidate)
    if candidate in SUPPORTED_ASPECT_RATIOS:
        return candidate
    raise ValidationError(
        "aspect_ratio",
        f"unsupported value {value!r}; expected one of {', '.join(SUPPORTED_ASPECT_RATIOS)}",
    )


def validate_model(model: str, base_url: str) -> str:
    """Validate ``model`` against the endpoint's allowlist.

    ``image-01-live`` is rejected when ``base_url`` points at the
    international endpoint.
    """
    if model not in SUPPORTED_MODELS:
        raise ValidationError(
            "model",
            f"unsupported value {model!r}; expected one of {', '.join(SUPPORTED_MODELS)}",
        )
    is_international = any(marker in base_url.lower() for marker in INTERNATIONAL_HOST_MARKERS)
    if is_international and model in CHINA_ONLY_MODELS:
        raise ValidationError(
            "model",
            f"{model!r} is only available on the China endpoint ({base_url} looks international)",
        )
    return model


def validate_prompt(prompt: Optional[str]) -> str:
    """Validate that ``prompt`` is a non-empty string ≤ 1500 chars."""
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValidationError("prompt", "must be a non-empty string")
    if len(prompt) > MAX_PROMPT_LENGTH:
        raise ValidationError(
            "prompt",
            f"must be ≤ {MAX_PROMPT_LENGTH} characters (got {len(prompt)})",
        )
    return prompt


def validate_n(n: Optional[int]) -> int:
    """Validate the ``n`` (image count) parameter."""
    if n is None:
        return DEFAULT_N
    if not isinstance(n, int) or isinstance(n, bool):
        raise ValidationError("n", "must be an integer")
    if n < MIN_N or n > MAX_N:
        raise ValidationError("n", f"must be in [{MIN_N}, {MAX_N}]")
    return n


def validate_response_format(value: Optional[str]) -> str:
    if value is None:
        return DEFAULT_RESPONSE_FORMAT
    candidate = value.strip().lower()
    if candidate not in SUPPORTED_RESPONSE_FORMATS:
        raise ValidationError(
            "response_format",
            f"unsupported value {value!r}; expected one of {', '.join(SUPPORTED_RESPONSE_FORMATS)}",
        )
    return candidate


def validate_dimensions(
    width: Optional[int],
    height: Optional[int],
    model: str,
) -> tuple[Optional[int], Optional[int]]:
    """Validate width/height per the official constraints (image-01 only)."""
    if width is None and height is None:
        return None, None
    if model not in ("image-01",):
        raise ValidationError(
            "width/height",
            f"only supported on image-01 (current model: {model!r})",
        )
    for name, value in (("width", width), ("height", height)):
        if value is None:
            raise ValidationError(
                name,
                "must be provided together with the other dimension",
            )
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValidationError(name, "must be an integer")
        if value < MIN_DIMENSION or value > MAX_DIMENSION:
            raise ValidationError(
                name, f"must be in [{MIN_DIMENSION}, {MAX_DIMENSION}]"
            )
        if value % 8 != 0:
            raise ValidationError(name, "must be a multiple of 8")
    return width, height


def validate_reference_url(url: Optional[str]) -> Optional[str]:
    if url is None:
        return None
    if not isinstance(url, str) or not url.strip():
        raise ValidationError("reference_url", "must be a non-empty URL string")
    if not (url.startswith("http://") or url.startswith("https://")):
        raise ValidationError(
            "reference_url", "must be an http(s) URL (the API requires a URL)"
        )
    return url


def validate_request(
    *,
    prompt: Optional[str],
    model: str,
    base_url: str,
    aspect_ratio: Optional[str] = None,
    n: Optional[int] = None,
    response_format: Optional[str] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    reference_url: Optional[str] = None,
    subject_type: str = "character",
    prompt_optimizer: bool = False,
    aigc_watermark: bool = False,
    seed: Optional[int] = None,
) -> dict:
    """Validate a full request and return the cleaned payload.

    Raises :class:`ValidationError` (or its first occurrence) on bad input.
    """
    cleaned: dict = {}
    cleaned["model"] = validate_model(model, base_url)
    cleaned["prompt"] = validate_prompt(prompt)
    cleaned["n"] = validate_n(n)
    cleaned["response_format"] = validate_response_format(response_format)

    normalized_ratio = normalize_aspect_ratio(aspect_ratio)
    if normalized_ratio:
        cleaned["aspect_ratio"] = normalized_ratio
        if (
            normalized_ratio == RATIO_21_9
            and cleaned["model"] in CHINA_ONLY_MODELS + ("image-01",)
        ):
            # image-01 supports 21:9 only per docs; keep the field.
            pass

    w, h = validate_dimensions(width, height, cleaned["model"])
    if w is not None and h is not None:
        cleaned["width"] = w
        cleaned["height"] = h

    if reference_url is not None:
        url = validate_reference_url(reference_url)
        cleaned["subject_reference"] = [
            {"type": subject_type, "image_file": url}
        ]

    if seed is not None:
        if not isinstance(seed, int) or isinstance(seed, bool):
            raise ValidationError("seed", "must be an integer")
        cleaned["seed"] = seed

    cleaned["prompt_optimizer"] = bool(prompt_optimizer)
    cleaned["aigc_watermark"] = bool(aigc_watermark)
    return cleaned


def supported_models() -> Iterable[str]:
    return SUPPORTED_MODELS


def supported_aspect_ratios() -> Iterable[str]:
    return SUPPORTED_ASPECT_RATIOS