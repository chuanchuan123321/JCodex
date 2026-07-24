"""Persistent desktop conversations with isolated per-task memory."""

import json
import shutil
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


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
        return datetime.now(timezone.utc).isoformat()

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

            index["conversations"] = normalized_items
            if not index.get("active_id") or not any(
                item.get("id") == index.get("active_id")
                for item in normalized_items
            ):
                index["active_id"] = normalized_items[0]["id"]
                changed = True
            if changed:
                self._write_index(index)

    def _read_json(self, path: Path, default: Any) -> Any:
        try:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            pass
        return default

    def _write_json(self, path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(path.suffix + ".tmp")
        temp_path.write_text(
            json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temp_path.replace(path)

    def _read_index(self) -> Dict[str, Any]:
        return self._read_json(
            self.index_file, {"active_id": None, "conversations": []}
        )

    def _write_index(self, index: Dict[str, Any]) -> None:
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
    ) -> List[Dict[str, Any]]:
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
            images: List[Dict[str, Any]] = []
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
        self, title: str, project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        now = self._now()
        conversation = {
            "id": str(uuid.uuid4()),
            "title": self._clean_title(title),
            "project_id": self._clean_project_id(project_id),
            "created_at": now,
            "updated_at": now,
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
    def _clean_project_id(project_id: Optional[str]) -> Optional[str]:
        value = str(project_id or "").strip()
        if not value:
            return None
        if any(char not in "0123456789abcdef-" for char in value):
            raise ValueError("Invalid project id")
        return value

    @staticmethod
    def _message_id(value: Any) -> int:
        try:
            return max(0, int(value or 0))
        except (TypeError, ValueError):
            return 0

    @classmethod
    def _normalize_completion_state(cls, conversation: Dict[str, Any]) -> None:
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
    def _metadata(conversation: Dict[str, Any]) -> Dict[str, Any]:
        ConversationStore._normalize_completion_state(conversation)
        return {
            "id": conversation["id"],
            "title": conversation.get("title", "新任务"),
            "project_id": ConversationStore._clean_project_id(
                conversation.get("project_id")
            ),
            "created_at": conversation.get("created_at", ""),
            "updated_at": conversation.get("updated_at", ""),
            "message_count": len(conversation.get("messages", [])),
            "unread_completion": conversation["unread_completion"],
            "last_completed_message_id": conversation[
                "last_completed_message_id"
            ],
            "last_read_message_id": conversation["last_read_message_id"],
        }

    def _load_required(self, conversation_id: str) -> Dict[str, Any]:
        conversation = self._read_json(self._conversation_file(conversation_id), None)
        if not isinstance(conversation, dict):
            raise ValueError("Conversation not found")
        self._normalize_completion_state(conversation)
        return conversation

    def _update_index_metadata(self, conversation: Dict[str, Any]) -> None:
        index = self._read_index()
        metadata = self._metadata(conversation)
        items = [
            item
            for item in index.get("conversations", [])
            if item.get("id") != conversation["id"]
        ]
        items.append(metadata)
        items.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
        index["conversations"] = items
        if not index.get("active_id"):
            index["active_id"] = conversation["id"]
        self._write_index(index)

    def list(self) -> Dict[str, Any]:
        with self._lock:
            index = self._read_index()
            items = list(index.get("conversations", []))
            items.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
            return {"active_id": index.get("active_id"), "conversations": items}

    def create(
        self, title: str = "新任务", project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        with self._lock:
            conversation = self._new_conversation(title, project_id)
            index = self._read_index()
            index["active_id"] = conversation["id"]
            index.setdefault("conversations", []).append(self._metadata(conversation))
            index["conversations"].sort(
                key=lambda item: item.get("updated_at", ""), reverse=True
            )
            self._write_index(index)
            return conversation

    def load(self, conversation_id: str) -> Dict[str, Any]:
        with self._lock:
            return self._load_required(conversation_id)

    def set_active(self, conversation_id: str) -> Dict[str, Any]:
        with self._lock:
            conversation = self._load_required(conversation_id)
            index = self._read_index()
            index["active_id"] = conversation_id
            self._write_index(index)
            return conversation

    def rename(self, conversation_id: str, title: str) -> Dict[str, Any]:
        with self._lock:
            conversation = self._load_required(conversation_id)
            conversation["title"] = self._clean_title(title)
            conversation["updated_at"] = self._now()
            self._write_json(self._conversation_file(conversation_id), conversation)
            self._update_index_metadata(conversation)
            return conversation

    def set_project(
        self, conversation_id: str, project_id: Optional[str]
    ) -> Dict[str, Any]:
        """Move a task into a project or back to the ordinary task list."""
        with self._lock:
            conversation = self._load_required(conversation_id)
            conversation["project_id"] = self._clean_project_id(project_id)
            conversation["updated_at"] = self._now()
            self._write_json(self._conversation_file(conversation_id), conversation)
            self._update_index_metadata(conversation)
            return conversation

    def detach_project(self, project_id: str) -> List[str]:
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
            metadata_items.sort(
                key=lambda entry: entry.get("updated_at", ""), reverse=True
            )
            index["conversations"] = metadata_items
            self._write_index(index)
            return detached

    def delete(self, conversation_id: str) -> Dict[str, Any]:
        with self._lock:
            self._load_required(conversation_id)
            shutil.rmtree(self._conversation_dir(conversation_id), ignore_errors=True)
            index = self._read_index()
            remaining = [
                item
                for item in index.get("conversations", [])
                if item.get("id") != conversation_id
            ]
            index["conversations"] = remaining
            if not remaining:
                replacement = self._new_conversation("新任务")
                remaining = [self._metadata(replacement)]
                index["conversations"] = remaining
            if index.get("active_id") == conversation_id:
                index["active_id"] = remaining[0]["id"]
            self._write_index(index)
            return {"active_id": index["active_id"], "conversations": remaining}

    def clear(self, conversation_id: str) -> Dict[str, Any]:
        with self._lock:
            conversation = self._load_required(conversation_id)
            conversation["messages"] = []
            conversation["unread_completion"] = False
            conversation["last_completed_message_id"] = 0
            conversation["last_read_message_id"] = 0
            conversation["updated_at"] = self._now()
            self._write_json(self._conversation_file(conversation_id), conversation)
            memory_dir = self.memory_dir(conversation_id)
            shutil.rmtree(memory_dir, ignore_errors=True)
            memory_dir.mkdir(parents=True, exist_ok=True)
            shutil.rmtree(self.attachments_dir(conversation_id), ignore_errors=True)
            self._update_index_metadata(conversation)
            return conversation

    def mark_completed(
        self,
        conversation_id: str,
        message_id: int,
        unread: Optional[bool] = True,
    ) -> Dict[str, Any]:
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

    def mark_read(self, conversation_id: str) -> Dict[str, Any]:
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
        self, conversation_id: str, message: Dict[str, Any]
    ) -> Dict[str, Any]:
        with self._lock:
            conversation = self._load_required(conversation_id)
            event = dict(message)
            event.setdefault("id", str(uuid.uuid4()))
            event.setdefault("timestamp", self._now())
            conversation.setdefault("messages", []).append(event)
            if (
                event.get("type") == "user"
                and conversation.get("title") == "新任务"
            ):
                conversation["title"] = self._clean_title(event.get("content", ""))
            conversation["updated_at"] = self._now()
            self._write_json(self._conversation_file(conversation_id), conversation)
            self._update_index_metadata(conversation)
            return event

    def upsert_plan_snapshot(
        self, conversation_id: str, message: Dict[str, Any]
    ) -> Dict[str, Any]:
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
            insert_at: Optional[int] = None
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

    def mark_plan_terminal(
        self,
        conversation_id: str,
        message_id: int,
        state: str,
        message: str = "",
    ) -> Optional[Dict[str, Any]]:
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
        self, conversation_id: str, message_id: int, attachments: List[Dict[str, Any]]
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

    def active_id(self) -> Optional[str]:
        return self._read_index().get("active_id")
