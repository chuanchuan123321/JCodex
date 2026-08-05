"""Command-line interface for the MiniMax video generation skill.

Examples
--------
    python3 generate_video.py \\
        --prompt "Camera slowly pans across a neon-lit Tokyo alley at night" \\
        --duration 6 --resolution 768P --output ./out/tokyo.mp4

    python3 generate_video.py \\
        --prompt "A puppy runs toward the camera on a sunny beach" \\
        --first-frame-image https://example.com/first.jpg \\
        --model MiniMax-H3 --payload-version v2 \\
        --output ./out/puppy.mp4

    # Just submit and poll separately
    python3 generate_video.py --prompt "..." --submit-only

    # Just poll an existing task_id
    python3 generate_video.py --poll-only --task-id 176843862716480 --output ./out/v.mp4

The CLI prints a single JSON line on stdout so the calling agent can parse
it directly, and a human-readable summary on stderr.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Optional

# Allow ``python3 scripts/generate_video.py`` to run without installing the
# package. We add the script's own directory so sibling modules are importable
# by their bare name regardless of where the user invokes from.
_THIS = Path(__file__).resolve()
_SCRIPTS_DIR = _THIS.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from video_client import (  # noqa: E402  (sys.path tweak above)
    ApiError,
    ConfigError,
    TimeoutError,
    TransportError,
    VideoGenerationClient,
)
from validators import (  # noqa: E402
    SUPPORTED_MODELS,
    SUPPORTED_RATIOS,
    ValidationError,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="generate_video",
        description="Generate videos via MiniMax video-01 / Hailuo / H3 (POST /v1 or /v2).",
    )
    # Mode selection
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--submit-only",
        action="store_true",
        help="submit the task and print the task_id, do not wait or download",
    )
    mode.add_argument(
        "--poll-only",
        action="store_true",
        help="poll an existing task (requires --task-id) and download on success",
    )

    # Common
    parser.add_argument("--prompt", help="text description (≤ 2000 / 7000 chars)")
    parser.add_argument(
        "--duration", type=int, default=None,
        help="video length in seconds (4-15; 10s only for Hailuo-2.3/Hailuo-02)",
    )
    parser.add_argument(
        "--resolution",
        choices=("720P", "768P", "1080P", "2K"),
        default=None,
        help="video resolution (v1 default 768P, v2 default 2K)",
    )
    parser.add_argument(
        "--ratio", choices=SUPPORTED_RATIOS, default=None,
        help="aspect ratio (required for v2; ignored for v1)",
    )
    parser.add_argument(
        "--model", choices=SUPPORTED_MODELS, default=None,
        help="override VIDEO_MODEL (defaults to env VIDEO_MODEL or MiniMax-Hailuo-2.3)",
    )
    parser.add_argument(
        "--payload-version", choices=("v1", "v2"), default="v1",
        help="v1=async flat payload, v2=multimodal content[] (MiniMax-H3 only)",
    )
    parser.add_argument(
        "--prompt-optimizer", action="store_true",
        help="enable prompt auto-rewriting (v1)",
    )
    parser.add_argument(
        "--fast-pretreatment", action="store_true",
        help="reduce optimization time (Hailuo-2.3 / Hailuo-02 only)",
    )
    parser.add_argument("--callback-url", default=None, help="optional task callback URL")
    # v2 multimodal inputs
    parser.add_argument("--first-frame-image", default=None, help="first-frame image URL (v2)")
    parser.add_argument("--last-frame-image", default=None, help="last-frame image URL (v2)")
    parser.add_argument("--reference-image", default=None, help="reference image URL (v2)")
    # Connection
    parser.add_argument("--base-url", default=None, help="override API_BASE_URL")
    parser.add_argument("--api-key", default=None, help="override API_KEY (prefer env)")
    parser.add_argument("--http-timeout", type=float, default=None, help="HTTP timeout for create + query")
    parser.add_argument("--download-timeout", type=float, default=None, help="HTTP timeout for the final video download")
    parser.add_argument("--dotenv", type=Path, default=None, help="path to .env (default: <cwd>/.env)")
    # Polling
    parser.add_argument(
        "--poll-interval", type=float, default=None,
        help="seconds between status polls (default: 10)",
    )
    parser.add_argument(
        "--wait-timeout", type=float, default=None,
        help="seconds to wait for terminal status (default: 600)",
    )
    parser.add_argument(
        "--task-id", default=None, help="task_id for --poll-only",
    )
    # Outputs
    parser.add_argument(
        "--output", type=Path, default=None,
        help="output file path (.mp4). required unless --submit-only.",
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="print the request payload (without the API key) and raw responses",
    )
    return parser


def _emit_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _require_prompt_when_needed(args: argparse.Namespace) -> None:
    if args.poll_only:
        return
    if not args.prompt:
        print("--prompt is required when not using --poll-only", file=sys.stderr)
        sys.exit(2)


def _build_client(args: argparse.Namespace) -> VideoGenerationClient:
    kwargs: dict[str, Any] = {}
    if args.api_key:
        kwargs["api_key"] = args.api_key
    if args.base_url:
        kwargs["base_url"] = args.base_url
    if args.model:
        kwargs["model"] = args.model
    if args.http_timeout is not None:
        kwargs["http_timeout"] = args.http_timeout
    if args.download_timeout is not None:
        kwargs["download_timeout"] = args.download_timeout
    if args.poll_interval is not None:
        kwargs["poll_interval"] = args.poll_interval
    if args.wait_timeout is not None:
        kwargs["wait_timeout"] = args.wait_timeout

    return VideoGenerationClient.from_env(
        dotenv_path=args.dotenv,
        **{k: v for k, v in kwargs.items() if k in {"api_key", "base_url", "model"}},
    ) if not all(k in kwargs for k in ("api_key", "base_url", "model", "http_timeout", "download_timeout", "poll_interval", "wait_timeout")) else VideoGenerationClient(**kwargs)


def _client_from_args(args: argparse.Namespace) -> VideoGenerationClient:
    """Build a client honoring CLI overrides on top of .env."""
    if args.api_key and args.base_url and args.model:
        return VideoGenerationClient(
            api_key=args.api_key,
            base_url=args.base_url,
            model=args.model,
            http_timeout=args.http_timeout or 120,
            download_timeout=args.download_timeout or 600,
            poll_interval=args.poll_interval or 10,
            wait_timeout=args.wait_timeout or 600,
        )
    client = VideoGenerationClient.from_env(dotenv_path=args.dotenv)
    if args.api_key:
        client.api_key = args.api_key
    if args.base_url:
        client.base_url = args.base_url.rstrip("/")
    if args.model:
        client.model = args.model
    if args.http_timeout is not None:
        client.http_timeout = args.http_timeout
    if args.download_timeout is not None:
        client.download_timeout = args.download_timeout
    if args.poll_interval is not None:
        client.poll_interval = args.poll_interval
    if args.wait_timeout is not None:
        client.wait_timeout = args.wait_timeout
    return client


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    _require_prompt_when_needed(args)

    if args.poll_only and not args.task_id:
        print("--task-id is required when using --poll-only", file=sys.stderr)
        return 2
    if not args.poll_only and not args.submit_only and not args.output:
        print("--output is required unless --submit-only is set", file=sys.stderr)
        return 2

    try:
        client = _client_from_args(args)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 3

    # --poll-only path: skip task creation, fetch status and download.
    if args.poll_only:
        try:
            task = client.get_task(args.task_id)
            completed = client.wait_for_completion(
                task,
                timeout_s=args.wait_timeout,
                poll_interval=args.poll_interval,
            )
        except ValidationError as exc:
            print(f"validation error: {exc}", file=sys.stderr)
            return 2
        except ConfigError as exc:
            print(f"config error: {exc}", file=sys.stderr)
            return 3
        except ApiError as exc:
            _emit_json({
                "ok": False, "error": "api_error", "message": str(exc),
                "base_resp": exc.payload.get("base_resp", {}), "raw": exc.payload,
            })
            return 4
        except TimeoutError as exc:
            _emit_json({
                "ok": False, "error": "timeout",
                "message": str(exc), "last_status": exc.payload,
            })
            return 5
        except TransportError as exc:
            print(f"transport error: {exc}", file=sys.stderr)
            return 5

        try:
            file_path = client.download(completed, output=args.output)
        except (TransportError, ApiError) as exc:
            print(f"download failed: {exc}", file=sys.stderr)
            return 6

        _emit_json({
            "ok": True,
            "mode": "poll_only",
            "task_id": completed.task_id,
            "status": completed.status,
            "file_id": completed.file_id,
            "video_width": completed.video_width,
            "video_height": completed.video_height,
            "file_path": file_path,
        })
        return 0

    # Create the task.
    try:
        task = client.create_text_to_video(
            prompt=args.prompt,
            duration=args.duration if args.duration is not None else 6,
            resolution=args.resolution,
            ratio=args.ratio,
            model=args.model,
            prompt_optimizer=True if args.prompt_optimizer else None,
            fast_pretreatment=True if args.fast_pretreatment else None,
            callback_url=args.callback_url,
        ) if args.payload_version == "v1" else client.create_task.__wrapped__ if False else _create_v2_or_default(
            client, args
        )
    except ValidationError as exc:
        print(f"validation error: {exc}", file=sys.stderr)
        return 2
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 3
    except ApiError as exc:
        _emit_json({
            "ok": False, "error": "api_error", "message": str(exc),
            "base_resp": exc.payload.get("base_resp", {}), "raw": exc.payload,
        })
        return 4
    except TransportError as exc:
        print(f"transport error: {exc}", file=sys.stderr)
        return 5

    if args.debug:
        print(f"[debug] task submitted: task_id={task.task_id}", file=sys.stderr)

    if args.submit_only:
        _emit_json({
            "ok": True,
            "mode": "submit_only",
            "task_id": task.task_id,
            "model": args.model or client.model,
            "payload_version": args.payload_version,
        })
        return 0

    # Poll + download.
    def _on_poll(snapshot) -> None:  # type: ignore[no-untyped-def]
        elapsed = time.monotonic() - start
        print(
            f"[poll] task_id={snapshot.task_id} status={snapshot.status} "
            f"elapsed={elapsed:.1f}s",
            file=sys.stderr,
        )

    start = time.monotonic()
    try:
        completed = client.wait_for_completion(
            task,
            timeout_s=args.wait_timeout,
            poll_interval=args.poll_interval,
            on_poll=_on_poll,
        )
    except ApiError as exc:
        _emit_json({
            "ok": False, "error": "task_failed", "message": str(exc),
            "base_resp": exc.payload.get("base_resp", {}), "raw": exc.payload,
            "task_id": task.task_id,
        })
        return 4
    except TimeoutError as exc:
        _emit_json({
            "ok": False, "error": "timeout", "message": str(exc),
            "task_id": task.task_id, "last_status": exc.payload,
        })
        return 5
    except TransportError as exc:
        print(f"transport error: {exc}", file=sys.stderr)
        return 5

    try:
        file_path = client.download(completed, output=args.output)
    except (TransportError, ApiError) as exc:
        print(f"download failed: {exc}", file=sys.stderr)
        return 6

    summary = {
        "ok": True,
        "mode": "submit_and_wait",
        "task_id": completed.task_id,
        "status": completed.status,
        "file_id": completed.file_id,
        "video_width": completed.video_width,
        "video_height": completed.video_height,
        "file_path": file_path,
        "elapsed_seconds": round(time.monotonic() - start, 2),
    }
    if args.debug:
        summary["debug_last_query"] = completed.raw
    _emit_json(summary)
    return 0


def _create_v2_or_default(client: VideoGenerationClient, args: argparse.Namespace):
    """Helper to dispatch v1 vs v2 creation without an if-ladder at top level."""
    if args.payload_version == "v2":
        # Pick the v2-specific wrapper based on which reference inputs were
        # provided. v2 requires MiniMax-H3.
        model = args.model or "MiniMax-H3"
        common = dict(
            prompt=args.prompt,
            duration=args.duration if args.duration is not None else 6,
            resolution=args.resolution,
            model=model,
        )
        if args.first_frame_image and args.last_frame_image:
            return client.create_start_end_to_video(
                **common,
                first_frame_image=args.first_frame_image,
                last_frame_image=args.last_frame_image,
            )
        if args.first_frame_image:
            return client.create_image_to_video(
                **common,
                first_frame_image=args.first_frame_image,
            )
        if args.reference_image:
            return client.create_reference_to_video(
                **common,
                reference_image=args.reference_image,
                ratio=args.ratio or "16:9",
            )
        # Pure text-to-video on v2 needs a non-adaptive ratio.
        if not args.ratio or args.ratio == "adaptive":
            raise ValidationError("ratio", "for v2 text-to-video, ratio is required and cannot be 'adaptive'")
        return client.create_text_to_video(
            prompt=args.prompt,
            duration=args.duration if args.duration is not None else 6,
            resolution=args.resolution,
            ratio=args.ratio,
            model=model,
        )
    # v1 path.
    return client.create_text_to_video(
        prompt=args.prompt,
        duration=args.duration if args.duration is not None else 6,
        resolution=args.resolution,
        ratio=args.ratio,
        model=args.model,
        prompt_optimizer=True if args.prompt_optimizer else None,
        fast_pretreatment=True if args.fast_pretreatment else None,
        callback_url=args.callback_url,
    )


if __name__ == "__main__":
    raise SystemExit(main())