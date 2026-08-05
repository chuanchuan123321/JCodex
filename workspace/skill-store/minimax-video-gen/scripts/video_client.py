"""Python client for the MiniMax video generation API.

Implements two flows documented at
https://platform.minimaxi.com/docs/guides/video-generation:

v1 (default for legacy models, async task flow):

    POST {API_BASE_URL}/v1/video_generation  -> {task_id, base_resp}
    GET  {API_BASE_URL}/v1/query/video_generation?task_id=...   -> poll status
    GET  {API_BASE_URL}/v1/files/retrieve?file_id=...           -> download URL

v2 (multimodal MiniMax-H3, returns content.url directly):

    POST {API_BASE_URL}/v2/video_generation  -> {task_id, base_resp}
    (still pollable via the same query endpoint or the v2-specific
    ``/v2/query/video_generation/{task_id}`` shown in the guide)

The client encapsulates task creation, polling, status parsing, and
download, so the CLI and other skills don't have to repeat the workflow.

Example
-------
>>> client = VideoGenerationClient.from_env()
>>> task = client.create_text_to_video(
...     prompt="Camera slowly pans across a neon-lit Tokyo alley at night",
...     resolution="768P",
...     duration=6,
... )
>>> result = client.wait_for_completion(task, timeout_s=300)
>>> path = client.download(result, output="./workspace/output/tokyo.mp4")
>>> print(path)
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

import requests

try:  # package import (preferred)
    from .validators import (
        DEFAULT_DURATION,
        SUPPORTED_STATUSES,
        TERMINAL_FAILURE,
        TERMINAL_SUCCESS,
        validate_request,
    )
except ImportError:  # script-mode import (scripts/ on sys.path)
    from validators import (  # type: ignore
        DEFAULT_DURATION,
        SUPPORTED_STATUSES,
        TERMINAL_FAILURE,
        TERMINAL_SUCCESS,
        validate_request,
    )

DEFAULT_MODEL = "MiniMax-Hailuo-2.3"
DEFAULT_HTTP_TIMEOUT = 120
DEFAULT_DOWNLOAD_TIMEOUT = 600
DEFAULT_POLL_INTERVAL = 10
DEFAULT_WAIT_TIMEOUT = 600
USER_AGENT = "minimax-video-gen-skill/1.0"


# -- Exceptions ----------------------------------------------------------------


class VideoGenerationError(RuntimeError):
    """Base error for video generation failures."""

    def __init__(self, message: str, *, payload: Optional[dict] = None) -> None:
        super().__init__(message)
        self.payload = payload or {}


class ConfigError(VideoGenerationError):
    """Raised when configuration (env, .env) is missing or invalid."""


class TransportError(VideoGenerationError):
    """Raised on network/timeout failures."""


class ApiError(VideoGenerationError):
    """Raised when the API responds with an error or terminal failure status."""


class TimeoutError_(VideoGenerationError):
    """Raised when waiting for a task exceeds the configured timeout."""

    def __init__(self, message: str, *, last_status: Optional[dict] = None) -> None:
        super().__init__(message, payload=last_status or {})


# Alias so callers can write ``TimeoutError`` without colliding with builtin.
TimeoutError = TimeoutError_


# -- Data classes --------------------------------------------------------------


@dataclass
class VideoGenerationRequest:
    """A validated video generation request."""

    prompt: str
    duration: int = DEFAULT_DURATION
    resolution: Optional[str] = None  # validator applies v1/v2-aware defaults
    ratio: Optional[str] = None  # required for v2; ignored for v1
    model: Optional[str] = None  # defaults to env VIDEO_MODEL or MiniMax-Hailuo-2.3
    payload_version: str = "v1"
    prompt_optimizer: Optional[bool] = None
    fast_pretreatment: Optional[bool] = None
    callback_url: Optional[str] = None
    first_frame_image: Optional[str] = None
    last_frame_image: Optional[str] = None
    reference_image: Optional[str] = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_payload(self, *, default_model: str, base_url: str) -> dict[str, Any]:
        model = self.model or default_model
        cleaned = validate_request(
            prompt=self.prompt,
            model=model,
            base_url=base_url,
            duration=self.duration,
            resolution=self.resolution,
            ratio=self.ratio,
            payload_version=self.payload_version,
            prompt_optimizer=self.prompt_optimizer,
            fast_pretreatment=self.fast_pretreatment,
            callback_url=self.callback_url,
            first_frame_image=self.first_frame_image,
            last_frame_image=self.last_frame_image,
            reference_image=self.reference_image,
        )
        # v1 wants the raw flat fields, v2 wants content[] + ratio. Both
        # validators already produce the correct shape; we just need to drop
        # our internal bookkeeping key.
        cleaned.pop("payload_version", None)
        cleaned.update(self.extra)
        return cleaned


@dataclass
class VideoTaskStatus:
    """A snapshot of an in-flight or completed task."""

    task_id: str
    status: str
    base_resp: dict[str, Any] = field(default_factory=dict)
    file_id: Optional[str] = None
    video_width: Optional[int] = None
    video_height: Optional[int] = None
    content_url: Optional[str] = None  # populated for v2 success
    error: Optional[dict[str, Any]] = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def is_terminal(self) -> bool:
        return self.status in (TERMINAL_SUCCESS, *TERMINAL_FAILURE)

    @property
    def succeeded(self) -> bool:
        return self.status == TERMINAL_SUCCESS

    @property
    def failed(self) -> bool:
        return self.status in TERMINAL_FAILURE


@dataclass
class VideoGenerationResult:
    """A successful (or definitively failed) generation."""

    task: VideoTaskStatus
    download_url: Optional[str] = None
    file_path: Optional[str] = None
    raw_query: Optional[dict[str, Any]] = None


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
    url = explicit or os.environ.get("API_BASE_URL")
    if not url:
        raise ConfigError(
            "API_BASE_URL is not set. Add it to your project's .env file "
            "so the skill uses the same endpoint as the rest of the project."
        )
    return url.rstrip("/")


def _resolve_model(explicit: Optional[str] = None) -> str:
    return (
        explicit
        or os.environ.get("VIDEO_MODEL")
        or os.environ.get("IMAGE_MODEL")  # fallback only if user wired VIDEO_MODEL later
        or DEFAULT_MODEL
    )


def _resolve_api_key(explicit: Optional[str] = None) -> str:
    key = explicit or os.environ.get("API_KEY")
    if not key:
        raise ConfigError(
            "API_KEY is not set. Add it to your project's .env file "
            "so the skill uses the same key as the rest of the project."
        )
    return key


# -- Client --------------------------------------------------------------------


class VideoGenerationClient:
    """Synchronous client for the MiniMax video_generation endpoints."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str = DEFAULT_MODEL,
        http_timeout: float = DEFAULT_HTTP_TIMEOUT,
        download_timeout: float = DEFAULT_DOWNLOAD_TIMEOUT,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        wait_timeout: float = DEFAULT_WAIT_TIMEOUT,
        session: Optional[requests.Session] = None,
    ) -> None:
        if not base_url:
            raise ConfigError(
                "base_url is required. Read it from the project's API_BASE_URL "
                "environment variable (do not hard-code a default)."
            )
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.http_timeout = http_timeout
        self.download_timeout = download_timeout
        self.poll_interval = poll_interval
        self.wait_timeout = wait_timeout
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", USER_AGENT)

    # -- factories -----------------------------------------------------------

    @classmethod
    def from_env(
        cls,
        *,
        dotenv_path: Optional[Path | str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> "VideoGenerationClient":
        if dotenv_path is None:
            dotenv_path = Path.cwd() / ".env"
        _load_dotenv(Path(dotenv_path))

        return cls(
            api_key=_resolve_api_key(api_key),
            base_url=_resolve_base_url(base_url),
            model=_resolve_model(model),
        )

    # -- helpers --------------------------------------------------------------

    @property
    def create_endpoint(self) -> str:
        return f"{self.base_url}/v1/video_generation"

    @property
    def query_endpoint(self) -> str:
        return f"{self.base_url}/v1/query/video_generation"

    @property
    def files_endpoint(self) -> str:
        return f"{self.base_url}/v1/files/retrieve"

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _post(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self.session.post(
                url,
                json=payload,
                headers=self._auth_headers(),
                timeout=self.http_timeout,
            )
        except requests.RequestException as exc:
            raise TransportError(f"network error POSTing to {url}: {exc}") from exc

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
                f"video_generation POST failed: {status_msg}",
                payload=body if isinstance(body, dict) else {},
            )

        if isinstance(body, dict) and body.get("base_resp", {}).get("status_code", 0) != 0:
            raise ApiError(
                f"video_generation POST returned status_code="
                f"{body.get('base_resp', {}).get('status_code')!r}: "
                f"{body.get('base_resp', {}).get('status_msg')}",
                payload=body,
            )
        return body if isinstance(body, dict) else {}

    def _get(self, url: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        try:
            response = self.session.get(
                url,
                params=params,
                headers=self._auth_headers(),
                timeout=self.http_timeout,
            )
        except requests.RequestException as exc:
            raise TransportError(f"network error GET {url}: {exc}") from exc

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
                f"video_generation GET failed: {status_msg}",
                payload=body if isinstance(body, dict) else {},
            )
        return body if isinstance(body, dict) else {}

    # -- task lifecycle ------------------------------------------------------

    def create_task(self, request: VideoGenerationRequest) -> VideoTaskStatus:
        """Submit a creation request and return the initial task snapshot."""
        payload = request.to_payload(default_model=self.model, base_url=self.base_url)
        body = self._post(self.create_endpoint, payload)
        task_id = body.get("task_id")
        if not task_id:
            raise ApiError(
                "video_generation POST succeeded but returned no task_id",
                payload=body,
            )
        return VideoTaskStatus(
            task_id=str(task_id),
            status="Preparing",
            base_resp=body.get("base_resp", {}),
            raw=body,
        )

    def get_task(self, task_id: str) -> VideoTaskStatus:
        """Poll a single task and return its current status snapshot."""
        body = self._get(self.query_endpoint, params={"task_id": task_id})
        status = body.get("status", "Unknown")
        if status not in SUPPORTED_STATUSES:
            raise ApiError(
                f"unknown task status {status!r} for task_id={task_id!r}",
                payload=body,
            )
        # v2 success payloads nest the download URL under ``content.url``
        # (and sometimes under ``task.content.url``); surface it uniformly.
        content_url: Optional[str] = None
        content_obj = body.get("content")
        if isinstance(content_obj, dict):
            content_url = content_obj.get("url")
        if content_url is None and isinstance(body.get("task"), dict):
            inner = body["task"].get("content")
            if isinstance(inner, dict):
                content_url = inner.get("url")
        return VideoTaskStatus(
            task_id=str(body.get("task_id", task_id)),
            status=status,
            base_resp=body.get("base_resp", {}),
            file_id=str(body.get("file_id")) if body.get("file_id") is not None else None,
            video_width=body.get("video_width"),
            video_height=body.get("video_height"),
            content_url=content_url,
            raw=body,
        )

    def wait_for_completion(
        self,
        task: VideoTaskStatus,
        *,
        timeout_s: Optional[float] = None,
        poll_interval: Optional[float] = None,
        on_poll: Optional[Any] = None,
    ) -> VideoTaskStatus:
        """Block until the task reaches a terminal status or times out.

        ``on_poll`` (optional) is called with each :class:`VideoTaskStatus`
        snapshot so the CLI can render progress without re-polling.
        """
        deadline = time.monotonic() + (timeout_s if timeout_s is not None else self.wait_timeout)
        interval = poll_interval if poll_interval is not None else self.poll_interval
        current = task
        while True:
            if on_poll is not None:
                on_poll(current)
            if current.is_terminal:
                if current.failed:
                    raise ApiError(
                        f"video generation failed: status={current.status}",
                        payload=current.raw,
                    )
                return current
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"timed out waiting for task_id={current.task_id!r} after {timeout_s or self.wait_timeout}s",
                    last_status=current.raw,
                )
            time.sleep(interval)
            current = self.get_task(current.task_id)

    def get_download_url(self, task: VideoTaskStatus) -> str:
        """Resolve a download URL from a succeeded :class:`VideoTaskStatus`."""
        if not task.succeeded:
            raise ApiError(
                f"cannot download from non-success task (status={task.status!r})",
                payload=task.raw,
            )
        # v2 success populates content_url directly on the task object.
        if task.content_url:
            return task.content_url
        # v1 success returns a file_id; fetch /v1/files/retrieve to get the URL.
        if not task.file_id:
            raise ApiError(
                "task succeeded but has neither content_url nor file_id",
                payload=task.raw,
            )
        body = self._get(self.files_endpoint, params={"file_id": task.file_id})
        url = body.get("file", {}).get("download_url") if isinstance(body, dict) else None
        if not url:
            raise ApiError(
                f"file retrieve returned no download_url for file_id={task.file_id!r}",
                payload=body if isinstance(body, dict) else {},
            )
        return url

    # -- convenience wrappers -----------------------------------------------

    def create_text_to_video(
        self,
        *,
        prompt: str,
        duration: int = DEFAULT_DURATION,
        resolution: Optional[str] = None,
        ratio: Optional[str] = None,
        model: Optional[str] = None,
        prompt_optimizer: Optional[bool] = None,
        fast_pretreatment: Optional[bool] = None,
        callback_url: Optional[str] = None,
    ) -> VideoTaskStatus:
        return self.create_task(
            VideoGenerationRequest(
                prompt=prompt,
                duration=duration,
                resolution=resolution,
                ratio=ratio,
                model=model,
                prompt_optimizer=prompt_optimizer,
                fast_pretreatment=fast_pretreatment,
                callback_url=callback_url,
            )
        )

    def create_image_to_video(
        self,
        *,
        prompt: str,
        first_frame_image: str,
        duration: int = DEFAULT_DURATION,
        resolution: Optional[str] = None,
        model: Optional[str] = None,
    ) -> VideoTaskStatus:
        """First-frame image-to-video. Requires the v2 endpoint + MiniMax-H3."""
        return self.create_task(
            VideoGenerationRequest(
                prompt=prompt,
                duration=duration,
                resolution=resolution,
                model=model or "MiniMax-H3",
                payload_version="v2",
                first_frame_image=first_frame_image,
                ratio="adaptive",
            )
        )

    def create_start_end_to_video(
        self,
        *,
        prompt: str,
        first_frame_image: str,
        last_frame_image: str,
        duration: int = DEFAULT_DURATION,
        resolution: Optional[str] = None,
        model: Optional[str] = None,
    ) -> VideoTaskStatus:
        """First+last frame image-to-video. Requires v2 + MiniMax-H3."""
        return self.create_task(
            VideoGenerationRequest(
                prompt=prompt,
                duration=duration,
                resolution=resolution,
                model=model or "MiniMax-H3",
                payload_version="v2",
                first_frame_image=first_frame_image,
                last_frame_image=last_frame_image,
                ratio="adaptive",
            )
        )

    def create_reference_to_video(
        self,
        *,
        prompt: str,
        reference_image: str,
        duration: int = DEFAULT_DURATION,
        resolution: Optional[str] = None,
        ratio: str = "16:9",
        model: Optional[str] = None,
    ) -> VideoTaskStatus:
        """Reference-image-driven video. Requires v2 + MiniMax-H3."""
        return self.create_task(
            VideoGenerationRequest(
                prompt=prompt,
                duration=duration,
                resolution=resolution,
                ratio=ratio,
                model=model or "MiniMax-H3",
                payload_version="v2",
                reference_image=reference_image,
            )
        )

    # -- downloads ----------------------------------------------------------

    def download(
        self,
        task: VideoTaskStatus,
        *,
        output: Path | str,
        overwrite: bool = True,
    ) -> str:
        """Resolve the download URL and save the video to ``output``."""
        url = self.get_download_url(task)
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.exists() and not overwrite:
            return str(output_path)
        try:
            response = self.session.get(url, timeout=self.download_timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise TransportError(f"failed to download {url}: {exc}") from exc
        output_path.write_bytes(response.content)
        return str(output_path)


# -- Public helpers ------------------------------------------------------------


def quick_video(
    prompt: str,
    *,
    output: Path | str,
    duration: int = DEFAULT_DURATION,
    resolution: str = "768P",
    model: Optional[str] = None,
    wait_timeout: float = DEFAULT_WAIT_TIMEOUT,
    poll_interval: float = DEFAULT_POLL_INTERVAL,
) -> VideoGenerationResult:
    """One-shot helper: create, wait, download, return the result."""
    client = VideoGenerationClient.from_env()
    task = client.create_text_to_video(
        prompt=prompt,
        duration=duration,
        resolution=resolution,
        model=model,
    )
    completed = client.wait_for_completion(
        task, timeout_s=wait_timeout, poll_interval=poll_interval
    )
    file_path = client.download(completed, output=output)
    return VideoGenerationResult(task=completed, file_path=file_path)