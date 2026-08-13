"""JCodex desktop UI - pure helpers."""

import base64
import mimetypes
import os
import re
import shutil
import tempfile
import threading
from pathlib import Path
from urllib.parse import unquote, urlsplit

from agent.core.memory_store import MemoryStore
from agent.core.project_store import PROJECT_CONTEXT_FILES
from agent.core.prompt_helpers import (
    _multi_agent_mode_instruction,
    _plan_mode_instruction,
    _platform_instruction,
)
from agent.ui.desktop import constants, runtime
from agent.ui.desktop.constants import MAX_ATTACHMENT_COUNT


def _seed_bundled_skill_files() -> None:
    """Seed bundled skills/store into the per-user data dir on first run.

    In the packaged app PROJECT_ROOT points inside the app bundle while
    DATA_ROOT is the user's Application Support folder; dev mode (same
    folder) is a no-op. Existing entries are never overwritten.
    """
    if constants.PROJECT_ROOT.resolve() == constants.DATA_ROOT.resolve():
        return
    try:
        for relative in ("skills", "skill-store"):
            source = constants.PROJECT_ROOT / "workspace" / relative
            destination = constants.DATA_ROOT / "workspace" / relative
            if not source.exists():
                continue
            destination.mkdir(parents=True, exist_ok=True)
            for item in source.iterdir():
                if not item.is_dir() or item.name.startswith("."):
                    continue
                target = destination / item.name
                if target.exists():
                    continue
                try:
                    shutil.copytree(item, target)
                    print(f"[skills] seeded {relative}/{item.name}")
                except Exception:
                    shutil.rmtree(target, ignore_errors=True)
    except Exception as exc:
        print(f"[skills] seed bundled skills failed: {exc}")


def _short_term_memory_lock(path: Path) -> threading.RLock:
    """Share one in-process write lock between panes using the same context files."""
    key = str(Path(path).expanduser().resolve())
    with runtime._short_term_memory_locks_guard:
        return runtime._short_term_memory_locks.setdefault(key, threading.RLock())


def _short_term_compression_lock(path: Path) -> threading.Lock:
    """Prevent two panes from compacting the same short-term files together."""
    key = str(Path(path).expanduser().resolve())
    with runtime._short_term_memory_locks_guard:
        return runtime._short_term_compression_locks.setdefault(key, threading.Lock())


