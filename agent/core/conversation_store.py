"""Persistent desktop conversations with isolated per-task memory."""

import builtins
import json
import shutil
import threading
import uuid
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_IMAGE_ATTACHMENT_SUFFIXES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}

class ConversationStore:
    """Store desktop task metadata, UI events, and task-local memory paths."""

    def __init__(self, root_dir: Path):
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.root_dir / "index.json"
        self._lock = threading.RLock()
        self._ensure_index()

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    def _ensure_index(self) -> None:
        with self._lock:
            index = self._read_index()
            if not index.get("conversations"):
                conversation = self._new_conversation("新任务")
                index = {
                    "active_id": conversation["id"],
                    "conversations": [self._metadata(conversation)],
                }
                self._write_index(index)
                return

            changed = False
            normalized_items = []
            for item in index.get("conversations", []):
                conversation_id = str(item.get("id", ""))
                conversation = self._read_json(
                    self._conversation_file(conversation_id), None
                )
                if isinstance(conversation, dict):
                    before = dict(conversation)
                    self._normalize_split_state(conversation)
                    self._ensure_split_memory_fork(conversation)
                    self._normalize_completion_state(conversation)
                    if conversation != before:
                        self._write_json(
                            self._conversation_file(conversation_id), conversation
                        )
                    metadata = self._metadata(conversation)
                else:
                    metadata = dict(item)
                    self._normalize_completion_state(metadata)
                normalized_items.append(metadata)
                changed = changed or metadata != item

            merged_items = self._merge_empty_untitled(
                normalized_items, index.get("active_id")
            )
            if len(merged_items) != len(normalized_items):
                changed = True
            index["conversations"] = merged_items
            normalized_items = merged_items
            visible_items = [
                item for item in normalized_items if not item.get("is_split_task")
            ]
            if not index.get("active_id") or not any(
                item.get("id") == index.get("active_id")
                for item in visible_items
            ):
                index["active_id"] = (
                    visible_items[0]["id"]
                    if visible_items
                    else normalized_items[0]["id"]
                )
                changed = True
            if changed:
                self._write_index(index)

    def _merge_empty_untitled(
        self, items: list[dict[str, Any]], active_id: str | None
    ) -> list[dict[str, Any]]:
        """Collapse duplicate auto-created empty ``新任务`` conversations.

        Only conversations that were never used (no messages, no project, not a
        split task and not archived) are eligible, so user content is never
        deleted.  The currently active conversation wins, otherwise the newest.
        """
        empty = [
            item
            for item in items
            if str(item.get("title", "")) == "新任务"
            and item.get("message_count", 0) == 0
            and not item.get("project_id")
            and not item.get("is_split_task")
            and not item.get("archived")
        ]
        if len(empty) <= 1:
            return items
        empty.sort(key=self._index_sort_time, reverse=True)
        active_id = str(active_id or "")
        keep_id = (
            active_id
            if any(str(item.get("id", "")) == active_id for item in empty)
            else empty[0]["id"]
        )
        removed_ids = {
            str(item.get("id", ""))
            for item in empty
            if str(item.get("id", "")) != keep_id
        }
        for conversation_id in removed_ids:
            with suppress(ValueError):
                shutil.rmtree(
                    self._conversation_dir(conversation_id), ignore_errors=True
                )
        return [
            item for item in items if str(item.get("id", "")) not in removed_ids
        ]

    def _read_json(self, path: Path, default: Any) -> Any:
        try:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            pass
        return default

    def _write_json(self, path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        # 使用唯一临时文件名：并发进程同时写入时不会互相覆盖 .tmp，
        # 避免 os.replace 抛 FileNotFoundError 导致后端崩溃。
        temp_path = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
        temp_path.write_text(
            json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temp_path.replace(path)

    def _read_index(self) -> dict[str, Any]:
        return self._read_json(
            self.index_file, {"active_id": None, "conversations": []}
        )

    def _write_index(self, index: dict[str, Any]) -> None:
        self._write_json(self.index_file, index)

    def _conversation_dir(self, conversation_id: str) -> Path:
        safe_id = str(conversation_id or "")
        if not safe_id or any(char not in "0123456789abcdef-" for char in safe_id):
            raise ValueError("Invalid conversation id")
        path = (self.root_dir / safe_id).resolve()
        if self.root_dir.resolve() not in path.parents:
            raise ValueError("Invalid conversation path")
        return path

    def _conversation_file(self, conversation_id: str) -> Path:
        return self._conversation_dir(conversation_id) / "conversation.json"

    def attachments_dir(self, conversation_id: str) -> Path:
        """Return the private attachment directory for one desktop task."""
        return self._conversation_dir(conversation_id) / "attachments"

    def attachment_path(self, conversation_id: str, asset_id: str) -> Path:
        """Resolve an opaque attachment identifier inside its owning task."""
        safe_asset_id = str(asset_id or "")
        if not safe_asset_id or Path(safe_asset_id).name != safe_asset_id:
            raise ValueError("Invalid attachment id")
        attachment_dir = self.attachments_dir(conversation_id).resolve()
        path = (attachment_dir / safe_asset_id).resolve()
        if attachment_dir not in path.parents:
            raise ValueError("Invalid attachment path")
        return path

    def save_attachment(
        self, conversation_id: str, message_id: int, mime_type: str, content: bytes
    ) -> str:
        """Persist a binary attachment in its private task attachment folder."""
        suffixes = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/webp": ".webp",
        }
        suffix = suffixes.get(str(mime_type or "").lower())
        if not suffix:
            raise ValueError("Unsupported attachment type")
        asset_id = f"{int(message_id)}-{uuid.uuid4().hex}{suffix}"
        path = self.attachment_path(conversation_id, asset_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.parent.chmod(0o700)
        temp_path = path.with_suffix(path.suffix + ".tmp")
        temp_path.write_bytes(content)
        temp_path.chmod(0o600)
        temp_path.replace(path)
        return asset_id

    def read_attachment(self, conversation_id: str, asset_id: str) -> bytes:
        """Read a persisted task attachment by its opaque identifier."""
        path = self.attachment_path(conversation_id, asset_id)
        if not path.is_file():
            raise ValueError("Attachment not found")
        return path.read_bytes()

    def list_image_attachments(
        self, conversation_id: str, limit: int = 24
    ) -> list[dict[str, Any]]:
        """Return recent conversation images with store-derived canonical paths.

        Paths embedded in old messages or memory are never trusted here.  The
        persisted opaque asset ID is resolved back through ``attachment_path``
        so callers can safely re-register images for a new task run.
        """
        try:
            max_items = max(0, int(limit))
        except (TypeError, ValueError):
            max_items = 24
        if max_items == 0:
            return []

        with self._lock:
            conversation = self._load_required(conversation_id)
            images: list[dict[str, Any]] = []
            seen_asset_ids = set()
            for event in reversed(conversation.get("messages", [])):
                if event.get("type") != "user":
                    continue
                attachments = event.get("attachments", [])
                if not isinstance(attachments, list):
                    continue
                for attachment in reversed(attachments):
                    if not isinstance(attachment, dict):
                        continue
                    asset_id = str(attachment.get("asset_id", "")).strip()
                    mime_type = str(attachment.get("type", "")).strip().lower()
                    if (
                        not asset_id
                        or asset_id in seen_asset_ids
                        or mime_type not in _IMAGE_ATTACHMENT_SUFFIXES
                        or attachment.get("success") is False
                    ):
                        continue
                    try:
                        path = self.attachment_path(conversation_id, asset_id)
                        if (
                            not path.is_file()
                            or path.suffix.lower()
                            != _IMAGE_ATTACHMENT_SUFFIXES[mime_type]
                        ):
                            continue
                        size = path.stat().st_size
                    except OSError:
                        continue
                    if size <= 0:
                        continue
                    seen_asset_ids.add(asset_id)
                    images.append(
                        {
                            "asset_id": asset_id,
                            "name": Path(
                                str(attachment.get("name", path.name))
                            ).name
                            or path.name,
                            "path": str(path),
                            "type": mime_type,
                            "size": size,
                            "source_message_id": self._message_id(
                                event.get("message_id")
                            ),
                        }
                    )
                    if len(images) >= max_items:
                        return list(reversed(images))
            return list(reversed(images))

    def delete_attachment(self, conversation_id: str, asset_id: str) -> None:
        """Remove one unreferenced attachment created by a failed upload."""
        path = self.attachment_path(conversation_id, asset_id)
        if path.exists():
            path.unlink()
        attachment_dir = self.attachments_dir(conversation_id)
        if attachment_dir.exists() and not any(attachment_dir.iterdir()):
            attachment_dir.rmdir()

    def _new_conversation(
        self,
        title: str,
        project_id: str | None = None,
        memory_scope_id: str | None = None,
        is_split_task: bool = False,
        parent_conversation_id: str | None = None,
        short_term_memory_id: str | None = None,
        split_conversation_id: str | None = None,
        split_open: bool = False,
        split_pane_width: int = 0,
    ) -> dict[str, Any]:
        now = self._now()
        conversation = {
            "id": str(uuid.uuid4()),
            "title": self._clean_title(title),
            "project_id": self._clean_project_id(project_id),
            "memory_scope_id": self._clean_memory_scope_id(memory_scope_id),
            "is_split_task": bool(is_split_task),
            "parent_conversation_id": self._clean_conversation_id(
                parent_conversation_id
            ),
            "short_term_memory_id": self._clean_conversation_id(
                short_term_memory_id
            ),
            "split_conversation_id": self._clean_conversation_id(
                split_conversation_id
            ),
            "split_open": bool(split_open),
            "split_pane_width": self._clean_split_pane_width(split_pane_width),
            "created_at": now,
            "updated_at": now,
            "last_user_message_at": "",
            "messages": [],
            "unread_completion": False,
            "last_completed_message_id": 0,
            "last_read_message_id": 0,
        }
        self._write_json(self._conversation_file(conversation["id"]), conversation)
        self.memory_dir(conversation["id"]).mkdir(parents=True, exist_ok=True)
        return conversation

    @staticmethod
    def _clean_title(title: str) -> str:
        title = " ".join(str(title or "新任务").split()).strip()
        return (title or "新任务")[:60]

    @staticmethod
    def _clean_project_id(project_id: str | None) -> str | None:
        value = str(project_id or "").strip()
        if not value:
            return None
        if any(char not in "0123456789abcdef-" for char in value):
            raise ValueError("Invalid project id")
        return value

    @staticmethod
    def _clean_memory_scope_id(memory_scope_id: str | None) -> str | None:
        """Validate the opaque identifier used by split ordinary tasks."""
        value = str(memory_scope_id or "").strip()
        if not value:
            return None
        if any(char not in "0123456789abcdef-" for char in value):
            raise ValueError("Invalid memory scope id")
        return value

    @staticmethod
    def _clean_conversation_id(conversation_id: str | None) -> str | None:
        value = str(conversation_id or "").strip()
        if not value:
            return None
        if any(char not in "0123456789abcdef-" for char in value):
            raise ValueError("Invalid conversation id")
        return value

    @staticmethod
    def _clean_split_pane_width(value: Any) -> int:
        try:
            width = int(value or 0)
        except (TypeError, ValueError):
            return 0
        return max(0, min(width, 4000))

    @classmethod
    def _normalize_split_state(cls, conversation: dict[str, Any]) -> None:
        """Migrate split tasks created before the explicit internal-task flag."""
        conversation_id = str(conversation.get("id", "") or "")
        memory_scope_id = cls._clean_memory_scope_id(
            conversation.get("memory_scope_id")
        )
        short_term_memory_id = cls._clean_conversation_id(
            conversation.get("short_term_memory_id")
        )
        inferred_split = bool(
            conversation_id
            and (
                (memory_scope_id and memory_scope_id != conversation_id)
                or (
                    short_term_memory_id
                    and short_term_memory_id != conversation_id
                )
            )
        )
        conversation["is_split_task"] = bool(
            conversation.get("is_split_task", inferred_split)
        )
        parent_id = conversation.get("parent_conversation_id")
        if conversation["is_split_task"] and not parent_id:
            parent_id = short_term_memory_id or memory_scope_id
        conversation["parent_conversation_id"] = cls._clean_conversation_id(
            parent_id
        )
        if conversation["is_split_task"] and not short_term_memory_id:
            # New split tasks own their post-fork memory directory.  A
            # self-reference keeps the persisted retrieval snapshot enabled
            # without resolving back to the parent's live files.
            short_term_memory_id = conversation_id
        elif not conversation["is_split_task"] and short_term_memory_id == conversation_id:
            # Older parents used a redundant self-reference solely because
            # their child shared this directory.  It is no longer needed.
            short_term_memory_id = None
        conversation["short_term_memory_id"] = short_term_memory_id
        conversation["split_conversation_id"] = cls._clean_conversation_id(
            conversation.get("split_conversation_id")
        )
        conversation["split_open"] = bool(conversation.get("split_open", False))
        conversation["split_pane_width"] = cls._clean_split_pane_width(
            conversation.get("split_pane_width", 0)
        )
        if conversation["is_split_task"]:
            conversation["split_conversation_id"] = None
            conversation["split_open"] = False
            conversation["split_pane_width"] = 0

    def _ensure_split_memory_fork(self, conversation: dict[str, Any]) -> bool:
        """Detach a legacy split task from its parent's live memory directory."""
        if not conversation.get("is_split_task"):
            return False
        conversation_id = self._clean_conversation_id(conversation.get("id"))
        if not conversation_id:
            return False
        current_scope = self._clean_conversation_id(
            conversation.get("short_term_memory_id")
        )
        if current_scope == conversation_id:
            return False
        source_id = current_scope or self._clean_conversation_id(
            conversation.get("parent_conversation_id")
        )
        source_dir = self.memory_dir(source_id) if source_id else None
        target_dir = self.memory_dir(conversation_id)
        if source_dir and source_dir != target_dir and source_dir.is_dir():
            shutil.copytree(source_dir, target_dir, dirs_exist_ok=True)
        else:
            target_dir.mkdir(parents=True, exist_ok=True)
        conversation["short_term_memory_id"] = conversation_id
        return True

    @staticmethod
    def _message_id(value: Any) -> int:
        try:
            return max(0, int(value or 0))
        except (TypeError, ValueError):
            return 0

    @classmethod
    def _normalize_completion_state(cls, conversation: dict[str, Any]) -> None:
        """Populate completion fields for both current and legacy conversations."""
        completed_id = cls._message_id(
            conversation.get("last_completed_message_id", 0)
        )
        read_id = cls._message_id(conversation.get("last_read_message_id", 0))
        has_explicit_state = all(
            key in conversation
            for key in (
                "unread_completion",
                "last_completed_message_id",
                "last_read_message_id",
            )
        )
        if "unread_completion" in conversation:
            unread = bool(conversation.get("unread_completion"))
        else:
            unread = completed_id > read_id
        if completed_id and read_id >= completed_id:
            unread = False
        elif completed_id and not unread and not has_explicit_state:
            read_id = completed_id

        conversation["unread_completion"] = unread
        conversation["last_completed_message_id"] = completed_id
        conversation["last_read_message_id"] = read_id

    @staticmethod
    def _metadata(conversation: dict[str, Any]) -> dict[str, Any]:
        ConversationStore._normalize_split_state(conversation)
        ConversationStore._normalize_completion_state(conversation)
        return {
            "id": conversation["id"],
            "title": conversation.get("title", "新任务"),
            "project_id": ConversationStore._clean_project_id(
                conversation.get("project_id")
            ),
            "memory_scope_id": ConversationStore._clean_memory_scope_id(
                conversation.get("memory_scope_id")
            ),
            "is_split_task": bool(conversation.get("is_split_task", False)),
            "parent_conversation_id": ConversationStore._clean_conversation_id(
                conversation.get("parent_conversation_id")
            ),
            "short_term_memory_id": ConversationStore._clean_conversation_id(
                conversation.get("short_term_memory_id")
            ),
            "split_conversation_id": ConversationStore._clean_conversation_id(
                conversation.get("split_conversation_id")
            ),
            "split_open": bool(conversation.get("split_open", False)),
            "split_pane_width": ConversationStore._clean_split_pane_width(
                conversation.get("split_pane_width", 0)
            ),
            "archived": bool(conversation.get("archived", False)),
            "created_at": conversation.get("created_at", ""),
            "updated_at": conversation.get("updated_at", ""),
            "last_user_message_at": conversation.get("last_user_message_at", ""),
            "message_count": len(conversation.get("messages", [])),
            "unread_completion": conversation["unread_completion"],
            "last_completed_message_id": conversation[
                "last_completed_message_id"
            ],
            "last_read_message_id": conversation["last_read_message_id"],
        }

    def _load_required(self, conversation_id: str) -> dict[str, Any]:
        conversation = self._read_json(self._conversation_file(conversation_id), None)
        if not isinstance(conversation, dict):
            raise ValueError("Conversation not found")
        before = dict(conversation)
        self._normalize_split_state(conversation)
        self._ensure_split_memory_fork(conversation)
        self._normalize_completion_state(conversation)
        if conversation != before:
            self._write_json(self._conversation_file(conversation_id), conversation)
        return conversation

    @staticmethod
    def _index_sort_time(item: dict[str, Any]) -> str:
        """Return the recency key for sidebar ordering.

        Only the user's latest message reorders a task; background assistant,
        tool, plan and team events keep the task in place while still touching
        ``updated_at`` for date display. Tasks without a user message yet fall
        back to their creation time so background activity never moves them.
        """
        return str(
            item.get("last_user_message_at")
            or item.get("created_at", "")
            or item.get("updated_at", "")
            or ""
        )

    def _update_index_metadata(self, conversation: dict[str, Any]) -> None:
        index = self._read_index()
        metadata = self._metadata(conversation)
        items = [
            item
            for item in index.get("conversations", [])
            if item.get("id") != conversation["id"]
        ]
        items.append(metadata)
        items.sort(key=self._index_sort_time, reverse=True)
        index["conversations"] = items
        if not index.get("active_id"):
            index["active_id"] = conversation["id"]
        self._write_index(index)

    def list(self) -> dict[str, Any]:
        with self._lock:
            index = self._read_index()
            items = list(index.get("conversations", []))
            items.sort(key=self._index_sort_time, reverse=True)
            return {"active_id": index.get("active_id"), "conversations": items}

    def create(
        self,
        title: str = "新任务",
        project_id: str | None = None,
        memory_scope_id: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            conversation = self._new_conversation(
                title, project_id, memory_scope_id
            )
            index = self._read_index()
            index["active_id"] = conversation["id"]
            index.setdefault("conversations", []).append(self._metadata(conversation))
            index["conversations"].sort(key=self._index_sort_time, reverse=True)
            self._write_index(index)
            return conversation

    def create_split(self, source_conversation_id: str) -> dict[str, Any]:
        """Create or reopen a child task forked from current short-term context."""
        with self._lock:
            source = self._load_required(source_conversation_id)
            if source.get("is_split_task"):
                raise ValueError("Split tasks cannot create nested split tasks")

            child_id = self._clean_conversation_id(
                source.get("split_conversation_id")
            )
            child = None
            if child_id:
                try:
                    candidate = self._load_required(child_id)
                except ValueError:
                    candidate = None
                if (
                    candidate
                    and candidate.get("is_split_task")
                    and candidate.get("parent_conversation_id") == source["id"]
                ):
                    child = candidate

            if child is None:
                for item in self._read_index().get("conversations", []):
                    if (
                        item.get("is_split_task")
                        and item.get("parent_conversation_id") == source["id"]
                    ):
                        try:
                            child = self._load_required(str(item.get("id", "")))
                        except ValueError:
                            child = None
                        if child is not None:
                            break

            if child is not None:
                source["short_term_memory_id"] = None
                source["memory_scope_id"] = None
                source["split_conversation_id"] = child["id"]
                source["split_open"] = True
                child["short_term_memory_id"] = child["id"]
                child["memory_scope_id"] = None
                self._write_json(self._conversation_file(source["id"]), source)
                self._write_json(self._conversation_file(child["id"]), child)
                self._update_index_metadata(source)
                self._update_index_metadata(child)
                return child

            source_memory_dir = self.short_term_memory_dir(source["id"])
            source["short_term_memory_id"] = None
            source["memory_scope_id"] = None
            child = self._new_conversation(
                f"{source.get('title', '新任务')} · 子任务",
                self._clean_project_id(source.get("project_id")),
                None,
                True,
                source["id"],
                None,
            )
            try:
                shutil.copytree(
                    source_memory_dir,
                    self.memory_dir(child["id"]),
                    dirs_exist_ok=True,
                )
            except OSError:
                shutil.rmtree(self._conversation_dir(child["id"]), ignore_errors=True)
                raise
            child["short_term_memory_id"] = child["id"]
            self._write_json(self._conversation_file(child["id"]), child)
            source["split_conversation_id"] = child["id"]
            source["split_open"] = True
            self._write_json(self._conversation_file(source["id"]), source)
            index = self._read_index()
            index["conversations"] = [
                item
                for item in index.get("conversations", [])
                if item.get("id") != source["id"]
            ]
            index["conversations"].append(self._metadata(source))
            index.setdefault("conversations", []).append(self._metadata(child))
            index["conversations"].sort(key=self._index_sort_time, reverse=True)
            self._write_index(index)
            return child

    def get_split_state(self, source_conversation_id: str) -> dict[str, Any]:
        """Return the persisted split pane state for one primary task."""
        with self._lock:
            source = self._load_required(source_conversation_id)
            if source.get("is_split_task"):
                raise ValueError("Split state belongs to a primary task")
            child_id = self._clean_conversation_id(
                source.get("split_conversation_id")
            )
            if child_id:
                try:
                    child = self._load_required(child_id)
                except ValueError:
                    child = None
                if not child or child.get("parent_conversation_id") != source["id"]:
                    child_id = None
            return {
                "parent_conversation_id": source["id"],
                "conversation_id": child_id,
                "open": bool(child_id and source.get("split_open")),
                "width": self._clean_split_pane_width(
                    source.get("split_pane_width", 0)
                ),
            }

    def set_split_state(
        self,
        source_conversation_id: str,
        *,
        is_open: bool | None = None,
        width: int | None = None,
    ) -> dict[str, Any]:
        """Persist pane visibility and width without changing task ordering."""
        with self._lock:
            source = self._load_required(source_conversation_id)
            if source.get("is_split_task"):
                raise ValueError("Split state belongs to a primary task")
            if is_open is not None:
                source["split_open"] = bool(
                    is_open and source.get("split_conversation_id")
                )
            if width is not None:
                source["split_pane_width"] = self._clean_split_pane_width(width)
            self._write_json(self._conversation_file(source["id"]), source)
            self._update_index_metadata(source)
            return self.get_split_state(source["id"])

    def load(self, conversation_id: str) -> dict[str, Any]:
        with self._lock:
            return self._load_required(conversation_id)

    def set_active(self, conversation_id: str) -> dict[str, Any]:
        with self._lock:
            conversation = self._load_required(conversation_id)
            index = self._read_index()
            index["active_id"] = conversation_id
            self._write_index(index)
            return conversation

    def rename(self, conversation_id: str, title: str) -> dict[str, Any]:
        with self._lock:
            conversation = self._load_required(conversation_id)
            conversation["title"] = self._clean_title(title)
            conversation["updated_at"] = self._now()
            self._write_json(self._conversation_file(conversation_id), conversation)
            self._update_index_metadata(conversation)
            return conversation

    def archive(self, conversation_id: str) -> dict[str, Any]:
        """Mark a conversation as archived so it leaves the ordinary sidebar."""
        with self._lock:
            conversation = self._load_required(conversation_id)
            conversation["archived"] = True
            conversation["updated_at"] = self._now()
            self._write_json(self._conversation_file(conversation_id), conversation)
            self._update_index_metadata(conversation)
            return conversation

    def restore(self, conversation_id: str) -> dict[str, Any]:
        """Clear the archived flag and bring a conversation back to the sidebar."""
        with self._lock:
            conversation = self._load_required(conversation_id)
            conversation["archived"] = False
            conversation["updated_at"] = self._now()
            self._write_json(self._conversation_file(conversation_id), conversation)
            self._update_index_metadata(conversation)
            return conversation

    def set_project(
        self, conversation_id: str, project_id: str | None
    ) -> dict[str, Any]:
        """Move a task into a project or back to the ordinary task list."""
        with self._lock:
            conversation = self._load_required(conversation_id)
            conversation["project_id"] = self._clean_project_id(project_id)
            conversation["updated_at"] = self._now()
            self._write_json(self._conversation_file(conversation_id), conversation)
            self._update_index_metadata(conversation)
            return conversation

    def detach_project(self, project_id: str) -> builtins.list[str]:
        """Move every task in a deleted project back to the ordinary task list."""
        target_id = self._clean_project_id(project_id)
        if not target_id:
            return []
        with self._lock:
            index = self._read_index()
            detached = []
            metadata_items = []
            for item in index.get("conversations", []):
                conversation_id = str(item.get("id", ""))
                conversation = self._read_json(
                    self._conversation_file(conversation_id), None
                )
                if not isinstance(conversation, dict):
                    metadata_items.append(item)
                    continue
                if self._clean_project_id(conversation.get("project_id")) == target_id:
                    conversation["project_id"] = None
                    conversation["updated_at"] = self._now()
                    self._write_json(
                        self._conversation_file(conversation_id), conversation
                    )
                    detached.append(conversation_id)
                metadata_items.append(self._metadata(conversation))
            metadata_items.sort(key=self._index_sort_time, reverse=True)
            index["conversations"] = metadata_items
            self._write_index(index)
            return detached

    def delete(self, conversation_id: str) -> dict[str, Any]:
        with self._lock:
            conversation = self._load_required(conversation_id)
            index = self._read_index()
            delete_ids = set(self.related_conversation_ids(conversation_id))
            for delete_id in delete_ids:
                shutil.rmtree(self._conversation_dir(delete_id), ignore_errors=True)
            remaining = [
                item
                for item in index.get("conversations", [])
                if item.get("id") not in delete_ids
            ]
            if conversation.get("is_split_task"):
                parent_id = self._clean_conversation_id(
                    conversation.get("parent_conversation_id")
                )
                if parent_id:
                    try:
                        parent = self._load_required(parent_id)
                    except ValueError:
                        parent = None
                    if parent:
                        parent["split_conversation_id"] = None
                        parent["split_open"] = False
                        self._write_json(self._conversation_file(parent_id), parent)
                        remaining = [
                            item for item in remaining if item.get("id") != parent_id
                        ]
                        remaining.append(self._metadata(parent))
            index["conversations"] = remaining
            if not remaining:
                replacement = self._new_conversation("新任务")
                remaining = [self._metadata(replacement)]
                index["conversations"] = remaining
            if index.get("active_id") == conversation_id:
                visible_remaining = [
                    item for item in remaining if not item.get("is_split_task")
                ]
                index["active_id"] = (
                    visible_remaining[0]["id"]
                    if visible_remaining
                    else remaining[0]["id"]
                )
            self._write_index(index)
            return {
                "active_id": index["active_id"],
                "conversations": remaining,
                "deleted_conversation_ids": sorted(delete_ids),
            }

    def related_conversation_ids(self, conversation_id: str) -> builtins.list[str]:
        """Return a task and any internal split children deleted with it."""
        with self._lock:
            conversation = self._load_required(conversation_id)
            related_ids = {conversation_id}
            if not conversation.get("is_split_task"):
                related_ids.update(
                    str(item.get("id", ""))
                    for item in self._read_index().get("conversations", [])
                    if item.get("is_split_task")
                    and item.get("parent_conversation_id") == conversation_id
                    and str(item.get("id", ""))
                )
            return sorted(related_ids)

    def clear(self, conversation_id: str) -> dict[str, Any]:
        with self._lock:
            conversation = self._load_required(conversation_id)
            conversation["messages"] = []
            conversation["unread_completion"] = False
            conversation["last_completed_message_id"] = 0
            conversation["last_read_message_id"] = 0
            conversation["updated_at"] = self._now()
            self._write_json(self._conversation_file(conversation_id), conversation)
            memory_dir = self.short_term_memory_dir(conversation_id)
            shutil.rmtree(memory_dir, ignore_errors=True)
            memory_dir.mkdir(parents=True, exist_ok=True)
            shutil.rmtree(self.attachments_dir(conversation_id), ignore_errors=True)
            self._update_index_metadata(conversation)
            return conversation

    def mark_completed(
        self,
        conversation_id: str,
        message_id: int,
        unread: bool | None = True,
    ) -> dict[str, Any]:
        """Persist that a task finished and whether its result is still unread."""
        normalized_message_id = self._message_id(message_id)
        if normalized_message_id <= 0:
            raise ValueError("message_id must be a positive integer")

        with self._lock:
            conversation = self._load_required(conversation_id)
            completed_id = conversation["last_completed_message_id"]
            if normalized_message_id < completed_id:
                return conversation

            conversation["last_completed_message_id"] = normalized_message_id
            if unread is None:
                index = self._read_index()
                unread = index.get("active_id") != conversation_id
            if unread:
                conversation["unread_completion"] = (
                    normalized_message_id > conversation["last_read_message_id"]
                )
            else:
                conversation["unread_completion"] = False
            self._write_json(self._conversation_file(conversation_id), conversation)
            self._update_index_metadata(conversation)
            return conversation

    def mark_read(self, conversation_id: str) -> dict[str, Any]:
        """Acknowledge the latest completed result for one conversation."""
        with self._lock:
            conversation = self._load_required(conversation_id)
            conversation["last_read_message_id"] = max(
                conversation["last_read_message_id"],
                conversation["last_completed_message_id"],
            )
            conversation["unread_completion"] = False
            self._write_json(self._conversation_file(conversation_id), conversation)
            self._update_index_metadata(conversation)
            return conversation

    def append_message(
        self, conversation_id: str, message: dict[str, Any]
    ) -> dict[str, Any]:
        with self._lock:
            conversation = self._load_required(conversation_id)
            event = dict(message)
            event.setdefault("id", str(uuid.uuid4()))
            event.setdefault("timestamp", self._now())
            conversation.setdefault("messages", []).append(event)
            if event.get("type") == "user":
                conversation["last_user_message_at"] = self._now()
                if conversation.get("title") == "新任务":
                    conversation["title"] = self._clean_title(event.get("content", ""))
            conversation["updated_at"] = self._now()
            self._write_json(self._conversation_file(conversation_id), conversation)
            self._update_index_metadata(conversation)
            return event

    def upsert_plan_snapshot(
        self, conversation_id: str, message: dict[str, Any]
    ) -> dict[str, Any]:
        """Persist only the latest plan snapshot for one task message."""
        with self._lock:
            conversation = self._load_required(conversation_id)
            event = dict(message)
            event["type"] = "plan_update"
            event["message_id"] = self._message_id(event.get("message_id"))
            event.setdefault("id", str(uuid.uuid4()))
            event["timestamp"] = self._now()

            matching = [
                existing
                for existing in conversation.setdefault("messages", [])
                if existing.get("type") == "plan_update"
                and self._message_id(existing.get("message_id"))
                == event["message_id"]
            ]
            if matching:
                latest = max(
                    matching,
                    key=lambda item: self._message_id(item.get("version")),
                )
                if self._message_id(event.get("version")) < self._message_id(
                    latest.get("version")
                ):
                    return dict(latest)

            retained = []
            insert_at: int | None = None
            for existing in conversation.setdefault("messages", []):
                same_snapshot = (
                    existing.get("type") == "plan_update"
                    and self._message_id(existing.get("message_id"))
                    == event["message_id"]
                )
                if same_snapshot:
                    if insert_at is None:
                        insert_at = len(retained)
                        event["id"] = existing.get("id", event["id"])
                    continue
                retained.append(existing)

            if insert_at is None:
                retained.append(event)
            else:
                retained.insert(insert_at, event)
            conversation["messages"] = retained
            conversation["updated_at"] = self._now()
            self._write_json(self._conversation_file(conversation_id), conversation)
            self._update_index_metadata(conversation)
            return event

    def upsert_agent_team_snapshot(
        self, conversation_id: str, message: dict[str, Any]
    ) -> dict[str, Any]:
        """Persist only the latest bounded multi-agent snapshot for one run.

        Live child activity arrives as complete, versioned snapshots. Replacing
        the prior snapshot keeps conversation history reloadable without growing
        one event for every child status transition.
        """
        with self._lock:
            conversation = self._load_required(conversation_id)
            event = dict(message)
            event["type"] = "agent_team"
            event["message_id"] = self._message_id(event.get("message_id"))
            event["team_id"] = str(event.get("team_id", "")).strip()
            if not event["team_id"]:
                raise ValueError("team_id is required")
            event["version"] = self._message_id(event.get("version"))
            event.setdefault("id", str(uuid.uuid4()))
            event["timestamp"] = self._now()

            matching = [
                existing
                for existing in conversation.setdefault("messages", [])
                if existing.get("type") == "agent_team"
                and self._message_id(existing.get("message_id"))
                == event["message_id"]
                and str(existing.get("team_id", "")) == event["team_id"]
            ]
            if matching:
                latest = max(
                    matching,
                    key=lambda item: self._message_id(item.get("version")),
                )
                if event["version"] < self._message_id(latest.get("version")):
                    return dict(latest)

            retained = []
            insert_at: int | None = None
            for existing in conversation.setdefault("messages", []):
                same_snapshot = (
                    existing.get("type") == "agent_team"
                    and self._message_id(existing.get("message_id"))
                    == event["message_id"]
                    and str(existing.get("team_id", "")) == event["team_id"]
                )
                if same_snapshot:
                    if insert_at is None:
                        insert_at = len(retained)
                        event["id"] = existing.get("id", event["id"])
                    continue
                retained.append(existing)

            if insert_at is None:
                retained.append(event)
            else:
                retained.insert(insert_at, event)
            conversation["messages"] = retained
            conversation["updated_at"] = self._now()
            self._write_json(self._conversation_file(conversation_id), conversation)
            self._update_index_metadata(conversation)
            return event

    def mark_plan_terminal(
        self,
        conversation_id: str,
        message_id: int,
        state: str,
        message: str = "",
    ) -> dict[str, Any] | None:
        """Persist a plan's run outcome without changing any step status."""
        terminal_state = str(state or "").strip().lower()
        if terminal_state not in {"complete", "error", "stopped"}:
            raise ValueError("Invalid plan terminal state")
        normalized_message_id = self._message_id(message_id)
        with self._lock:
            conversation = self._load_required(conversation_id)
            plan_event = next(
                (
                    event
                    for event in reversed(conversation.get("messages", []))
                    if event.get("type") == "plan_update"
                    and self._message_id(event.get("message_id"))
                    == normalized_message_id
                ),
                None,
            )
            if plan_event is None:
                return None
            plan_event["terminal_state"] = terminal_state
            plan_event["terminal_message"] = str(message or "").strip()
            plan_event["terminal_at"] = self._now()
            conversation["updated_at"] = self._now()
            self._write_json(self._conversation_file(conversation_id), conversation)
            self._update_index_metadata(conversation)
            return dict(plan_event)

    def update_user_attachments(
        self, conversation_id: str, message_id: int, attachments: builtins.list[dict[str, Any]]
    ) -> None:
        with self._lock:
            conversation = self._load_required(conversation_id)
            for event in reversed(conversation.get("messages", [])):
                if event.get("type") == "user" and int(
                    event.get("message_id", 0)
                ) == int(message_id):
                    event["attachments"] = attachments
                    break
            conversation["updated_at"] = self._now()
            self._write_json(self._conversation_file(conversation_id), conversation)
            self._update_index_metadata(conversation)

    def memory_dir(self, conversation_id: str) -> Path:
        return self._conversation_dir(conversation_id) / "memory"

    def short_term_memory_dir(self, conversation_id: str) -> Path:
        """Return this task's writable short-term context directory."""
        with self._lock:
            conversation = self._load_required(conversation_id)
            scope_id = self._clean_conversation_id(
                conversation.get("short_term_memory_id")
            ) or conversation["id"]
            return self.memory_dir(scope_id)

    def active_id(self) -> str | None:
        return self._read_index().get("active_id")
