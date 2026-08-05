"""Parameter validators for the MiniMax video generation skill.

Implements rules from the official MiniMax v1 / v2 video generation docs:

- v1 (async task flow): https://platform.minimaxi.com/docs/guides/video-generation
- v2 (multimodal content[]):  same guide page; H3 model.

Two flavors of payload are supported:

- ``payload_version="v1"`` -> flat ``{model, prompt, duration, resolution}``
  with optional ``prompt_optimizer``, ``fast_pretreatment``, ``callback_url``,
  ``first_frame_image``, ``last_frame_image``, ``reference_image``.
- ``payload_version="v2"`` -> ``{model, content:[...], duration, resolution,
  ratio}`` with text + image_url / video_url / audio_url entries.

The two validators share the helper utilities here so the CLI and client
do not duplicate work.
"""

from __future__ import annotations

import re
from typing import Iterable, Optional

# -- v1 model allowlist --------------------------------------------------------

# From https://platform.minimax.io/docs/api-reference/video-generation-t2v
SUPPORTED_MODELS = (
    "MiniMax-Hailuo-2.3",
    "MiniMax-Hailuo-02",
    "T2V-01-Director",
    "T2V-01",
    "MiniMax-H3",  # new H3 (v2 endpoint with multimodal content[])
)

# Per the v1 reference table: v1 only takes a subset.
V1_MODELS = ("MiniMax-Hailuo-2.3", "MiniMax-Hailuo-02", "T2V-01-Director", "T2V-01")
V2_MODELS = ("MiniMax-H3",)

SUPPORTED_RESOLUTIONS = ("720P", "768P", "1080P", "2K")
V1_RESOLUTIONS = ("720P", "768P", "1080P")
V2_RESOLUTIONS = ("2K",)
SUPPORTED_RATIOS = ("16:9", "9:16", "1:1", "4:3", "3:4", "21:9", "adaptive")

MIN_DURATION = 4
MAX_DURATION = 15
DEFAULT_DURATION = 6
MAX_PROMPT_LENGTH = 2000  # v1 limit; v2 raises this to 7000
V2_MAX_PROMPT_LENGTH = 7000

# 15 official camera commands per the docs.
CAMERA_COMMANDS = {
    "Truck left", "Truck right",
    "Pan left", "Pan right",
    "Push in", "Pull out",
    "Pedestal up", "Pedestal down",
    "Tilt up", "Tilt down",
    "Zoom in", "Zoom out",
    "Shake", "Tracking shot", "Static shot",
}
CAMERA_PATTERN = re.compile(r"\[[^\]]*\]")

SUPPORTED_STATUSES = (
    "Preparing",
    "Queueing",
    "Processing",
    "Success",
    "Fail",
)
TERMINAL_SUCCESS = "Success"
TERMINAL_FAILURE = ("Fail",)

INTERNATIONAL_HOST_MARKERS = ("minimax.io",)


# -- Errors --------------------------------------------------------------------