def _coerce_plan_mode(value: object) -> bool:
    """Coerce Eel's JSON value without treating the string ``false`` as true."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _voice_mode_instruction(voice_mode: bool) -> str:
    """Build response-style guidance used only for spoken conversations."""
    if not voice_mode:
        return ""
    return (
        "Voice conversation mode is active. Keep every user-visible progress "
        "update and final answer brief, natural, and conversational, normally "
        "one to three short sentences. Speak like an everyday conversation. "
        "Never expose private reasoning, hidden analysis, chain-of-thought, or "
        "meta-commentary about how you formed the answer. Avoid Markdown, "
        "headings, lists, tables, code fences, URLs, file-system paths, command "
        "syntax, raw identifiers, and decorative symbols unless the user "
        "explicitly asks for exact technical details. Do not call the `question` "
        "tool in voice mode because it requires desktop clicking. When you need "
        "information or confirmation, ask one short natural spoken question in "
        "your response, then wait for the user's next voice message. Use other "
        "tools normally when needed, but keep spoken progress updates concise."
    )


def _tool_display_params(params: object) -> dict:
    """Keep only compact, non-content tool arguments for desktop cards."""
    if not isinstance(params, dict):
        return {}

    display = {}
    for key in constants._TOOL_DISPLAY_PARAM_KEYS:
        value = params.get(key)
        if isinstance(value, str):
            display[key] = value[: constants._TOOL_DISPLAY_PARAM_MAX_CHARS]
        elif isinstance(value, (int, float, bool)):
            display[key] = value
    return display


def _is_exceptionally_complex_project_request(message: str) -> bool:
    """Keep automatic planning limited to clearly large build requests.

    Length and ordinary multi-step wording intentionally do not count. A request
    needs both a project/build scope and either several independent delivery
    concerns or a genuinely substantial checklist.
    """
    text = str(message or "").strip()
    if not text:
        return False
    if not (
        constants._PLAN_PROJECT_SCOPE_RE.search(text)
        and constants._PLAN_BUILD_INTENT_RE.search(text)
    ):
        return False

    strong_signals = sum(
        bool(pattern.search(text)) for pattern in constants._PLAN_COMPLEXITY_SIGNAL_RES
    )
    checklist_items = len(constants._PLAN_CHECKLIST_ITEM_RE.findall(text))
    return (
        strong_signals >= 3
        or (strong_signals >= 2 and checklist_items >= 4)
        or checklist_items >= 6
    )


def _resolve_plan_mode(plan_mode: object, message: str) -> tuple[bool, str]:
    """Resolve manual Plan Mode before considering the conservative fallback."""
    if _coerce_plan_mode(plan_mode):
        return True, "manual"
    if _is_exceptionally_complex_project_request(message):
        return True, "auto"
    return False, "off"


def _read_env_file(env_file: Path) -> dict:
    settings = {}
    if env_file.exists():
        with open(env_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    settings[key.strip()] = value.strip()
    return settings


def _write_env_file(env_file: Path, settings: dict) -> None:
    """Write the runtime settings back to the project root .env file."""
    existing_settings = _read_env_file(env_file)
    env_key_map = {
        "API_BASE_URL": "api_base_url",
        "API_KEY": "api_key",
        "API_MODEL": "api_model",
        "REASONING_EFFORT": "reasoning_effort",
        "MODEL_SUPPORTS_VISION": "supports_vision",
        "TAVILY_API_KEY": "tavily_api_key",
        "CUSTOM_SYSTEM_PROMPT": "custom_system_prompt",
        "MAX_STEPS": "max_steps",
        "MAX_TOKENS": "max_tokens",
        "CONTEXT_WINDOW": "context_window",
        "MAX_WEB_SEARCHES": "max_web_searches",
        "AUTO_COMPACT_THRESHOLD_PERCENT": "auto_compact_threshold_percent",
    }
    # 数值型设置留空时回退到默认值，避免写出 CONTEXT_WINDOW= 导致下次启动崩溃
    numeric_defaults = {
        "MAX_STEPS": "100",
        "MAX_TOKENS": "50000",
        "CONTEXT_WINDOW": "256000",
        "MAX_WEB_SEARCHES": "8",
        "AUTO_COMPACT_THRESHOLD_PERCENT": "85",
    }
    ordered_keys = list(env_key_map.keys())

    for env_key, setting_key in env_key_map.items():
        if setting_key in settings:
            value = str(settings.get(setting_key, ""))
            if env_key == "CUSTOM_SYSTEM_PROMPT":
                # 多行提示词在 .env 中以 \n 转义存储
                value = value.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\n")
            else:
                value = value.replace("\r", "").replace("\n", "")
            if not value.strip() and env_key in numeric_defaults:
                value = numeric_defaults[env_key]
            existing_settings[env_key] = value

    env_file.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=env_file.parent, delete=False
        ) as f:
            temp_path = Path(f.name)
            for key in ordered_keys:
                f.write(f"{key}={existing_settings.get(key, '')}\n")

            for key, value in existing_settings.items():
                if key not in env_key_map:
                    f.write(f"{key}={value}\n")
        temp_path.replace(env_file)
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()


def _resolve_within(base: Path, *parts: str) -> Path:
    """Resolve user-provided path parts without allowing directory traversal."""
    base = base.resolve()
    candidate = base.joinpath(*parts).resolve()
    if candidate != base and base not in candidate.parents:
        raise ValueError("Path is outside the allowed directory")
    return candidate


def _workspace_folder(folder: str) -> Path:
    """Return an allowlisted workspace folder exposed by the desktop UI."""
    if folder not in {"output", "temp"}:
        raise ValueError("Unknown workspace folder")
    return _resolve_within(constants.DATA_ROOT / "workspace", folder)


def _project_for_conversation(conversation: dict) -> dict | None:
    """Return the persisted project binding for one task, if any."""
    project_id = str(conversation.get("project_id") or "").strip()
    if not project_id:
        return None
    try:
        return runtime.project_store.load(project_id)
    except ValueError:
        return {
            "id": project_id,
            "name": "项目不可用",
            "root_path": "",
            "instructions": "",
            "available": False,
        }


def _redact_embedded_media_data(content: str) -> str:
    """Keep large inline media payloads out of persisted conversation text."""
    return constants._EMBEDDED_MEDIA_DATA_RE.sub(
        "[已省略 Base64 媒体数据，请改用文件路径或 HTTP(S) 地址]",
        str(content or ""),
    )


def _chat_media_roots(conversation_id: str = "") -> list[Path]:
    """Return local roots whose media may be shown in one desktop task."""
    roots = [
        constants.DATA_ROOT / "workspace" / "output",
        constants.DATA_ROOT / "workspace" / "temp",
    ]
    if conversation_id:
        try:
            conversation = runtime.conversation_store.load(str(conversation_id))
        except (RuntimeError, ValueError):
            conversation = None
        project = _project_for_conversation(conversation) if conversation else None
        project_path = str((project or {}).get("root_path", "")).strip()
        if project and project.get("available") and project_path:
            roots.insert(0, Path(project_path).expanduser())

    resolved_roots = []
    for root in roots:
        resolved = root.resolve(strict=False)
        if resolved not in resolved_roots:
            resolved_roots.append(resolved)
    return resolved_roots


def _resolve_chat_media_file(raw_path: str, conversation_id: str = "") -> tuple[Path, str]:
    """Resolve a local image or video path without following escapes.

    Absolute paths may point anywhere on disk; relative paths must stay
    inside the active task roots. Only image/video files are accepted.
    """
    source = str(raw_path or "").strip()
    if not source or "\x00" in source:
        raise ValueError("Media path is invalid")
    if source.lower().startswith("file://"):
        parsed = urlsplit(source)
        if parsed.netloc not in {"", "localhost"}:
            raise ValueError("Remote file URLs are not supported")
        source = unquote(parsed.path)
    elif re.match(r"^[a-z][a-z0-9+.-]*:", source, flags=re.IGNORECASE):
        raise ValueError("Only local media paths are accepted by this endpoint")

    roots = _chat_media_roots(conversation_id)
    requested = Path(source).expanduser()
    requested_is_absolute = requested.is_absolute()
    candidates = [requested] if requested_is_absolute else []
    if not requested_is_absolute:
        candidates.extend(root / requested for root in roots)
        candidates.append(constants.PROJECT_ROOT / requested)

    for candidate in candidates:
        try:
            resolved = candidate.resolve(strict=True)
        except OSError:
            continue
        if not resolved.is_file():
            continue
        if not requested_is_absolute and not any(
            resolved == root or root in resolved.parents for root in roots
        ):
            continue
        mime_type = constants.CHAT_MEDIA_MIME_TYPES.get(resolved.suffix.lower())
        if not mime_type:
            guessed_type, _encoding = mimetypes.guess_type(resolved.name)
            if guessed_type and guessed_type.startswith(("image/", "video/")):
                mime_type = guessed_type
        if mime_type not in constants.CHAT_MEDIA_MIME_TYPES.values():
            raise ValueError("Unsupported chat media type")
        return resolved, mime_type
    raise ValueError("Media path is outside the active task or unavailable")


def _project_unavailable_error(conversation: dict) -> str:
    """Explain why a project task cannot currently execute."""
    project = _project_for_conversation(conversation)
    if not project:
        return ""
    root_path = str(project.get("root_path", "")).strip()
    if not project.get("available") or not root_path or not Path(root_path).is_dir():
        return "项目目录当前不可用，请在项目设置中重新绑定有效目录"
    return ""


def _read_project_context(project: dict | None) -> str:
    """Build bounded project-level context from durable instructions and files."""
    if not project:
        return "当前任务不属于项目，使用 JCodex 默认工作目录。"
    root_path = Path(str(project.get("root_path", ""))).expanduser()
    sections = [
        f"项目名称: {project.get('name', root_path.name)}",
        f"项目根目录: {root_path}",
    ]
    instructions = str(project.get("instructions", "")).strip()
    if instructions:
        sections.append(f"项目长期说明:\n{instructions[:12000]}")

    remaining = 30000
    for relative_path in PROJECT_CONTEXT_FILES:
        path = root_path / relative_path
        if not path.is_file() or remaining <= 0:
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        content = content[: min(12000, remaining)].strip()
        if not content:
            continue
        sections.append(f"项目文件 {relative_path}:\n{content}")
        remaining -= len(content)
    return "\n\n".join(sections)


def _memory_store_for_conversation(conversation: dict) -> MemoryStore:
    """Resolve the long-term memory scope for a persisted desktop task."""
    conversation_id = str(conversation.get("id", "") or "")
    if not conversation_id:
        raise ValueError("Conversation id is required for memory storage")
    project = _project_for_conversation(conversation)
    root_path = str((project or {}).get("root_path", "")).strip()
    project_root = Path(root_path).expanduser().resolve() if root_path else None
    if project and project.get("available") and project_root and project_root.is_dir():
        scope_path = project_root
    else:
        scope_path = runtime.conversation_store.memory_dir(conversation_id)
    return MemoryStore(
        constants.DATA_ROOT / "workspace" / "memory", scope_path, include_global=False
    )


def _valid_long_term_memory_scope_paths() -> set[Path]:
    """Return every task, project, or CLI scope that must survive cleanup."""
    scopes = {constants.PROJECT_ROOT.resolve()}
    projects = {
        str(project.get("id", "")): project
        for project in runtime.project_store.list().get("projects", [])
        if str(project.get("id", ""))
    }
    for project in projects.values():
        root_path = str(project.get("root_path", "") or "").strip()
        if root_path:
            scopes.add(Path(root_path).expanduser().resolve(strict=False))
    for conversation in runtime.conversation_store.list().get("conversations", []):
        conversation_id = str(conversation.get("id", "") or "")
        if not conversation_id:
            continue
        project = projects.get(str(conversation.get("project_id", "") or ""))
        project_root = str((project or {}).get("root_path", "") or "").strip()
        if project and project.get("available") and project_root:
            scopes.add(Path(project_root).expanduser().resolve(strict=False))
        else:
            scopes.add(runtime.conversation_store.memory_dir(conversation_id).resolve())
    return scopes


def _cleanup_orphaned_long_term_memory() -> dict:
    """Reclaim long-term indexes left by tasks/projects deleted in old builds."""
    try:
        return MemoryStore.prune_orphaned_scopes(
            constants.DATA_ROOT / "workspace" / "memory",
            _valid_long_term_memory_scope_paths(),
        )
    except OSError as exc:
        return {
            "removed_scopes": [],
            "removed_bytes": 0,
            "preserved_scopes": [],
            "errors": [{"scope": "", "error": str(exc)}],
        }


def _decode_attachment_data(data_url: str) -> tuple:
    """Decode one strict base64 data URL and return its declared MIME type."""
    if (
        not isinstance(data_url, str)
        or not data_url.lower().startswith("data:")
        or "," not in data_url
    ):
        raise ValueError("Invalid attachment data")
    header, encoded = data_url.split(",", 1)
    header_parts = header[5:].split(";")
    declared_mime = header_parts[0].strip().lower()
    parameters = {part.strip().lower() for part in header_parts[1:]}
    if not declared_mime or "base64" not in parameters:
        raise ValueError("Attachment must use base64 encoding")
    max_encoded_length = ((constants.MAX_ATTACHMENT_BYTES + 2) // 3) * 4 + 4
    if len(encoded) > max_encoded_length:
        raise ValueError("Attachment exceeds the 12 MB limit")
    try:
        return declared_mime, base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise ValueError("Attachment base64 is invalid") from exc


def _detect_image_mime(content: bytes) -> str | None:
    """Detect supported image types from their signatures, not file names."""
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(content) >= 12 and content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "image/webp"
    return None


def _resolve_attachment_image_mime(
    name: str, browser_mime: str, data_mime: str, content: bytes
) -> str | None:
    """Validate image declarations against the actual bytes."""
    browser_mime = str(browser_mime or "").split(";", 1)[0].strip().lower()
    data_mime = str(data_mime or "").split(";", 1)[0].strip().lower()
    suffix = Path(name).suffix.lower()
    suffix_mime = constants.IMAGE_SUFFIX_MIME_TYPES.get(suffix)
    actual_mime = _detect_image_mime(content)
    declared_image_mimes = {mime for mime in (browser_mime, data_mime) if mime.startswith("image/")}
    if suffix_mime:
        declared_image_mimes.add(suffix_mime)
    unsupported = declared_image_mimes - constants.SUPPORTED_IMAGE_MIME_TYPES
    if unsupported:
        raise ValueError(f"{name} 的图片格式不受支持，仅支持 PNG、JPEG 和 WebP")
    if suffix in constants.UNSUPPORTED_IMAGE_SUFFIXES:
        raise ValueError(f"{name} 的图片格式不受支持，仅支持 PNG、JPEG 和 WebP")
    if not actual_mime:
        if declared_image_mimes:
            raise ValueError(f"{name} 的图片内容无效或与声明格式不一致")
        return None
    if (
        data_mime != actual_mime
        or (browser_mime and browser_mime != actual_mime)
        or (suffix_mime and suffix_mime != actual_mime)
    ):
        raise ValueError(f"{name} 的 MIME 类型、扩展名与图片内容不一致")
    return actual_mime


def _attachment_declares_image(attachment) -> bool:
    if not isinstance(attachment, dict):
        return False
    name = Path(str(attachment.get("name", ""))).name
    browser_mime = str(attachment.get("type", "")).split(";", 1)[0].strip().lower()
    return (
        browser_mime.startswith("image/")
        or Path(name).suffix.lower() in constants.IMAGE_SUFFIX_MIME_TYPES
    )


def _attachment_is_directory_reference(attachment) -> bool:
    """Return whether an attachment represents a dropped local folder."""
    return (
        isinstance(attachment, dict)
        and str(attachment.get("kind", "")).strip().lower() == "directory_reference"
    )


def _resolve_reference_folder(attachment: dict) -> Path:
    """Validate a task-scoped local folder reference from the desktop UI."""
    raw_path = str(attachment.get("path", "")).strip()
    if not raw_path:
        raise ValueError("参考文件夹路径为空")
    path = Path(raw_path).expanduser().resolve(strict=True)
    if not path.is_dir():
        raise ValueError("参考路径必须是文件夹")
    return path


def _prepare_attachments(attachments, message_id: int, conversation_id: str, read_tool) -> tuple:
    if not attachments:
        return "", [], [], []
    if not isinstance(attachments, list):
        raise ValueError("附件参数格式错误")
    if len(attachments) > constants.MAX_ATTACHMENT_COUNT:
        raise ValueError(f"最多上传 {MAX_ATTACHMENT_COUNT} 个附件")

    total_bytes = 0
    upload_dir = _resolve_within(
        constants.DATA_ROOT / "workspace" / "temp", "uploads", str(message_id)
    )
    sections = []
    metadata = []
    read_results = []
    task_images = []
    saved_asset_ids = []
    try:
        for index, attachment in enumerate(attachments, start=1):
            if not isinstance(attachment, dict):
                raise ValueError(f"第 {index} 个附件格式错误")
            name = Path(str(attachment.get("name", f"attachment-{index}"))).name
            if _attachment_is_directory_reference(attachment):
                reference_path = _resolve_reference_folder(attachment)
                metadata.append(
                    {
                        "name": reference_path.name or name or "参考文件夹",
                        "size": 0,
                        "type": "inode/directory",
                        "path": str(reference_path),
                        "success": True,
                        "error": "",
                        "parse_mode": "directory_reference",
                        "kind": "directory_reference",
                    }
                )
                continue
            data_mime, content = _decode_attachment_data(attachment.get("data", ""))
            if len(content) > constants.MAX_ATTACHMENT_BYTES:
                raise ValueError(f"{name} 超过 12 MB")
            total_bytes += len(content)
            if total_bytes > constants.MAX_ATTACHMENT_TOTAL_BYTES:
                raise ValueError("附件总大小超过 30 MB")

            image_mime = _resolve_attachment_image_mime(
                name, attachment.get("type", ""), data_mime, content
            )
            if image_mime:
                asset_id = runtime.conversation_store.save_attachment(
                    conversation_id, message_id, image_mime, content
                )
                saved_asset_ids.append(asset_id)
                image_record = {
                    "name": name,
                    "size": len(content),
                    "type": image_mime,
                    "success": True,
                    "error": "",
                    "parse_mode": "image_view",
                    "asset_id": asset_id,
                    "path": str(
                        runtime.conversation_store.attachment_path(conversation_id, asset_id)
                    ),
                }
                metadata.append(image_record)
                task_images.append(image_record)
                continue

            upload_dir.mkdir(parents=True, exist_ok=True)
            target = _resolve_within(upload_dir, name)
            if target.exists():
                target = _resolve_within(upload_dir, f"{target.stem}-{index}{target.suffix}")
            target.write_bytes(content)
            text = read_tool("read", {"filePath": str(target)}).strip()
            if len(text) > 50000:
                text = text[:50000] + "\n\n[Read 输出过长，已截断]"
            success = not text.startswith("Error:")
            metadata.append(
                {
                    "name": name,
                    "size": len(content),
                    "type": str(attachment.get("type", "") or data_mime),
                    "path": str(target),
                    "success": success,
                    "error": "" if success else text,
                    "parse_mode": "read",
                }
            )
            read_results.append({"name": name, "content": text})
            sections.append(
                f'<attachment index="{index}" name="{name}" path="{target}">\n{text or "[Read 未返回内容]"}\n</attachment>'
            )
    except Exception:
        for asset_id in saved_asset_ids:
            runtime.conversation_store.delete_attachment(conversation_id, asset_id)
        raise

    context = "\n\n".join(sections)
    if len(context) > constants.MAX_ATTACHMENT_CONTEXT_CHARS:
        context = context[: constants.MAX_ATTACHMENT_CONTEXT_CHARS] + "\n\n[附件上下文已截断]"
    return context, metadata, read_results, task_images


def _merge_task_images(*image_groups) -> list[dict]:
    """Deduplicate trusted image records before registering one task allowlist."""
    merged = {}
    for images in image_groups:
        for image in images or []:
            if not isinstance(image, dict):
                continue
            path = str(image.get("path", "")).strip()
            if not path:
                continue
            key = str(image.get("asset_id", "")).strip() or path
            merged[key] = dict(image)
    return list(merged.values())


def _append_image_manifest(message: str, image_paths: list[str]) -> str:
    """Tell the model which conversation images it may inspect this task run."""
    if os.getenv("MODEL_SUPPORTS_VISION", "true").strip().lower() in {"0", "false", "no", "off"}:
        return message
    paths = [str(path).strip() for path in image_paths if str(path).strip()]
    if not paths:
        return message
    manifest = "\n".join(f"- {path}" for path in paths)
    return (
        f"{message}\n\n"
        "本会话中可供当前任务查看的图片已保存为受控本地文件。图片内容未直接写入上下文；"
        "需要视觉信息时，必须调用 view_image。除以下完整路径外，也可查看 Temp 或 Output 目录内已知的 PNG、JPEG 或 WebP 路径：\n"
        f"{manifest}"
    )


def _append_reference_folder_manifest(message: str, folder_paths: list[str]) -> str:
    """Expose explicitly dropped folders as task-scoped local working folders."""
    paths = [str(path).strip() for path in folder_paths if str(path).strip()]
    if not paths:
        return message
    manifest = "\n".join(f"- {path}" for path in paths)
    return (
        f"{message}\n\n"
        "用户为本次任务拖入了以下本地文件夹。这些目录已由用户明确放入任务范围，"
        "可以读取、搜索、创建、编辑、移动或删除其中的文件，也可以作为 Shell 工作目录；"
        "也可以直接作为 project_preview 的工作目录。所有修改、命令和预览启动仍遵循普通审批规则：\n"
        f"{manifest}"
    )


def _jcchat_multimodal_message(text: str, images: list[dict]) -> list:
    """Build a multimodal user-message content list with images embedded."""
    content_blocks: list[dict] = [{"type": "text", "text": text}]
    name_lines: list[str] = []
    for image in images or []:
        if not isinstance(image, dict):
            continue
        path = str(image.get("path", "") or "").strip()
        if not path:
            continue
        try:
            raw = Path(path).read_bytes()
        except OSError:
            continue
        mime = str(image.get("type", "") or "image/png")
        encoded = base64.b64encode(raw).decode("ascii")
        content_blocks.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{encoded}"},
            }
        )
        name_lines.append(Path(str(image.get("name", path))).name)
    if name_lines:
        content_blocks.insert(
            1,
            {
                "type": "text",
                "text": "用户上传了以下图片，已随本条消息以多模态内容提供：\n"
                + "\n".join(f"- {name}" for name in name_lines),
            },
        )
    return content_blocks


def _jcchat_content_text(content) -> str:
    """Flatten a user-message content value for token estimation and history."""
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(str(block.get("text", "") or ""))
                elif block.get("type") == "image_url":
                    parts.append("[图片]")
        return " ".join(part for part in parts if part)
    return str(content or "")


def _validate_runtime_settings(settings: dict) -> dict:
    """Validate and normalize settings received from the desktop form."""
    normalized = dict(settings or {})
    api_base_url = str(normalized.get("api_base_url", "")).strip()
    api_model = str(normalized.get("api_model", "")).strip()
    if not api_base_url.startswith(("http://", "https://")):
        raise ValueError("API Base URL must start with http:// or https://")
    if not api_model:
        raise ValueError("API Model cannot be empty")

    numeric_rules = {
        "max_steps": (1, 200, 100),
        "max_tokens": (1000, 200000, 50000),
        "context_window": (8000, 2000000, 256000),
        "max_web_searches": (0, 100, 8),
        "auto_compact_threshold_percent": (1, 100, 85),
    }
    for key, (minimum, maximum, default) in numeric_rules.items():
        raw_value = normalized.get(key, default)
        try:
            value = int(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{key} must be an integer") from exc
        if not minimum <= value <= maximum:
            raise ValueError(f"{key} must be between {minimum} and {maximum}")
        normalized[key] = str(value)

    normalized["api_base_url"] = api_base_url
    normalized["api_model"] = api_model
    vision = str(normalized.get("supports_vision", "true")).strip().lower()
    normalized["supports_vision"] = (
        "true"
        if vision
        in {
            "1",
            "true",
            "yes",
            "on",
        }
        else "false"
    )
    custom_prompt = str(normalized.get("custom_system_prompt", "") or "")
    normalized["custom_system_prompt"] = custom_prompt.strip("\r\n").strip()
    return normalized


__all__ = [
    "_append_image_manifest",
    "_append_reference_folder_manifest",
    "_attachment_declares_image",
    "_attachment_is_directory_reference",
    "_chat_media_roots",
    "_cleanup_orphaned_long_term_memory",
    "_coerce_plan_mode",
    "_decode_attachment_data",
    "_detect_image_mime",
    "_is_exceptionally_complex_project_request",
    "_jcchat_content_text",
    "_jcchat_multimodal_message",
    "_memory_store_for_conversation",
    "_merge_task_images",
    "_multi_agent_mode_instruction",
    "_plan_mode_instruction",
    "_platform_instruction",
    "_prepare_attachments",
    "_project_for_conversation",
    "_project_unavailable_error",
    "_read_env_file",
    "_read_project_context",
    "_redact_embedded_media_data",
    "_resolve_attachment_image_mime",
    "_resolve_chat_media_file",
    "_resolve_plan_mode",
    "_resolve_reference_folder",
    "_resolve_within",
    "_seed_bundled_skill_files",
    "_short_term_compression_lock",
    "_short_term_memory_lock",
    "_tool_display_params",
    "_valid_long_term_memory_scope_paths",
    "_validate_runtime_settings",
    "_voice_mode_instruction",
    "_workspace_folder",
    "_write_env_file",
]
