---
name: minimax-image-gen
description: "Generate images (生图 / 文生图 / 图生图 / 配图 / 出图 / 画一张 / 生成图片 / 做张海报 / 做个 logo / 角色一致性) with the MiniMax image-01 API. Use this skill whenever the user wants a picture, illustration, poster, cover, character sheet, concept art, or any visual asset produced from a text prompt or a prompt + reference image. Wraps POST {API_BASE_URL}/v1/image_generation with a Python client + CLI; supports url and base64 response_format, downloads URL results to disk before the 24h expiry."
always: false
requires_bins: python3
requires_env: API_KEY,API_BASE_URL
---

# MiniMax Image Generation Skill

> **What this skill does — generates images.**
> Given a text prompt (or a prompt + reference image), this skill calls the
> MiniMax image model and returns an actual image file on disk. It is the
> skill to load whenever the user asks for "画一张", "生成图片", "做个海报",
> "出一张配图", "draw me a picture", "generate an illustration", "create a
> cover / logo / character sheet", or any visual deliverable.

The skill wraps the official MiniMax endpoint:

```
POST {API_BASE_URL}/v1/image_generation
```

It ships:

- a reusable Python client (`scripts/image_client.py`),
- parameter validators (`scripts/validators.py`),
- a CLI entry point (`scripts/generate_image.py`) — the **primary** interface,
  invoked via `bash` when the skill is in scope.

## Capabilities (when to use this skill)

Use it whenever the user wants to **generate an image**, including:

- **Text-to-image (文生图)** — turn a written description into a picture.
- **Image-to-image with a subject reference (图生图 / 角色一致性)** — keep a
  character / object looking the same across new scenes.
- **Multiple variations** — `--n 2..9` for "几张 / 多给几个 / a few options".
- **Deterministic regeneration** — fix a `seed` for reproducibility.
- **Specific aspect ratios** — `1:1`, `16:9`, `9:16`, `4:3`, `3:2`, `2:3`,
  `3:4`, `21:9` (image-01 only).
- **Either URL or base64** output; the CLI downloads URL outputs to disk
  before they expire (~24 h).

### Trigger phrases (load this skill when you see these)

- 生图 / 文生图 / 图生图 / 配图 / 出图 / 画一张 / 生成图片 / 做张海报 / 做个 logo
- generate an image / draw / illustrate / create a picture / make a poster /
  render / visual / cover art / character sheet / concept art
- 角色一致性 / 同一个角色不同场景 / keep the character consistent
- 需要一张图 / 给我看看长什么样 / 出一个视觉稿
- draw me / make me a picture of / show me what X looks like

Do **not** use this skill for:

- Video generation (MiniMax video / Hailuo / Sora / Veo) — wrong product.
- Audio, music, TTS — wrong product.
- Editing / inpainting / outpainting / upscaling — the endpoint only does
  text-to-image and single-reference character image-to-image.
- Querying an existing image — use vision / file-reading tools instead.

## Prerequisites

- Python 3.9+ with `requests` (`pip install requests`).
- The skill reads **all** configuration from your project's `.env` file at
  the active project root. There is no example file and no built-in
  default URL — the host of the project's `API_BASE_URL` is the host this
  skill will call. Required keys:
  - `API_BASE_URL` — the MiniMax API endpoint your project already uses
    (e.g. `https://api.minimaxi.com` / `https://api.minimax.io`). The
    skill rejects empty values with `ConfigError` at startup.
  - `API_KEY` — your MiniMax API key (Bearer token). The skill raises
    `ConfigError` if it is missing.
  - `IMAGE_MODEL` *(optional)* — defaults to `image-01`. Set this in your
    project's `.env` to switch to `image-01-live` (China-only) or any
    custom value. The skill does **not** hard-code a default URL; it
    also does **not** ship a `.env.example`.

> The skill frontmatter declares `requires_env: API_KEY,API_BASE_URL`
> only. `IMAGE_MODEL` is intentionally **not** a hard requirement, so the
> skill loader will recognise this skill as long as `API_KEY` and
> `API_BASE_URL` are set in the active process environment. The model
> itself falls back to a hard-coded `image-01` when `IMAGE_MODEL` is
> absent, which matches the previous generation behaviour.

