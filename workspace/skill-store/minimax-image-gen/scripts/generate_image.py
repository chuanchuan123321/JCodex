"""Command-line interface for the MiniMax image generation skill.

Examples
--------
    python3 generate_image.py \\
        --prompt "一只橘猫坐在雨后的上海街头" \\
        --aspect-ratio 16:9 \\
        --output ./out/cat.jpg

    python3 generate_image.py \\
        --prompt "Studio shot, vintage typewriter" \\
        --n 3 --prompt-optimizer --seed 42 \\
        --output-dir ./out/typewriter

    python3 generate_image.py \\
        --prompt "在赛博朋克东京街头" \\
        --reference-url "https://example.com/character.jpg" \\
        --aspect-ratio 9:16 --n 2 \\
        --output-dir ./out/character

The CLI prints a single JSON line on stdout so the calling agent can parse
it directly, and a human-readable summary on stderr.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path
from typing import Any, Optional

# Allow ``python3 scripts/generate_image.py`` to run without installing the
# package. We add the script's own directory so sibling modules are importable
# by their bare name regardless of where the user invokes from.
_THIS = Path(__file__).resolve()
_SCRIPTS_DIR = _THIS.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from image_client import (  # noqa: E402  (sys.path tweak above)
    ApiError,
    ConfigError,
    ImageGenerationClient,
    ImageGenError,
    TransportError,
)
from validators import (  # noqa: E402
    SUPPORTED_ASPECT_RATIOS,
    SUPPORTED_MODELS,
    ValidationError,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="generate_image",
        description="Generate images via MiniMax image-01 (POST /v1/image_generation).",
    )
    parser.add_argument(
        "--prompt",
        required=True,
        help="text description (≤ 1500 characters)",
    )
    parser.add_argument(
        "--aspect-ratio",
        choices=SUPPORTED_ASPECT_RATIOS,
        default="1:1",
        help="image aspect ratio (default: 1:1)",
    )
    parser.add_argument(
        "--n",
        type=int,
        default=1,
        help="number of images to generate (1-9, default: 1)",
    )
    parser.add_argument(
        "--response-format",
        choices=("url", "base64"),
        default="url",
        help="response format (default: url, expires ~24h)",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=None,
        help="image width in px (image-01 only, must pair with --height, multiple of 8)",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=None,
        help="image height in px (image-01 only, must pair with --width, multiple of 8)",
    )
    parser.add_argument(
        "--reference-url",
        default=None,
        help="subject reference image URL (image-to-image)",
    )
    parser.add_argument(
        "--prompt-optimizer",
        action="store_true",
        help="enable automatic prompt optimization",
    )
    parser.add_argument(
        "--aigc-watermark",
        action="store_true",
        help="embed an AIGC watermark in the output",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="random seed for reproducibility",
    )
    parser.add_argument(
        "--model",
        choices=SUPPORTED_MODELS,
        default=None,
        help="override IMAGE_MODEL (defaults to env IMAGE_MODEL or the hard-coded image-01)",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="override API_BASE_URL (defaults to env API_BASE_URL)",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="override API_KEY (defaults to env API_KEY; prefer env)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="single-file output path (only valid when --n=1)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="directory to write outputs into (created if missing)",
    )
    parser.add_argument(
        "--filename-prefix",
        default="image",
        help="prefix for output filenames when --output-dir is used",
    )
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="do not download URL responses (URLs expire ~24h)",
    )
    parser.add_argument(
        "--save-base64",
        type=Path,
        default=None,
        help="when response-format=base64, write the raw base64 string to this file",
    )
    parser.add_argument(
        "--http-timeout",
        type=float,
        default=None,
        help="HTTP timeout in seconds for the generation request",
    )
    parser.add_argument(
        "--dotenv",
        type=Path,
        default=None,
        help="path to a .env file to load (default: <cwd>/.env)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="print request payload (without API key) and raw response",
    )
    return parser


def _resolve_output_paths(args: argparse.Namespace) -> tuple[Optional[Path], Optional[Path]]:
    if args.output and args.output_dir:
        raise SystemExit("--output and --output-dir are mutually exclusive")
    if args.output and args.n != 1:
        raise SystemExit("--output can only be used when --n=1; use --output-dir instead")
    return args.output, args.output_dir


def _emit_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    output_path, output_dir = _resolve_output_paths(args)

    # Construct the client. ConfigError maps to exit code 3.
    client_kwargs: dict[str, Any] = {}
    if args.api_key:
        client_kwargs["api_key"] = args.api_key
    if args.base_url:
        client_kwargs["base_url"] = args.base_url
    if args.model:
        client_kwargs["model"] = args.model
    if args.http_timeout:
        client_kwargs["http_timeout"] = args.http_timeout

    try:
        client = ImageGenerationClient.from_env(
            dotenv_path=args.dotenv,
            **{k: v for k, v in client_kwargs.items() if k in {"api_key", "base_url", "model"}},
        )
        if "http_timeout" in client_kwargs:
            client.http_timeout = client_kwargs["http_timeout"]
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 3

    # Build the request.
    try:
        if args.reference_url:
            result = client.generate_with_reference(
                prompt=args.prompt,
                reference_url=args.reference_url,
                aspect_ratio=args.aspect_ratio,
                n=args.n,
                response_format=args.response_format,
                prompt_optimizer=args.prompt_optimizer,
                aigc_watermark=args.aigc_watermark,
                seed=args.seed,
                model=args.model,
            )
        else:
            result = client.generate_text_to_image(
                prompt=args.prompt,
                aspect_ratio=args.aspect_ratio,
                n=args.n,
                response_format=args.response_format,
                width=args.width,
                height=args.height,
                prompt_optimizer=args.prompt_optimizer,
                aigc_watermark=args.aigc_watermark,
                seed=args.seed,
                model=args.model,
            )
    except ValidationError as exc:
        print(f"validation error: {exc}", file=sys.stderr)
        return 2
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 3
    except ApiError as exc:
        # surface API errors with their payload
        _emit_json(
            {
                "ok": False,
                "error": "api_error",
                "message": str(exc),
                "base_resp": exc.payload.get("base_resp", {}),
                "raw": exc.payload,
            }
        )
        return 4
    except TransportError as exc:
        print(f"transport error: {exc}", file=sys.stderr)
        return 5

    # Persist outputs.
    saved_paths: list[str] = []
    base64_blobs: list[str] = []

    if args.response_format == "base64":
        base64_blobs = [
            base64.b64encode(chunk).decode("ascii") for chunk in result.image_bytes
        ]
        if args.save_base64:
            args.save_base64.parent.mkdir(parents=True, exist_ok=True)
            args.save_base64.write_text("\n".join(base64_blobs), encoding="utf-8")
            saved_paths.append(str(args.save_base64))
        if output_path:
            if not result.image_bytes:
                print("api returned no images", file=sys.stderr)
                return 4
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(result.image_bytes[0])
            saved_paths.append(str(output_path))
        elif output_dir and not args.no_download:
            saved_paths.extend(
                client.download(result, output_dir=output_dir, filename_prefix=args.filename_prefix)
            )
    else:
        # response_format=url
        if args.no_download:
            print(
                "warning: --no-download set; URLs expire in ~24 hours.",
                file=sys.stderr,
            )
        elif output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            saved = client.download(result, output_dir=output_path.parent, filename_prefix=args.filename_prefix)
            # rename first file to the requested --output target if possible
            try:
                Path(saved[0]).replace(output_path)
                saved_paths.append(str(output_path))
                saved_paths.extend(saved[1:])
            except (IndexError, OSError):
                print("failed to rename downloaded file to --output target", file=sys.stderr)
                return 6
        elif output_dir:
            saved_paths.extend(
                client.download(result, output_dir=output_dir, filename_prefix=args.filename_prefix)
            )

    summary = {
        "ok": True,
        "task_id": result.task_id,
        "model": result.model,
        "response_format": result.response_format,
        "image_paths": saved_paths,
        "image_urls": result.image_urls,
        "image_base64_count": len(result.image_bytes),
        "failed_count": result.failed_count,
        "success_count": result.success_count,
        "base_resp": result.base_resp,
        "seed_used": (result.raw.get("data", {}) if isinstance(result.raw, dict) else {}).get("seed"),
    }
    if base64_blobs and not args.save_base64:
        # Provide the first blob inline so the caller can grab it if it wants,
        # but only when it isn't already written somewhere.
        summary["image_base64_first"] = base64_blobs[0]

    if args.debug:
        summary["debug_raw_response"] = result.raw

    _emit_json(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())