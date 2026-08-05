---
name: minimax-video-gen
description: "Generate videos (生视频 / text-to-video / image-to-video / start-end-frame / reference-to-video) with the MiniMax video API (MiniMax-H3 / MiniMax-Hailuo-2.3 / MiniMax-Hailuo-02 / T2V-01). Use this skill whenever the user wants a video clip, animation, cinematic shot, short film, storyboard, promo reel, or any moving picture produced from a text prompt and/or reference image(s). Wraps the official async workflow (POST /v1/video_generation, GET /v1/query/video_generation, GET /v1/files/retrieve) plus the v2 multimodal /v2/video_generation endpoint, with a Python client + CLI that polls and downloads the result."
always: false
requires_bins: python3
requires_env: API_KEY,API_BASE_URL
---

# MiniMax Video Generation Skill

> **What this skill does — generates videos.**
> Given a text prompt (or a prompt + reference image / first-frame / last-frame),
> this skill calls the MiniMax video model and returns an actual video file on
> disk. It is the skill to load whenever the user asks for "做个视频", "出一段视频",
> "拍一段短片", "生成一个动画", "做一段 demo 视频", "make a video", "create a short",
> "generate an animation", "render a clip", or any moving-picture deliverable.

The skill wraps the official MiniMax endpoints:

```
POST   {API_BASE_URL}/v1/video_generation          # async create (legacy models)
POST   {API_BASE_URL}/v2/video_generation          # multimodal create (MiniMax-H3)
GET    {API_BASE_URL}/v1/query/video_generation    # poll status
GET    {API_BASE_URL}/v1/files/retrieve            # resolve download URL
```

It ships:

- a reusable Python client (`scripts/video_client.py`),
- parameter validators (`scripts/validators.py`),
- a CLI entry point (`scripts/generate_video.py`) — the **primary** interface,
  invoked via `bash` when the skill is in scope.

## Capabilities (when to use this skill)

Use it whenever the user wants to **generate a video**, including:

- **Text-to-video (文生视频 / t2va)** — turn a written description into a clip.
- **Image-to-video (i2va)** — first-frame image + text, "make this picture move".
- **First + last frame (start/end to video)** — define both ends and let the
  model interpolate.
- **Reference-to-video (r2va)** — keep a character / scene / style consistent
  across generations.
- **Camera-move directives** — `[Pan left]`, `[Push in]`, `[Tilt up]`, …
  15 official commands per docs, combinable up to 3 per bracket.
- **Polling + auto-download** — submit, wait, save the .mp4 to disk.
- **Determinism** — pass `--callback-url` to your own webhook for server-push
  instead of polling.

### Trigger phrases (load this skill when you see these)

- 生视频 / 文生视频 / 图生视频 / 视频生成 / 做个视频 / 出一段视频 / 拍个短片
- generate a video / create a clip / make a short / render a video / animation /
  storyboard / cinematic / promo / reel / teaser
- 让这张图动起来 / animate this image / 把图片做成视频
- 首尾帧 / 起止帧 / 多模态参考 / 角色视频 / 镜头一致

Do **not** use this skill for:

- Image generation — use the sibling `minimax-image-gen` skill instead.
- Audio, music, TTS — wrong product.
- Video editing / inpainting / style transfer — the API only does generation,
  not post-production.
- Live streaming or real-time video — out of scope.

## Prerequisites

- Python 3.9+ with `requests` (`pip install requests`).
- The skill reads **all** configuration from your project's `.env` file at
  the active project root. There is no example file and no built-in
  default URL — the host of the project's `API_BASE_URL` is the host this
  skill will call. Required keys:
  - `API_BASE_URL` — the MiniMax API endpoint your project already uses
    (e.g. `https://api.minimaxi.com` / `https://api.minimax.io`). The
    skill rejects empty values with `ConfigError` at startup.
  - `API_KEY` — your MiniMax API key (Bearer token).
  - `VIDEO_MODEL` — defaults to `MiniMax-Hailuo-2.3`. The skill supports
    `MiniMax-Hailuo-2.3`, `MiniMax-Hailuo-02`, `T2V-01-Director`, `T2V-01`
    (v1 flat payload), and `MiniMax-H3` (v2 multimodal `content[]`).