## Endpoint

```
POST {API_BASE_URL}/v1/image_generation
Authorization: Bearer {API_KEY}
Content-Type: application/json
```

### Request body (full schema)

| field               | type            | required | notes                                                                 |
| ------------------- | --------------- | -------- | --------------------------------------------------------------------- |
| `model`             | enum            | yes      | `image-01` (or `image-01-live` on China endpoint)                     |
| `prompt`            | string          | yes      | ≤ 1500 characters                                                     |
| `aspect_ratio`      | enum            | no       | `1:1`, `16:9`, `4:3`, `3:2`, `2:3`, `3:4`, `9:16`, `21:9` (image-01) |
| `width` / `height`  | int (512–2048)  | no       | Image-01 only; must be set together; must be multiples of 8           |
| `response_format`   | enum            | no       | `url` (default, expires ~24h) or `base64`                             |
| `n`                 | int (1–9)       | no       | Default 1                                                             |
| `seed`              | int64           | no       | Same seed + params ≈ reproducible result                              |
| `prompt_optimizer`  | bool            | no       | Default false                                                         |
| `aigc_watermark`    | bool            | no       | Default false                                                         |
| `subject_reference` | array<object>   | no       | Up to 1 entry: `{"type":"character","image_file":"<url>"}`            |

If both `aspect_ratio` and `width`/`height` are sent, `aspect_ratio` wins
according to the official docs.

### Response shape

```json
{
  "id": "03ff3cd0820949eb8a410056b5f21d38",
  "data": {
    "image_urls": ["https://..."],
    "image_base64": ["..."]
  },
  "metadata": { "failed_count": "0", "success_count": "1" },
  "base_resp": { "status_code": 0, "status_msg": "success" }
}
```

Failure path: `base_resp.status_code != 0` — surface `status_msg` and the full
payload to the caller.

## Quick Start — CLI

The CLI lives at `scripts/generate_image.py` and is the recommended entry.
From the active project root (so the skill can read `.env`):

```bash
python3 workspace/skills/minimax-image-gen/scripts/generate_image.py \
  --prompt "一只橘猫坐在雨后的上海街头，霓虹灯倒映在湿润的路面上，电影感" \
  --aspect-ratio 16:9 \
  --output ./workspace/output/orange-cat.jpg
```

Useful flags:

```bash
# 3 variations, auto-prompt-rewrite, deterministic
python3 workspace/skills/minimax-image-gen/scripts/generate_image.py \
  --prompt "Studio shot of a vintage typewriter, dramatic lighting" \
  --n 3 --prompt-optimizer --seed 42 \
  --output-dir ./workspace/output/typewriter

# Subject reference (character-consistent generation)
python3 workspace/skills/minimax-image-gen/scripts/generate_image.py \
  --prompt "在赛博朋克东京街头，未来雨夜，电影海报风格" \
  --reference-url "https://example.com/character.jpg" \
  --aspect-ratio 9:16 --n 2 \
  --output-dir ./workspace/output/character

# Get base64 inline (skips download step)
python3 workspace/skills/minimax-image-gen/scripts/generate_image.py \
  --prompt "Logo mark for an AI assistant, flat vector, minimal" \
  --response-format base64
```

The CLI prints a JSON line with `task_id`, `image_paths`, and any `failed_count`
so the calling agent can pick the path up directly. When `response_format=url`,
the CLI downloads every URL into `--output-dir` (or `--output` if a single file
is requested) and removes nothing from the remote CDN — that is the user's
job if they want to scrub the URL.

### Exit codes

| code | meaning                                                       |
| ---- | ------------------------------------------------------------- |
| 0    | success (every requested image saved / returned)              |
| 2    | validation error (bad prompt / ratio / seed)                  |
| 3    | API auth/config error (missing env, 401/403)                  |
| 4    | API returned `base_resp.status_code != 0`                     |
| 5    | network/transport error (timeout, DNS, connection)            |
| 6    | file I/O error when writing outputs                           |

## Programmatic Use — `image_client.py`

