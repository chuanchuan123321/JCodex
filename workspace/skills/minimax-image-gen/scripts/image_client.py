"""Python client for the MiniMax image generation API.

A thin wrapper around ``POST {API_BASE_URL}/v1/image_generation`` that:
- validates parameters via :mod:`validators`
- loads config from environment / ``.env``
- surfaces structured results so the CLI (and other skills) can pick
  them up without re-parsing JSON
- downloads URL results to disk in one call

Example
-------
>>> client = ImageGenerationClient.from_env()
>>> result = client.generate_text_to_image(
...     prompt="Studio shot of a vintage typewriter",
...     aspect_ratio="16:9",
... )
>>> saved = client.download(result, output_dir="./out")
>>> print(saved)
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

import requests

try:  # package import (preferred)
    from .validators import (
        DEFAULT_RESPONSE_FORMAT,
        validate_request,
    )
except ImportError:  # script-mode import (scripts/ on sys.path)
    from validators import (  # type: ignore
        DEFAULT_RESPONSE_FORMAT,
        validate_request,
    )

DEFAULT_BASE_URL = "https://api.minimaxi.com"
DEFAULT_MODEL = "image-01"
DEFAULT_HTTP_TIMEOUT = 120
DEFAULT_DOWNLOAD_TIMEOUT = 60
USER_AGENT = "minimax-image-gen-skill/1.0"


# -- Exceptions ----------------------------------------------------------------


class ImageGenError(RuntimeError):
    """Base error for image generation failures."""

    def __init__(self, message: str, *, payload: Optional[dict] = None) -> None:
        super().__init__(message)
        self.payload = payload or {}


class ConfigError(ImageGenError):
    """Raised when configuration (env, .env) is missing or invalid."""


class TransportError(ImageGenError):
    """Raised on network/timeout failures."""


class ApiError(ImageGenError):
    """Raised when the API responds with a non-success base_resp."""


# -- Data classes --------------------------------------------------------------


@dataclass
class GenerationRequest:
    """A cleaned-up image generation request."""

    prompt: str
    aspect_ratio: Optional[str] = None
    n: int = 1
    response_format: str = DEFAULT_RESPONSE_FORMAT
    width: Optional[int] = None
    height: Optional[int] = None
    reference_url: Optional[str] = None
    subject_type: str = "character"
    prompt_optimizer: bool = False
    aigc_watermark: bool = False
    seed: Optional[int] = None
    model: Optional[str] = None  # defaults to env IMAGE_MODEL or image-01
    extra: dict[str, Any] = field(default_factory=dict)

    def to_payload(self, *, default_model: str, base_url: str) -> dict[str, Any]:
        model = self.model or default_model
        cleaned = validate_request(
            prompt=self.prompt,
            model=model,
            base_url=base_url,
            aspect_ratio=self.aspect_ratio,
            n=self.n,
            response_format=self.response_format,
            width=self.width,
            height=self.height,
            reference_url=self.reference_url,
            subject_type=self.subject_type,
            prompt_optimizer=self.prompt_optimizer,
            aigc_watermark=self.aigc_watermark,
            seed=self.seed,
        )
        cleaned.update(self.extra)
        return cleaned


@dataclass
class GenerationResult:
    """A successful response from the image generation API."""

    task_id: str
    model: str
    response_format: str
    image_urls: list[str] = field(default_factory=list)
    image_bytes: list[bytes] = field(default_factory=list)
    failed_count: int = 0
    success_count: int = 0
    base_resp: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def images(self) -> list[bytes | str]:
        """Return whichever representation the server actually returned."""
        if self.image_bytes:
            return list(self.image_bytes)
        return list(self.image_urls)

    @property
    def ok(self) -> bool:
        return self.base_resp.get("status_code", 0) == 0


# -- Env loading ---------------------------------------------------------------


def _load_dotenv(path: Path) -> None:
    """Populate ``os.environ`` from a minimal ``.env`` file (no extra deps)."""
    if not path.exists() or not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _resolve_base_url(explicit: Optional[str] = None) -> str:
    url = explicit or os.environ.get("API_BASE_URL") or DEFAULT_BASE_URL
    return url.rstrip("/")


def _resolve_model(explicit: Optional[str] = None) -> str:
    return explicit or os.environ.get("IMAGE_MODEL") or DEFAULT_MODEL


def _resolve_api_key(explicit: Optional[str] = None) -> str:
    key = explicit or os.environ.get("API_KEY")
    if not key:
        raise ConfigError(
            "API_KEY is not set. Add it to your project's .env file "
            "so the skill uses the same key as the rest of the project."
        )
    return key


# -- Client --------------------------------------------------------------------


class ImageGenerationClient:
    """Synchronous client for the MiniMax image_generation endpoint."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        http_timeout: float = DEFAULT_HTTP_TIMEOUT,
        download_timeout: float = DEFAULT_DOWNLOAD_TIMEOUT,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.http_timeout = http_timeout
        self.download_timeout = download_timeout
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", USER_AGENT)

    # -- factories ----------------------------------------------------------

    @classmethod
    def from_env(
        cls,
        *,
        dotenv_path: Optional[Path | str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> "ImageGenerationClient":
        """Build a client from environment variables.

        ``dotenv_path`` defaults to ``<cwd>/.env``; if present, values are
        loaded into ``os.environ`` first (only for keys that are unset).

        Resolution order for the model: explicit ``model`` argument →
        ``IMAGE_MODEL`` env var → hard-coded ``DEFAULT_MODEL`` (``image-01``).
        ``IMAGE_MODEL`` is intentionally optional: the skill ships with a
        default model and a default base URL so the loader never blocks on
        missing env keys for those.
        """
        if dotenv_path is None:
            dotenv_path = Path.cwd() / ".env"
        _load_dotenv(Path(dotenv_path))

        return cls(
            api_key=_resolve_api_key(api_key),
            base_url=_resolve_base_url(base_url),
            model=_resolve_model(model),
        )

    # -- helpers -------------------------------------------------------------

    @property
    def endpoint(self) -> str:
        return f"{self.base_url}/v1/image_generation"

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self.session.post(
                self.endpoint,
                json=payload,
                headers=self._auth_headers(),
                timeout=self.http_timeout,
            )
        except requests.RequestException as exc:
            raise TransportError(
                f"network error talking to {self.endpoint}: {exc}"
            ) from exc

        # Try to parse JSON even on 4xx/5xx so we can surface base_resp.
        try:
            body = response.json()
        except ValueError:
            body = {"raw_text": response.text}

        if response.status_code >= 400:
            status_msg = (
                body.get("base_resp", {}).get("status_msg")
                if isinstance(body, dict)
                else None
            ) or f"HTTP {response.status_code}"
            raise ApiError(
                f"image_generation failed: {status_msg}",
                payload=body if isinstance(body, dict) else {},
            )

        return body

    # -- public API ----------------------------------------------------------

    def generate(self, request: GenerationRequest) -> GenerationResult:
        """Submit a :class:`GenerationRequest` and return the parsed result."""
        payload = request.to_payload(default_model=self.model, base_url=self.base_url)
        body = self._post(payload)

        base_resp = body.get("base_resp", {}) if isinstance(body, dict) else {}
        if base_resp.get("status_code", 0) != 0:
            raise ApiError(
                f"image_generation returned status_code="
                f"{base_resp.get('status_code')!r}: {base_resp.get('status_msg')}",
                payload=body if isinstance(body, dict) else {},
            )

        data = body.get("data", {}) if isinstance(body, dict) else {}
        meta = body.get("metadata", {}) if isinstance(body, dict) else {}

        urls = list(data.get("image_urls", []) or [])
        raw_b64 = list(data.get("image_base64", []) or [])
        bytes_list = [base64.b64decode(chunk) for chunk in raw_b64]

        return GenerationResult(
            task_id=body.get("id", "") if isinstance(body, dict) else "",
            model=payload["model"],
            response_format=payload["response_format"],
            image_urls=urls,
            image_bytes=bytes_list,
            failed_count=int(meta.get("failed_count", 0) or 0),
            success_count=int(meta.get("success_count", len(bytes_list) or len(urls)) or 0),
            base_resp=base_resp,
            raw=body if isinstance(body, dict) else {},
        )

    def generate_text_to_image(
        self,
        *,
        prompt: str,
        aspect_ratio: Optional[str] = None,
        n: int = 1,
        response_format: str = DEFAULT_RESPONSE_FORMAT,
        width: Optional[int] = None,
        height: Optional[int] = None,
        prompt_optimizer: bool = False,
        aigc_watermark: bool = False,
        seed: Optional[int] = None,
        model: Optional[str] = None,
    ) -> GenerationResult:
        """Convenience wrapper for the common text-to-image call."""
        return self.generate(
            GenerationRequest(
                prompt=prompt,
                aspect_ratio=aspect_ratio,
                n=n,
                response_format=response_format,
                width=width,
                height=height,
                prompt_optimizer=prompt_optimizer,
                aigc_watermark=aigc_watermark,
                seed=seed,
                model=model,
            )
        )

    def generate_with_reference(
        self,
        *,
        prompt: str,
        reference_url: str,
        aspect_ratio: Optional[str] = None,
        n: int = 1,
        response_format: str = DEFAULT_RESPONSE_FORMAT,
        prompt_optimizer: bool = False,
        aigc_watermark: bool = False,
        seed: Optional[int] = None,
        subject_type: str = "character",
        model: Optional[str] = None,
    ) -> GenerationResult:
        """Convenience wrapper for subject-reference image-to-image."""
        return self.generate(
            GenerationRequest(
                prompt=prompt,
                aspect_ratio=aspect_ratio,
                n=n,
                response_format=response_format,
                reference_url=reference_url,
                subject_type=subject_type,
                prompt_optimizer=prompt_optimizer,
                aigc_watermark=aigc_watermark,
                seed=seed,
                model=model,
            )
        )

    # -- downloads -----------------------------------------------------------

    def download(
        self,
        result: GenerationResult,
        *,
        output_dir: Path | str,
        filename_prefix: str = "image",
        overwrite: bool = True,
    ) -> list[str]:
        """Download URL-based images into ``output_dir`` and return saved paths.

        For ``response_format=base64`` results the bytes are written under
        the same naming scheme, so callers can treat the return value uniformly.
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        saved: list[str] = []

        if result.image_urls:
            for index, url in enumerate(result.image_urls):
                target = output_path / self._filename(filename_prefix, index, url)
                if target.exists() and not overwrite:
                    saved.append(str(target))
                    continue
                try:
                    response = self.session.get(url, timeout=self.download_timeout)
                    response.raise_for_status()
                except requests.RequestException as exc:
                    raise TransportError(
                        f"failed to download {url}: {exc}"
                    ) from exc
                target.write_bytes(response.content)
                saved.append(str(target))

        if result.image_bytes:
            for index, data in enumerate(result.image_bytes):
                target = output_path / self._filename(filename_prefix, index, None, ext="jpeg")
                if target.exists() and not overwrite:
                    saved.append(str(target))
                    continue
                target.write_bytes(data)
                saved.append(str(target))

        return saved

    @staticmethod
    def _filename(prefix: str, index: int, url: Optional[str], *, ext: str = "jpeg") -> str:
        suffix_from_url: Optional[str] = None
        if url is not None:
            stripped = url.split("?", 1)[0]
            if "." in stripped.rsplit("/", 1)[-1]:
                suffix_from_url = stripped.rsplit(".", 1)[-1].lower()
        chosen_ext = suffix_from_url if suffix_from_url else ext
        return f"{prefix}-{index:03d}.{chosen_ext}"


# -- Public helpers ------------------------------------------------------------


def quick_generate(
    prompt: str,
    *,
    output: Path | str,
    aspect_ratio: str = "1:1",
    n: int = 1,
    seed: Optional[int] = None,
    prompt_optimizer: bool = False,
) -> list[str]:
    """One-shot helper: generate, download, return file paths."""
    client = ImageGenerationClient.from_env()
    result = client.generate_text_to_image(
        prompt=prompt,
        aspect_ratio=aspect_ratio,
        n=n,
        response_format="url",
        prompt_optimizer=prompt_optimizer,
        seed=seed,
    )
    return client.download(result, output_dir=output, filename_prefix="image")