Never hard-code the API key. Always read it from the environment.

## Endpoint

```
POST  {API_BASE_URL}/v1/video_generation   (v1: MiniMax-Hailuo-2.3 / 02 / T2V-01)
POST  {API_BASE_URL}/v2/video_generation   (v2: MiniMax-H3 multimodal)
GET   {API_BASE_URL}/v1/query/video_generation?task_id=...
GET   {API_BASE_URL}/v1/files/retrieve?file_id=...
Authorization: Bearer {API_KEY}
Content-Type: application/json
```

### v1 request body (async task flow)

```json
{
  "model": "MiniMax-Hailuo-2.3",
  "prompt": "A man picks up a book [Pedestal up], then reads [Static shot].",
  "duration": 6,
  "resolution": "1080P",
  "prompt_optimizer": true,
  "fast_pretreatment": false,
  "callback_url": "https://your.app/callback"
}
```

| field               | type    | required | notes                                                              |
| ------------------- | ------- | -------- | ------------------------------------------------------------------ |
| `model`             | enum    | yes      | `MiniMax-Hailuo-2.3`, `MiniMax-Hailuo-02`, `T2V-01-Director`, `T2V-01` |
| `prompt`            | string  | yes      | ≤ 2000 characters. Camera commands via `[...]` syntax.             |
| `duration`          | int     | yes      | 6 or 10 (10 only for Hailuo-2.3 / Hailuo-02 at 768P/1080P).        |
| `resolution`        | enum    | yes      | `720P`, `768P` (default for Hailuo), `1080P`.                      |
| `prompt_optimizer`  | bool    | no       | Default true. Set false for precise control.                       |
| `fast_pretreatment` | bool    | no       | Hailuo-2.3 / Hailuo-02 only.                                       |
| `callback_url`      | string  | no       | Server-push callback (must echo `challenge` in 3 s).                |

v1 supports **text-to-video only**. First-frame / last-frame / reference
require v2 (see below).

### v2 request body (multimodal MiniMax-H3)

```json
{
  "model": "MiniMax-H3",
  "content": [
    {"type": "text", "text": "镜头拍摄一个女性坐在咖啡馆里..."},
    {"type": "image_url", "image_url": {"url": "https://..."}, "role": "first_frame"}
  ],
  "duration": 5,
  "resolution": "2K",
  "ratio": "16:9"
}
```

| field               | type     | required | notes                                                             |
| ------------------- | -------- | -------- | ----------------------------------------------------------------- |
| `model`             | enum     | yes      | `MiniMax-H3` only on v2                                            |
| `content`           | array    | yes      | multimodal elements with `type` + `role`                          |
| `duration`          | int      | yes      | integer seconds, 4–15                                              |
| `resolution`        | enum     | yes      | `2K` (H3 output)                                                   |
| `ratio`             | enum     | yes      | `16:9`, `9:16`, `1:1`, `4:3`, `3:4`, `21:9`, or `adaptive`        |
| `content[].type`    | enum     | yes      | `text`, `image_url`, `video_url`, `audio_url`                      |
| `content[].role`    | enum     | depends  | `first_frame`, `last_frame`, `reference_image`, `reference_video`, `reference_audio` |

For pure text-to-video on v2 (no images), `ratio` is required and cannot
be `adaptive`. For image-to-video the ratio is determined by the image.

### Status & terminal states

Polling `GET /v1/query/video_generation?task_id=…` returns one of:

| status      | meaning                       |
| ----------- | ----------------------------- |
| `Preparing` | preparing                     |
| `Queueing`  | in queue                      |
| `Processing`| generating                    |
| `Success`   | done — fetch the file          |
| `Fail`      | failed — see `error`          |

On `Success`, the response includes a `file_id` (v1) or a `content.url`
(v2). The client resolves this to a download URL and saves the .mp4
locally.

## Quick Start — CLI

The CLI lives at `scripts/generate_video.py` and is the recommended entry.
From the active project root (so the skill can read `.env`):