The skill directory is named with a hyphen (`minimax-image-gen`) because
JCodex's skill catalog expects kebab-case names, but Python imports can't
use hyphens. The recommended pattern is to invoke the CLI; if you really
need in-process use, add the skill's `scripts/` directory to `sys.path`
and import the modules by their bare name:

```python
import sys
from pathlib import Path

SKILL_DIR = Path("workspace/skills/minimax-image-gen")
sys.path.insert(0, str(SKILL_DIR / "scripts"))

from image_client import (
    ImageGenerationClient,
    GenerationRequest,
    GenerationResult,
)

client = ImageGenerationClient.from_env()  # reads API_BASE_URL + API_KEY + (optional IMAGE_MODEL)

req = GenerationRequest(
    prompt="Studio shot of a vintage typewriter",
    aspect_ratio="16:9",
    n=1,
    response_format="url",
    prompt_optimizer=True,
)

result = client.generate(req)            # type: GenerationResult
print(result.task_id, result.image_urls) # URLs or local paths after download

# Auto-download URLs to disk
saved = client.download(result, output_dir="./workspace/output/typewriter")
print(saved)  # list[str] of local file paths
```

`GenerationResult.image_bytes` is populated when `response_format="base64"`.

## Repository Layout

```
workspace/skills/minimax-image-gen/
├── SKILL.md                 # this file
└── scripts/
    ├── __init__.py
    ├── image_client.py      # ImageGenerationClient + dataclasses
    ├── validators.py        # prompt / ratio / seed validation
    └── generate_image.py    # CLI entry point (argparse)
```

## Conventions & Tips

- Treat `API_KEY` as a secret. Never print it, never commit `.env`, never echo
  it into logs. The CLI redacts it from `--debug` output.
- Always set an explicit `aspect_ratio` unless you deliberately want 1:1.
- When the user asks for "几张 / 多几张 / a few variants", pass `--n 2..4`.
  Do not exceed 9 — that is the API limit and will return 4xx.
- URL links expire ~24h. The CLI downloads them by default; if you opt out of
  download with `--no-download`, surface that expiry clearly to the user.
- If `prompt_optimizer` is on, the rewritten prompt is not echoed back. Tell
  the user the prompt was optimized, not what it became.
- For reproducibility, record the `seed` (echoed by the CLI as `seed_used`)
  and the full `payload` so reruns are byte-identical.
- The international endpoint (`api.minimax.io`) currently only lists `image-01`;
  `image-01-live` is China-only. The CLI rejects `image-01-live` when it
  detects the international host.

## Common Mistakes

- Sending `model: MiniMax-M3` (the text model) — `image-01` is a separate model.
- Sending `width` *or* `height` without the other on `image-01` — the API ignores
  them unless both are present and divisible by 8.
- Mixing `aspect_ratio` with `width/height` and expecting a custom ratio — the
  official docs say `aspect_ratio` wins.
- Treating the returned URL as long-lived — download it or switch to `base64`.
- Forgetting the `Authorization: Bearer ` prefix on the key — the API silently
  rejects with HTTP 401 and a JSON `base_resp.status_msg`.

## Troubleshooting

| symptom                                   | likely cause                                | fix                                                   |
| ----------------------------------------- | ------------------------------------------- | ----------------------------------------------------- |
| `401 invalid api key`                     | key missing prefix or wrong env var         | ensure `--header "Authorization: Bearer <API_KEY>"`  |
| `1004 invalid params` / `prompt too long` | prompt > 1500 chars                         | shorten or split                                      |
| `1008 invalid aspect_ratio`               | typo or unsupported value                  | use one of the 8 enum values                          |
| `2049 invalid api key`                    | wrong endpoint (chat vs image)              | confirm `${API_BASE_URL}/v1/image_generation`         |
| download fails for one of N images        | transient CDN issue                         | retry; surface `metadata.failed_count`                |
| skill shows "unavailable" in the loader   | `API_KEY` or `API_BASE_URL` missing in env  | set them in the project `.env` (cwd) and reload      |

For deeper debugging, run with `--debug` to print the request payload (without
the API key) and the raw response.