class ValidationError(ValueError):
    """Raised when a request parameter fails validation."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(f"{field}: {message}")
        self.field = field
        self.message = message


# -- Helpers -------------------------------------------------------------------


def normalize_ratio(value: Optional[str]) -> Optional[str]:
    """Return the canonical ratio string, or ``None`` if not provided."""
    if value is None:
        return None
    candidate = value.strip().lower().replace("x", ":").replace("／", ":")
    candidate = re.sub(r"\s+", "", candidate)
    if candidate in SUPPORTED_RATIOS:
        return candidate
    # Tolerate "16,9" or "16 9" — only when the stripped value is purely
    # digits/commas/spaces/colons/x. We must NOT drop letters because some
    # supported values ("adaptive") are alphabetic.
    if re.match(r"^[\d:,x]+$", candidate):
        candidate = candidate.replace(",", ":").replace("x", ":")
        candidate = re.sub(r"[^0-9:]", "", candidate)
    if candidate in SUPPORTED_RATIOS:
        return candidate
    raise ValidationError(
        "ratio",
        f"unsupported value {value!r}; expected one of {', '.join(SUPPORTED_RATIOS)}",
    )


def validate_prompt(prompt: Optional[str], *, max_length: int = MAX_PROMPT_LENGTH) -> str:
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValidationError("prompt", "must be a non-empty string")
    if len(prompt) > max_length:
        raise ValidationError(
            "prompt",
            f"must be ≤ {max_length} characters (got {len(prompt)})",
        )
    return prompt


def validate_model(model: str, base_url: str, payload_version: str) -> str:
    if model not in SUPPORTED_MODELS:
        raise ValidationError(
            "model",
            f"unsupported value {model!r}; expected one of {', '.join(SUPPORTED_MODELS)}",
        )
    if payload_version == "v1" and model not in V1_MODELS:
        raise ValidationError(
            "model",
            f"{model!r} is only available on the v2 endpoint; use payload_version='v2'",
        )
    if payload_version == "v2" and model not in V2_MODELS:
        raise ValidationError(
            "model",
            f"{model!r} is not supported on the v2 endpoint (v2 is MiniMax-H3 only)",
        )
    is_international = any(marker in base_url.lower() for marker in INTERNATIONAL_HOST_MARKERS)
    # All current models work on both endpoints; if the official docs ever add
    # China-only models, gate them here.
    del is_international
    return model


def validate_duration(
    duration: Optional[int], *, resolution: str, model: str, payload_version: str
) -> int:
    if duration is None:
        return DEFAULT_DURATION
    if not isinstance(duration, int) or isinstance(duration, bool):
        raise ValidationError("duration", "must be an integer")
    if duration < MIN_DURATION or duration > MAX_DURATION:
        raise ValidationError(
            "duration", f"must be in [{MIN_DURATION}, {MAX_DURATION}] seconds"
        )
    # Per v1 docs table: 10s is only allowed for Hailuo-2.3 / Hailuo-02 at 768P/1080P.
    if duration == 10 and payload_version == "v1":
        if model not in ("MiniMax-Hailuo-2.3", "MiniMax-Hailuo-02"):
            raise ValidationError(
                "duration",
                f"10s is only supported by MiniMax-Hailuo-2.3 / MiniMax-Hailuo-02 (model={model!r})",
            )
        if resolution not in ("768P", "1080P"):
            raise ValidationError(
                "duration",
                f"10s requires resolution in ('768P', '1080P') (got {resolution!r})",
            )
    return duration


def validate_resolution(value: Optional[str], *, payload_version: str) -> str:
    allowed = V2_RESOLUTIONS if payload_version == "v2" else V1_RESOLUTIONS
    default = "2K" if payload_version == "v2" else "768P"
    if value is None:
        return default
    if value not in allowed:
        raise ValidationError(
            "resolution",
            f"unsupported value {value!r} for {payload_version}; expected one of {', '.join(allowed)}",
        )
    return value


def validate_payload_version(value: Optional[str]) -> str:
    if value is None:
        return "v1"
    candidate = value.strip().lower()
    if candidate not in ("v1", "v2"):
        raise ValidationError(
            "payload_version",
            "must be 'v1' (async task flow) or 'v2' (multimodal content[])",
        )
    return candidate


def validate_url(value: Optional[str], field: str) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(field, "must be a non-empty URL string")
    if not (value.startswith("http://") or value.startswith("https://")):
        raise ValidationError(field, "must be an http(s) URL")
    return value


def validate_request(
    *,
    prompt: Optional[str],
    model: str,
    base_url: str,
    duration: Optional[int] = None,
    resolution: Optional[str] = None,
    ratio: Optional[str] = None,
    payload_version: Optional[str] = None,
    prompt_optimizer: Optional[bool] = None,
    fast_pretreatment: Optional[bool] = None,
    callback_url: Optional[str] = None,
    first_frame_image: Optional[str] = None,
    last_frame_image: Optional[str] = None,
    reference_image: Optional[str] = None,
) -> dict:
    """Validate the full request and return the cleaned payload.

    Returns a dict in the shape the chosen API version expects.
    """
    version = validate_payload_version(payload_version)
    cleaned_model = validate_model(model, base_url, version)
    resolution = validate_resolution(resolution, payload_version=version)
    duration = validate_duration(
        duration, resolution=resolution, model=cleaned_model, payload_version=version
    )

    # v2 has a 7000-char budget; v1 stays at 2000.
    max_prompt = V2_MAX_PROMPT_LENGTH if version == "v2" else MAX_PROMPT_LENGTH
    cleaned_prompt = validate_prompt(prompt, max_length=max_prompt)

    cleaned: dict = {
        "model": cleaned_model,
        "prompt": cleaned_prompt,
        "duration": duration,
        "resolution": resolution,
        "payload_version": version,
    }

    if version == "v1":
        # Flat v1 payload.
        if prompt_optimizer is not None:
            cleaned["prompt_optimizer"] = bool(prompt_optimizer)
        if fast_pretreatment is not None:
            # Fast pretreatment only meaningful for Hailuo-2.3 / Hailuo-02.
            if cleaned_model not in ("MiniMax-Hailuo-2.3", "MiniMax-Hailuo-02"):
                raise ValidationError(
                    "fast_pretreatment",
                    f"only applies to MiniMax-Hailuo-2.3 / MiniMax-Hailuo-02 (model={cleaned_model!r})",
                )
            cleaned["fast_pretreatment"] = bool(fast_pretreatment)
        if callback_url is not None:
            cleaned["callback_url"] = validate_url(callback_url, "callback_url")
        # Reference frames aren't part of v1's flat payload — those go through
        # v2 multimodal content[]. We accept and ignore them with a warning
        # unless the caller explicitly chooses v2.
        for name, value in (
            ("first_frame_image", first_frame_image),
            ("last_frame_image", last_frame_image),
            ("reference_image", reference_image),
        ):
            if value is not None:
                raise ValidationError(
                    name,
                    f"{name!r} requires payload_version='v2' (multimodal content[])",
                )
        # v1 doesn't use ratio; silently drop.
        return cleaned

    # v2 multimodal payload.
    ratio_norm = normalize_ratio(ratio)
    if ratio_norm is None:
        raise ValidationError(
            "ratio",
            "v2 requests require an explicit ratio (use 'adaptive' if unsure)",
        )
    if ratio_norm == "adaptive" and not (first_frame_image or last_frame_image or reference_image):
        # t2va (text-to-video) requires an explicit non-adaptive ratio per docs.
        raise ValidationError(
            "ratio",
            "for text-to-video (v2 t2va) ratio is required and cannot be 'adaptive'",
        )
    cleaned["ratio"] = ratio_norm

    content: list[dict] = [{"type": "text", "text": cleaned_prompt}]
    if first_frame_image is not None:
        url = validate_url(first_frame_image, "first_frame_image")
        content.append(
            {"type": "image_url", "image_url": {"url": url}, "role": "first_frame"}
        )
    if last_frame_image is not None:
        url = validate_url(last_frame_image, "last_frame_image")
        content.append(
            {"type": "image_url", "image_url": {"url": url}, "role": "last_frame"}
        )
    if reference_image is not None:
        url = validate_url(reference_image, "reference_image")
        content.append(
            {"type": "image_url", "image_url": {"url": url}, "role": "reference_image"}
        )
    cleaned["content"] = content
    return cleaned


def supported_models() -> Iterable[str]:
    return SUPPORTED_MODELS


def supported_resolutions() -> Iterable[str]:
    return SUPPORTED_RESOLUTIONS


def supported_ratios() -> Iterable[str]:
    return SUPPORTED_RATIOS


def supported_statuses() -> Iterable[str]:
    return SUPPORTED_STATUSES