```bash
# 6-second text-to-video at 768P, wait + download
python3 workspace/skills/minimax-video-gen/scripts/generate_video.py \
  --prompt "镜头拍摄一个女性坐在咖啡馆里，女人抬头看着窗外，镜头缓缓移动拍摄到窗外的街道，画面呈现暖色调" \
  --duration 6 --resolution 768P \
  --output ./workspace/output/cafe.mp4

# 10-second 1080P with explicit camera moves (Hailuo-2.3)
python3 workspace/skills/minimax-video-gen/scripts/generate_video.py \
  --prompt "A man picks up a book [Pedestal up], then reads [Static shot]." \
  --duration 10 --resolution 1080P --model MiniMax-Hailuo-2.3 \
  --output ./workspace/output/book.mp4

# First-frame image-to-video (v2 / MiniMax-H3)
python3 workspace/skills/minimax-video-gen/scripts/generate_video.py \
  --prompt "Contemporary dance, the people in the picture are performing contemporary dance." \
  --first-frame-image "https://example.com/first.png" \
  --payload-version v2 --model MiniMax-H3 \
  --output ./workspace/output/dance.mp4

# Reference image (v2 / MiniMax-H3) — keep a character consistent
python3 workspace/skills/minimax-video-gen/scripts/generate_video.py \
  --prompt "On an overcast day, in an ancient cobbled alleyway, the model walks and adjusts a vintage beret with a smile" \
  --reference-image "https://example.com/character.png" \
  --payload-version v2 --model MiniMax-H3 --ratio 16:9 \
  --output ./workspace/output/alleyway.mp4

# Submit only, then poll separately
python3 workspace/skills/minimax-video-gen/scripts/generate_video.py \
  --prompt "..." --submit-only
# → {"ok": true, "task_id": "176843862716480", ...}

python3 workspace/skills/minimax-video-gen/scripts/generate_video.py \
  --poll-only --task-id 176843862716480 --output ./workspace/output/v.mp4
```

Useful flags (all flags also exist on the client API):

| flag                    | purpose                                                      |
| ----------------------- | ------------------------------------------------------------ |
| `--duration N`          | seconds (4-15; 10 only for Hailuo-2.3/02 + 768P/1080P)       |
| `--resolution RES`      | 720P / 768P / 1080P                                          |
| `--ratio RATIO`         | aspect ratio (required for v2 text-to-video)                 |
| `--prompt-optimizer`    | enable prompt auto-rewriting (v1)                            |
| `--fast-pretreatment`   | speed up optimization (Hailuo-2.3/02 only)                   |
| `--callback-url URL`    | server-push instead of polling                               |
| `--poll-interval SECS`  | seconds between polls (default 10)                           |
| `--wait-timeout SECS`   | max wait time (default 600)                                  |
| `--debug`               | print last raw query response                                |

The CLI prints a single JSON line on stdout (`task_id`, `status`, `file_path`,
`elapsed_seconds`) so the calling agent can pick paths up directly.

### Exit codes

| code | meaning                                                  |
| ---- | -------------------------------------------------------- |
| 0    | success (video saved / submitted / polled)               |
| 2    | validation error (bad prompt / model / duration / ratio) |
| 3    | config error (missing `API_BASE_URL` / `API_KEY`)        |
| 4    | API error or task reached terminal failure               |
| 5    | transport error or poll timeout                          |
| 6    | file I/O error during download                           |

## Programmatic Use — `video_client.py`

The skill directory is named with a hyphen (`minimax-video-gen`) because
JCodex's skill catalog expects kebab-case names, but Python imports can't
use hyphens. The recommended pattern is to invoke the CLI; if you really
need in-process use, add the skill's `scripts/` directory to `sys.path`
and import the modules by their bare name:

```python
import sys
import time
from pathlib import Path

SKILL_DIR = Path("workspace/skills/minimax-video-gen")
sys.path.insert(0, str(SKILL_DIR / "scripts"))

from video_client import VideoGenerationClient

client = VideoGenerationClient.from_env()  # reads API_BASE_URL + API_KEY + VIDEO_MODEL

task = client.create_text_to_video(
    prompt="镜头拍摄一个女性坐在咖啡馆里...",
    duration=6,
    resolution="768P",
)

# Optional: stream progress to stderr
def on_poll(snapshot):
    print(f"  status={snapshot.status}", file=sys.stderr)

completed = client.wait_for_completion(task, timeout_s=600, on_poll=on_poll)
file_path = client.download(completed, output="./workspace/output/cafe.mp4")
print("saved:", file_path)
```

