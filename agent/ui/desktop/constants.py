"""JCodex desktop UI - constants and derived paths.

Extracted from the legacy monolithic ``main.py``; values here are shared
by every desktop module. Keep this module free of mutable state.
"""

import os
import re
import shutil
import sys
from pathlib import Path

from agent.core.prompt_helpers import (
    _PLAN_POLICIES,
)

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
DATA_ROOT = Path(os.getenv("JCODEX_DATA_DIR", "") or PROJECT_ROOT).expanduser().resolve()
DATA_ROOT.mkdir(parents=True, exist_ok=True)

MAX_ATTACHMENT_COUNT = 8
MAX_ATTACHMENT_BYTES = 12 * 1024 * 1024
MAX_ATTACHMENT_TOTAL_BYTES = 30 * 1024 * 1024
MAX_ATTACHMENT_CONTEXT_CHARS = 120000
MAX_REUSABLE_CONVERSATION_IMAGES = 24
MAX_SKILL_IMPORT_FILES = 512
MAX_SKILL_IMPORT_BYTES = 30 * 1024 * 1024
MAX_SKILL_IMPORT_FILE_BYTES = 12 * 1024 * 1024
BUILTIN_SKILL_NAMES = frozenset(
    {
        "docx",
        "frontend-design",
        "pptx",
        "project-setup",
        "python",
        "xlsx",
    }
)
MAX_MODIFIED_FILE_TEXT_BYTES = 1024 * 1024
MAX_MODIFIED_FILE_DIFF_LINES = 1200
MAX_MODIFIED_TASK_DIFF_LINES = 4000
MAX_MODIFIED_DIFF_LINE_CHARS = 3000
MAX_MODIFIED_FILE_DIFF_CHARS = 600000
MEMORY_FILE_NAMES = {
    "execution_history": "execution_history.md",
    "accumulated_compression": "accumulated_compression.md",
    # This is the exact <memory-context> block appended to the system prompt.
    "memory_context": "memory_context.md",
}
SUPPORTED_IMAGE_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
}
_TOOL_DISPLAY_PARAM_KEYS = {
    "action",
    "description",
    "destination",
    "entry_path",
    "filePath",
    "file_path",
    "filename",
    "include",
    "input_path",
    "minutes",
    "name",
    "output_path",
    "path",
    "pattern",
    "preview_id",
    "query",
    "skill_name",
    "source",
    "url",
    "workdir",
}
_TOOL_DISPLAY_PARAM_MAX_CHARS = 512
_MULTI_AGENT_TOOL_NAMES = {
    "spawn_agent",
    "send_agent_message",
    "publish_agent_artifact",
    "get_agent_collaboration",
    "wait_agents",
    "list_agents",
    "cancel_agent",
}
_SUBAGENT_COLLABORATION_TOOLS = {
    "send_agent_message",
    "publish_agent_artifact",
    "get_agent_collaboration",
}
_SUBAGENT_READ_TOOLS = {
    "view_image",
    "read",
    "glob",
    "grep",
    "websearch",
    "codesearch",
    "read_url",
    "load_skill",
    "web_search",
    "web_fetch",
    "list_dir",
    "memory_search",
    "memory_get",
}
_PLAN_PROJECT_SCOPE_RE = re.compile(
    r"(?:项目|系统|平台|应用|网站|站点|产品|游戏|服务|工具|仪表盘|后台|"
    r"project|application|app|website|site|platform|system|dashboard|service|tool)",
    re.IGNORECASE,
)
_PLAN_BUILD_INTENT_RE = re.compile(
    r"(?:开发|构建|实现|搭建|设计|改造|迁移|重构|制作|创建|"
    r"build|create|develop|implement|design|migrate|refactor)",
    re.IGNORECASE,
)
_PLAN_COMPLEXITY_SIGNAL_RES = (
    re.compile(
        r"(?:架构|微服务|权限|认证|授权|architecture|microservice|"
        r"authentication|authorization)",
        re.IGNORECASE,
    ),
    re.compile(r"(?:迁移|重构|改造|migration|migrate|refactor)", re.IGNORECASE),
    re.compile(
        r"(?:全栈|前后端|full[ -]?stack|frontend.*backend|backend.*frontend)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:多页面|多模块|多端|多个页面|多个模块|multi[ -]?(?:page|module)|"
        r"multiple[ -]?(?:page|module))",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:数据库|数据模型|缓存|database|postgres(?:ql)?|mysql|redis|orm)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:部署|上线|容器|持续集成|测试套件|集成测试|端到端测试|"
        r"deploy(?:ment)?|docker|kubernetes|ci/?cd|test(?:ing)?|e2e)",
        re.IGNORECASE,
    ),
)
_PLAN_CHECKLIST_ITEM_RE = re.compile(r"(?:^|\n)\s*(?:[-*•]|\d{1,2}[.)、])\s+\S+")