For the multimodal v2 flow:

```python
task = client.create_reference_to_video(
    prompt="On an overcast day, in an ancient cobbled alleyway, the model walks...",
    reference_image="https://example.com/character.png",
    ratio="16:9",
)
completed = client.wait_for_completion(task)
client.download(completed, output="./out/alleyway.mp4")
```

## Repository Layout

```
workspace/skills/minimax-video-gen/
├── SKILL.md                 # this file
└── scripts/
    ├── __init__.py
    ├── video_client.py      # VideoGenerationClient + dataclasses + polling
    ├── validators.py        # prompt / model / duration / resolution / ratio
    └── generate_video.py    # CLI entry point (argparse)
```

The skill does **not** ship an `.env.example` or any default URL on
purpose. Configuration is read live from the project's own `.env`.

## Conventions & Tips

- Treat `API_KEY` as a secret. Never print it, never commit `.env`, never
  echo it into logs. The CLI redacts it from `--debug` output.
- Video generation takes minutes. Default poll interval is 10 s, default
  wait timeout is 600 s. Raise `--wait-timeout` for slow models.
- Want to react to completion in your own backend? Set `--callback-url`
  and your server must echo the `challenge` field in 3 s during validation,
  then receive status pushes.
- Camera commands inside `[brackets]` after key actions guide the model —
  e.g. `[Pan left]`, `[Push in]`, `[Zoom out]`. Up to 3 per bracket, combine
  with commas for simultaneous motion (`[Pan left, Pedestal up]`).
- File IDs and download URLs are short-lived — the CLI downloads
  immediately and you can ignore the URL after that.
- For long runs, prefer `--submit-only` then a separate `--poll-only` so
  the calling agent can stay responsive.

## Common Mistakes

- Sending `model: MiniMax-M3` (the text model) — video uses Hailuo / H3.
- Setting `duration: 10` with `resolution: 720P` — 10s requires Hailuo-2.3 /
  Hailuo-02 and `768P`/`1080P`. The validator rejects bad combos.
- Setting `duration: 4` — docs say "4-15 seconds", the validator caps at ≥ 4.
- Mixing `payload_version: v1` with `--first-frame-image` — first-frame /
  last-frame / reference inputs are v2-only.
- Forgetting `ratio` for v2 text-to-video — required and cannot be
  `adaptive` when there's no image input.
- Treating `file_id` as long-lived — fetch the download URL immediately
  via `/v1/files/retrieve`.
- Polling every second — docs recommend 10 s intervals to avoid load.

## Troubleshooting

| symptom                                            | likely cause                                          | fix                                                                  |
| -------------------------------------------------- | ----------------------------------------------------- | -------------------------------------------------------------------- |
| `401 invalid api key`                              | key missing prefix or wrong env var                   | ensure `--header "Authorization: Bearer <API_KEY>"`                  |
| `ConfigError: API_BASE_URL is not set`             | `.env` missing the key                                | add `API_BASE_URL=https://api.minimaxi.com` to project `.env`         |
| task stays in `Preparing` / `Queueing` > 5 min     | server load                                           | normal; keep polling; increase `--wait-timeout`                       |
| `404 /v1/video_generation`                         | hitting the wrong host                                | confirm `API_BASE_URL` matches your account's region                 |
| `Fail` status with `1004 invalid params`          | prompt > 2000 chars, bad duration/resolution combo    | shorten prompt; check duration × resolution × model table            |
| `Fail` status with `1011 invalid model`           | model not enabled on your account                     | switch to a model listed on the model page; or enable it in console  |
| download URL returns 403 / 410                     | URL expired (rare)                                    | re-poll task, refetch via `/v1/files/retrieve`                       |

For deeper debugging, run with `--debug` to print the last raw query
response.