_PROJECT_FOLDER_PICKER_TIMEOUT_SECONDS = 10 * 60
_SKILL_IMPORT_IGNORED_PARTS = {".git", "__pycache__", "node_modules"}
_MODIFIED_FILE_TOOL_PATHS = {
    "write": ("path",),
    "edit": ("filePath",),
    "generate_pdf": ("output_path",),
}
# Rollback only tracks file tools the model can actually call today.
_ROLLBACK_FILE_TOOL_PATHS = {
    "write": ("path",),
    "edit": ("filePath",),
    "generate_pdf": ("output_path",),
}
# Claude Code-style rollback: approved file mutations keep a before-state on
# disk under workspace/rollback so the user can undo a completed task.
ROLLBACK_ROOT = DATA_ROOT / "workspace" / "rollback"
# Migrate snapshots stored under the old temp location.
_LEGACY_ROLLBACK_ROOT = DATA_ROOT / "workspace" / "temp" / "rollback"
if _LEGACY_ROLLBACK_ROOT.exists() and not ROLLBACK_ROOT.exists():
    try:
        ROLLBACK_ROOT.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(_LEGACY_ROLLBACK_ROOT), str(ROLLBACK_ROOT))
        print(f"[rollback] migrated snapshots to {ROLLBACK_ROOT}")
    except Exception as exc:
        print(f"[rollback] migrate legacy snapshots failed: {exc}")
MAX_ROLLBACK_FILE_BYTES = 256 * 1024 * 1024
IMAGE_SUFFIX_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}
UNSUPPORTED_IMAGE_SUFFIXES = {
    ".avif",
    ".bmp",
    ".gif",
    ".heic",
    ".heif",
    ".svg",
    ".tif",
    ".tiff",
}
CHAT_MEDIA_MIME_TYPES = {
    ".avif": "image/avif",
    ".gif": "image/gif",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".m4v": "video/mp4",
    ".mov": "video/quicktime",
    ".mp4": "video/mp4",
    ".ogv": "video/ogg",
    ".webm": "video/webm",
}
_EMBEDDED_MEDIA_DATA_RE = re.compile(
    r"data:(?:image|video)/[a-z0-9.+-]+;base64,[a-z0-9+/=_-]{256,}",
    flags=re.IGNORECASE,
)
_EEL_SESSION_COOKIE = "jcodex_eel_session"
CONVERSATION_ROOT = DATA_ROOT / "workspace" / "conversations"

PROJECT_STORE_ROOT = DATA_ROOT / "workspace" / "projects"

_EDGE_TTS_TEXT_LIMIT = 2000


__all__ = [
    "BUILTIN_SKILL_NAMES",
    "CHAT_MEDIA_MIME_TYPES",
    "CONVERSATION_ROOT",
    "DATA_ROOT",
    "IMAGE_SUFFIX_MIME_TYPES",
    "MAX_ATTACHMENT_BYTES",
    "MAX_ATTACHMENT_CONTEXT_CHARS",
    "MAX_ATTACHMENT_COUNT",
    "MAX_ATTACHMENT_TOTAL_BYTES",
    "MAX_MODIFIED_DIFF_LINE_CHARS",
    "MAX_MODIFIED_FILE_DIFF_CHARS",
    "MAX_MODIFIED_FILE_DIFF_LINES",
    "MAX_MODIFIED_FILE_TEXT_BYTES",
    "MAX_MODIFIED_TASK_DIFF_LINES",
    "MAX_REUSABLE_CONVERSATION_IMAGES",
    "MAX_ROLLBACK_FILE_BYTES",
    "MAX_SKILL_IMPORT_BYTES",
    "MAX_SKILL_IMPORT_FILES",
    "MAX_SKILL_IMPORT_FILE_BYTES",
    "MEMORY_FILE_NAMES",
    "PROJECT_ROOT",
    "PROJECT_STORE_ROOT",
    "ROLLBACK_ROOT",
    "SUPPORTED_IMAGE_MIME_TYPES",
    "UNSUPPORTED_IMAGE_SUFFIXES",
    "_EDGE_TTS_TEXT_LIMIT",
    "_EEL_SESSION_COOKIE",
    "_EMBEDDED_MEDIA_DATA_RE",
    "_LEGACY_ROLLBACK_ROOT",
    "_MODIFIED_FILE_TOOL_PATHS",
    "_MULTI_AGENT_TOOL_NAMES",
    "_PLAN_BUILD_INTENT_RE",
    "_PLAN_CHECKLIST_ITEM_RE",
    "_PLAN_COMPLEXITY_SIGNAL_RES",
    "_PLAN_POLICIES",
    "_PLAN_PROJECT_SCOPE_RE",
    "_PROJECT_FOLDER_PICKER_TIMEOUT_SECONDS",
    "_ROLLBACK_FILE_TOOL_PATHS",
    "_SKILL_IMPORT_IGNORED_PARTS",
    "_SUBAGENT_COLLABORATION_TOOLS",
    "_SUBAGENT_READ_TOOLS",
    "_TOOL_DISPLAY_PARAM_KEYS",
    "_TOOL_DISPLAY_PARAM_MAX_CHARS",
]
