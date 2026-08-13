"""Thread-safe multi-agent team primitives for local collaboration runs."""

from __future__ import annotations

import inspect
import json
import queue
import threading
import time
import uuid
from collections import deque
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

MAX_TEAM_AGENTS = 4
MULTI_AGENT_TOOL_NAMES = frozenset(
    {
        "spawn_agent",
        "send_agent_message",
        "publish_agent_artifact",
        "get_agent_collaboration",
        "wait_agents",
        "list_agents",
        "cancel_agent",
    }
)

_TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled"})
_MESSAGE_KINDS = frozenset({"message", "question", "decision", "handoff", "blocker", "artifact"})

ActivityCallback = Callable[[object, str, Mapping[str, Any] | None], None]
UpdateCallback = Callable[[dict[str, Any]], None]
WorkerCallback = Callable[..., Any]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _clean_text(value: object, *, limit: int, fallback: str = "") -> str:
    text = " ".join(str(value or fallback).split()).strip()
    return text[:limit]


def _json_safe(value: Any) -> Any:
    """Return a defensive, JSON-serializable copy for public snapshots."""
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))
    except (TypeError, ValueError):
        return str(value)


@dataclass
class _AgentRecord:
    agent_id: str
    name: str
    role: str
    task: str
    context: str
    write_access: bool
    write_paths: tuple[str, ...]
    workdir: str
    depends_on: tuple[str, ...]
    created_at: str
    cancel_event: threading.Event = field(default_factory=threading.Event)
    inbox: queue.Queue[str] = field(default_factory=queue.Queue)
    activities: deque[dict[str, Any]] = field(default_factory=deque)
    messages: deque[dict[str, Any]] = field(default_factory=deque)
    status: str = "queued"
    started_at: str = ""
    completed_at: str = ""
    result: Any = None
    error: str = ""
    activity_sequence: int = 0
    message_sequence: int = 0
    thread: threading.Thread | None = None


class MultiAgentTeam:
    """Run and observe a bounded set of isolated worker callbacks.

    The team owns lifecycle state only; model and tool isolation remain the
    caller's responsibility. The worker receives a public task dictionary, a
    per-agent cancellation event, and an activity callback. Workers accepting a
    fourth positional argument also receive a thread-safe inbox populated by
    :meth:`send_message`.

    Every mutation increments the team version. ``on_update`` is invoked with a
    complete defensive snapshot, never a delta, and callbacks are serialized in
    version order.
    """

    def __init__(
        self,
        worker: WorkerCallback,
        *,
        on_update: UpdateCallback | None = None,
        max_agents: int = MAX_TEAM_AGENTS,
        max_activities: int = 80,
        max_messages: int = 40,
        max_artifacts: int = 40,
        max_collaboration_events: int = 120,
        max_activity_chars: int = 4000,
    ) -> None:
        if not callable(worker):
            raise TypeError("worker must be callable")
        if on_update is not None and not callable(on_update):
            raise TypeError("on_update must be callable")
        try:
            normalized_max_agents = int(max_agents)
        except (TypeError, ValueError) as exc:
            raise ValueError("max_agents must be an integer") from exc
        if not 1 <= normalized_max_agents <= MAX_TEAM_AGENTS:
            raise ValueError(f"max_agents must be between 1 and {MAX_TEAM_AGENTS}")

        self.worker = worker
        self.on_update = on_update
        self.max_agents = normalized_max_agents
        self.max_activities = max(1, min(int(max_activities), 500))
        self.max_messages = max(1, min(int(max_messages), 200))
        self.max_artifacts = max(1, min(int(max_artifacts), 100))
        self.max_collaboration_events = max(1, min(int(max_collaboration_events), 500))
        self.max_activity_chars = max(128, min(int(max_activity_chars), 20000))
        self.team_id = uuid.uuid4().hex
        self.created_at = _now()

        self._agents: dict[str, _AgentRecord] = {}
        self._artifacts: deque[dict[str, Any]] = deque(maxlen=self.max_artifacts)
        self._collaboration_events: deque[dict[str, Any]] = deque(
            maxlen=self.max_collaboration_events
        )
        self._collaboration_sequence = 0
        self._version = 0
        # All writes and callbacks use this outer lock, preserving callback
        # ordering while the inner condition remains usable by waiters.
        self._update_lock = threading.RLock()
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)

    def spawn(
        self,
        name: str,
        role: str,
        task: str,
        context: str = "",
        write_access: bool = False,
        write_paths: Sequence[str] | None = None,
        workdir: str = "",
        depends_on: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        """Create one agent and start its worker in a daemon thread."""
        normalized_name = _clean_text(name, limit=80)
        normalized_role = _clean_text(role, limit=240)
        normalized_task = str(task or "").strip()[:20000]
        normalized_context = str(context or "").strip()[:50000]
        if not normalized_name:
            raise ValueError("agent name is required")
        if not normalized_role:
            raise ValueError("agent role is required")
        if not normalized_task:
            raise ValueError("agent task is required")

        paths: list[str] = []
        for raw_path in write_paths or ():
            path = str(raw_path or "").strip()
            if path and path not in paths:
                paths.append(path[:4096])
        if paths and not bool(write_access):
            raise ValueError("write_paths require write_access=true")
        normalized_workdir = str(workdir or "").strip()[:4096]
        dependencies = self._normalize_agent_ids(depends_on)

        with self._update_lock:
            with self._condition:
                if len(self._agents) >= self.max_agents:
                    raise RuntimeError(
                        f"team already has the maximum of {self.max_agents} agents"
                    )
                for dependency_id in dependencies:
                    self._require_agent_locked(dependency_id)
                self._assert_write_paths_available_locked(paths)
                agent_id = uuid.uuid4().hex
                record = _AgentRecord(
                    agent_id=agent_id,
                    name=normalized_name,
                    role=normalized_role,
                    task=normalized_task,
                    context=normalized_context,
                    write_access=bool(write_access),
                    write_paths=tuple(paths),
                    workdir=normalized_workdir,
                    depends_on=dependencies,
                    created_at=_now(),
                    activities=deque(maxlen=self.max_activities),
                    messages=deque(maxlen=self.max_messages),
                )
                thread = threading.Thread(
                    target=self._run_worker,
                    args=(agent_id,),
                    name=f"multi-agent-{agent_id[:8]}",
                    daemon=True,
                )
                record.thread = thread
                self._agents[agent_id] = record
                snapshot = self._commit_locked()
            self._notify(snapshot)
            thread.start()
        return self.get_agent(agent_id)

    def send_message(
        self,
        agent_id: str,
        message: str,
        *,
        sender_agent_id: str = "",
        kind: str = "message",
        references: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        """Append a public message and deliver it to a running agent's inbox."""
        content = str(message or "").strip()[:20000]
        if not content:
            raise ValueError("message is required")
        normalized_kind = str(kind or "message").strip().lower()
        if normalized_kind not in _MESSAGE_KINDS:
            raise ValueError(f"unsupported collaboration message kind: {normalized_kind}")
        normalized_references = self._normalize_references(references)
        with self._update_lock:
            with self._condition:
                record = self._require_agent_locked(agent_id)
                if record.status in _TERMINAL_STATUSES:
                    raise RuntimeError("cannot message a terminal agent")
                sender = (
                    self._require_agent_locked(sender_agent_id)
                    if sender_agent_id
                    else None
                )
                if sender is not None and sender.agent_id == record.agent_id:
                    raise ValueError("an agent cannot message itself")
                record.message_sequence += 1
                message_entry = {
                    "sequence": record.message_sequence,
                    "timestamp": _now(),
                    "content": content,
                    "kind": normalized_kind,
                    "sender_agent_id": sender.agent_id if sender else "primary",
                    "sender_name": sender.name if sender else "主智能体",
                    "references": normalized_references,
                }
                record.messages.append(message_entry)
                # Preserve the original coordinator inbox contract for custom
                # workers while peer messages keep their explicit provenance.
                inbox_message = (
                    content
                    if sender is None
                    and normalized_kind == "message"
                    and not normalized_references
                    else self._inbox_text(message_entry)
                )
                record.inbox.put(inbox_message)
                self._append_activity_locked(
                    record,
                    f"{message_entry['sender_name']}：{content}",
                    "message",
                    {
                        "message_sequence": record.message_sequence,
                        "kind": normalized_kind,
                        "sender_agent_id": message_entry["sender_agent_id"],
                        "direction": "inbound",
                        "references": normalized_references,
                    },
                )
                if sender is not None:
                    self._append_activity_locked(
                        sender,
                        f"发送给 {record.name}：{content}",
                        "message",
                        {
                            "kind": normalized_kind,
                            "recipient_agent_id": record.agent_id,
                            "direction": "outbound",
                            "references": normalized_references,
                        },
                    )
                self._append_collaboration_event_locked(
                    {
                        "type": "message",
                        "kind": normalized_kind,
                        "content": content,
                        "sender_agent_id": message_entry["sender_agent_id"],
                        "sender_name": message_entry["sender_name"],
                        "recipient_agent_id": record.agent_id,
                        "recipient_name": record.name,
                        "references": normalized_references,
                    }
                )
                snapshot = self._commit_locked()
            self._notify(snapshot)
        return self.get_agent(record.agent_id)

    def publish_artifact(
        self,
        sender_agent_id: str,
        title: str,
        summary: str,
        paths: Sequence[str] | None = None,
        recipient_agent_ids: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        """Publish a bounded, explicit handoff artifact to the team blackboard."""
        normalized_title = _clean_text(title, limit=160)
        normalized_summary = str(summary or "").strip()[:8000]
        if not normalized_title or not normalized_summary:
            raise ValueError("artifact title and summary are required")
        normalized_paths = self._normalize_references(paths)
        recipients = self._normalize_agent_ids(recipient_agent_ids)
        with self._update_lock:
            with self._condition:
                sender = (
                    None
                    if sender_agent_id == "primary"
                    else self._require_agent_locked(sender_agent_id)
                )
                for recipient_id in recipients:
                    recipient = self._require_agent_locked(recipient_id)
                    if recipient.status in _TERMINAL_STATUSES:
                        raise RuntimeError("cannot deliver an artifact to a terminal agent")
                artifact = {
                    "id": uuid.uuid4().hex,
                    "sequence": self._next_collaboration_sequence_locked(),
                    "timestamp": _now(),
                    "sender_agent_id": sender.agent_id if sender else "primary",
                    "sender_name": sender.name if sender else "主智能体",
                    "title": normalized_title,
                    "summary": normalized_summary,
                    "paths": normalized_paths,
                    "recipient_agent_ids": list(recipients),
                }
                self._artifacts.append(artifact)
                if sender is not None:
                    self._append_activity_locked(
                        sender,
                        f"发布工件：{normalized_title}",
                        "artifact",
                        {"artifact_id": artifact["id"], "paths": normalized_paths},
                    )
                for recipient_id in recipients:
                    recipient = self._require_agent_locked(recipient_id)
                    recipient.message_sequence += 1
                    notification = {
                        "sequence": recipient.message_sequence,
                        "timestamp": artifact["timestamp"],
                        "content": f"{normalized_title}\n{normalized_summary}",
                        "kind": "artifact",
                        "sender_agent_id": sender.agent_id,
                        "sender_name": sender.name,
                        "references": normalized_paths,
                    }
                    recipient.messages.append(notification)
                    recipient.inbox.put(self._inbox_text(notification))
                    self._append_activity_locked(
                        recipient,
                        f"收到工件 {sender.name}：{normalized_title}",
                        "artifact",
                        {"artifact_id": artifact["id"], "direction": "inbound"},
                    )
                self._append_collaboration_event_locked(
                    {"type": "artifact", **artifact}
                )
                snapshot = self._commit_locked()
            self._notify(snapshot)
        return _json_safe(artifact)

    def take_inbox(self, agent_id: str, limit: int = 8) -> list[str]:
        """Drain bounded public messages for safe injection before a model turn."""
        maximum = max(1, min(int(limit), 32))
        with self._lock:
            inbox = self._require_agent_locked(agent_id).inbox
            messages = []
            while len(messages) < maximum:
                try:
                    messages.append(str(inbox.get_nowait()))
                except queue.Empty:
                    break
        return messages

    def collaboration_snapshot(self, agent_id: str = "") -> dict[str, Any]:
        """Return bounded public blackboard data, optionally scoped to one agent."""
        with self._lock:
            if agent_id:
                self._require_agent_locked(agent_id)
            artifacts = list(self._artifacts)
            events = list(self._collaboration_events)
            if agent_id:
                artifacts = [
                    item for item in artifacts
                    if item["sender_agent_id"] == agent_id
                    or not item["recipient_agent_ids"]
                    or agent_id in item["recipient_agent_ids"]
                ]
                events = [
                    item for item in events
                    if item.get("sender_agent_id") == agent_id
                    or item.get("recipient_agent_id") == agent_id
                ]
            return _json_safe(
                {
                    "artifacts": artifacts,
                    "events": events,
                    # File claims are deliberately public coordination metadata.
                    # They contain ownership only, never an agent's private history.
                    "file_claims": self._file_claims_locked(),
                }
            )

    def wait_agents(
        self,
        agent_ids: Sequence[str] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Wait until the selected agents are terminal or the timeout expires."""
        normalized_ids = self._normalize_agent_ids(agent_ids)
        if timeout is not None:
            try:
                timeout = max(0.0, float(timeout))
            except (TypeError, ValueError) as exc:
                raise ValueError("timeout must be a number of seconds") from exc
        deadline = None if timeout is None else time.monotonic() + timeout

        with self._condition:
            if not normalized_ids:
                normalized_ids = tuple(self._agents)
            for agent_id in normalized_ids:
                self._require_agent_locked(agent_id)
            while not self._all_terminal_locked(normalized_ids):
                remaining = None if deadline is None else deadline - time.monotonic()
                if remaining is not None and remaining <= 0:
                    break
                self._condition.wait(remaining)
            completed = self._all_terminal_locked(normalized_ids)
            snapshot = self._snapshot_locked()

        snapshot["wait"] = {
            "agent_ids": list(normalized_ids),
            "completed": completed,
            "timed_out": not completed,
        }
        return snapshot

    def list_agents(self) -> dict[str, Any]:
        """Return the current full team snapshot."""
        with self._lock:
            return self._snapshot_locked()

    def get_agent(self, agent_id: str) -> dict[str, Any]:
        """Return one public agent snapshot."""
        with self._lock:
            return self._agent_snapshot_locked(self._require_agent_locked(agent_id))

    def cancel_agent(self, agent_id: str) -> dict[str, Any]:
        """Request cooperative cancellation for one agent."""
        with self._update_lock:
            with self._condition:
                record = self._require_agent_locked(agent_id)
                if record.status not in _TERMINAL_STATUSES:
                    record.cancel_event.set()
                    if record.status != "cancelling":
                        record.status = "cancelling"
                        self._append_activity_locked(
                            record, "Cancellation requested", "status", None
                        )
                        snapshot = self._commit_locked()
                    else:
                        snapshot = self._snapshot_locked()
                else:
                    snapshot = self._snapshot_locked()
            self._notify(snapshot)
        return self.get_agent(record.agent_id)

    def cancel_all(self) -> dict[str, Any]:
        """Request cooperative cancellation for every non-terminal agent."""
        changed = False
        with self._update_lock:
            with self._condition:
                for record in self._agents.values():
                    if record.status in _TERMINAL_STATUSES:
                        continue
                    record.cancel_event.set()
                    if record.status != "cancelling":
                        record.status = "cancelling"
                        self._append_activity_locked(
                            record, "Cancellation requested", "status", None
                        )
                        changed = True
                snapshot = (
                    self._commit_locked() if changed else self._snapshot_locked()
                )
            self._notify(snapshot)
        return snapshot

    def receive_message(
        self, agent_id: str, timeout: float | None = None
    ) -> str | None:
        """Receive one inbox message, primarily for custom worker adapters."""
        with self._lock:
            inbox = self._require_agent_locked(agent_id).inbox
        try:
            return inbox.get(timeout=timeout)
        except queue.Empty:
            return None

    def _run_worker(self, agent_id: str) -> None:
        while True:
            with self._update_lock, self._condition:
                record = self._require_agent_locked(agent_id)
                if record.cancel_event.is_set():
                    record.status = "cancelled"
                    record.completed_at = _now()
                    snapshot = self._commit_locked()
                    cancelled_before_start = True
                    ready_to_start = False
                elif self._dependencies_terminal_locked(record.depends_on):
                    record.status = "running"
                    record.started_at = _now()
                    self._append_activity_locked(
                        record, "Agent started", "status", None
                    )
                    snapshot = self._commit_locked()
                    cancelled_before_start = False
                    ready_to_start = True
                else:
                    if record.status != "waiting":
                        record.status = "waiting"
                        self._append_activity_locked(
                            record,
                            "等待依赖的子智能体完成",
                            "status",
                            {"depends_on": list(record.depends_on)},
                        )
                        snapshot = self._commit_locked()
                    else:
                        snapshot = None
                    cancelled_before_start = False
                    ready_to_start = False
            if snapshot is not None:
                self._notify(snapshot)
            if cancelled_before_start or ready_to_start:
                break
            # Do not retain the serialized update lock while a dependency runs.
            with self._condition:
                self._condition.wait(timeout=0.5)
        if cancelled_before_start:
            return

        request = self._worker_request(record)

        def activity(
            content: object,
            kind: str = "progress",
            metadata: Mapping[str, Any] | None = None,
        ) -> None:
            self._record_activity(agent_id, content, kind, metadata)

        try:
            result = self._invoke_worker(
                request, record.cancel_event, activity, record.inbox
            )
        except Exception as exc:
            with self._update_lock:
                with self._condition:
                    current = self._require_agent_locked(agent_id)
                    current.completed_at = _now()
                    if current.cancel_event.is_set():
                        current.status = "cancelled"
                    else:
                        current.status = "failed"
                        current.error = _clean_text(
                            f"{type(exc).__name__}: {exc}", limit=4000
                        )
                        self._append_activity_locked(
                            current, current.error, "error", None
                        )
                    snapshot = self._commit_locked()
                self._notify(snapshot)
            return

        with self._update_lock:
            with self._condition:
                current = self._require_agent_locked(agent_id)
                current.completed_at = _now()
                if current.cancel_event.is_set():
                    current.status = "cancelled"
                    current.result = None
                else:
                    current.status = "completed"
                    current.result = _json_safe(result)
                    self._append_activity_locked(
                        current, "Agent completed", "status", None
                    )
                snapshot = self._commit_locked()
            self._notify(snapshot)

    def _record_activity(
        self,
        agent_id: str,
        content: object,
        kind: str,
        metadata: Mapping[str, Any] | None,
    ) -> None:
        with self._update_lock:
            with self._condition:
                record = self._require_agent_locked(agent_id)
                if record.status in _TERMINAL_STATUSES:
                    return
                self._append_activity_locked(record, content, kind, metadata)
                snapshot = self._commit_locked()
            self._notify(snapshot)

    def _append_activity_locked(
        self,
        record: _AgentRecord,
        content: object,
        kind: str,
        metadata: Mapping[str, Any] | None,
    ) -> None:
        text = str(content or "").strip()
        if not text:
            return
        metadata_copy = dict(metadata or {})
        replace_existing = bool(metadata_copy.get("_replace", False))
        activity_key = str(metadata_copy.get("_activity_key", "") or "")
        if replace_existing and activity_key:
            for existing in reversed(record.activities):
                existing_metadata = existing.get("metadata")
                if not isinstance(existing_metadata, Mapping):
                    continue
                if str(existing_metadata.get("_activity_key", "") or "") != activity_key:
                    continue
                existing.update(
                    {
                        "timestamp": _now(),
                        "kind": _clean_text(kind, limit=80, fallback="progress")
                        or "progress",
                        "content": text[: self.max_activity_chars],
                        "metadata": _json_safe(metadata_copy),
                    }
                )
                return
        record.activity_sequence += 1
        record.activities.append(
            {
                "sequence": record.activity_sequence,
                "timestamp": _now(),
                "kind": _clean_text(kind, limit=80, fallback="progress")
                or "progress",
                "content": text[: self.max_activity_chars],
                "metadata": _json_safe(metadata_copy),
            }
        )

    def _commit_locked(self) -> dict[str, Any]:
        self._version += 1
        self._condition.notify_all()
        return self._snapshot_locked()

    def _notify(self, snapshot: dict[str, Any]) -> None:
        if self.on_update is None:
            return
        # UI/persistence callbacks must not terminate agent workers.
        with suppress(Exception):
            self.on_update(_json_safe(snapshot))

    def _snapshot_locked(self) -> dict[str, Any]:
        agents = [
            self._agent_snapshot_locked(record) for record in self._agents.values()
        ]
        active_count = sum(
            agent["status"] not in _TERMINAL_STATUSES for agent in agents
        )
        return {
            "team_id": self.team_id,
            "version": self._version,
            "created_at": self.created_at,
            "max_agents": self.max_agents,
            "agent_count": len(agents),
            "active_count": active_count,
            "all_terminal": bool(agents) and active_count == 0,
            "agents": agents,
            "artifacts": _json_safe(list(self._artifacts)),
            "collaboration_events": _json_safe(list(self._collaboration_events)),
            "file_claims": self._file_claims_locked(),
        }

    @staticmethod
    def _agent_snapshot_locked(record: _AgentRecord) -> dict[str, Any]:
        return {
            "agent_id": record.agent_id,
            "name": record.name,
            "role": record.role,
            "task": record.task,
            "context": record.context,
            "write_access": record.write_access,
            "write_paths": list(record.write_paths),
            "workdir": record.workdir,
            "depends_on": list(record.depends_on),
            "status": record.status,
            "created_at": record.created_at,
            "started_at": record.started_at,
            "completed_at": record.completed_at,
            "result": _json_safe(record.result),
            "error": record.error,
            "activities": _json_safe(list(record.activities)),
            "messages": _json_safe(list(record.messages)),
        }

    @staticmethod
    def _worker_request(record: _AgentRecord) -> dict[str, Any]:
        return {
            "agent_id": record.agent_id,
            "name": record.name,
            "role": record.role,
            "task": record.task,
            "context": record.context,
            "write_access": record.write_access,
            "write_paths": list(record.write_paths),
            "workdir": record.workdir,
            "depends_on": list(record.depends_on),
        }

    @staticmethod
    def _normalize_references(values: Sequence[str] | None) -> list[str]:
        references: list[str] = []
        for raw_value in values or ():
            value = str(raw_value or "").strip()
            if value and value not in references:
                references.append(value[:4096])
        return references[:24]

    @staticmethod
    def _inbox_text(message: Mapping[str, Any]) -> str:
        kind = str(message.get("kind", "message") or "message")
        sender = str(message.get("sender_name", "协作成员") or "协作成员")
        references = message.get("references") or []
        reference_text = ""
        if references:
            reference_text = "\n关联项：" + "、".join(str(item) for item in references[:12])
        return (
            f"[协作消息/{kind}] 来自 {sender}\n"
            f"{str(message.get('content', '') or '').strip()[:8000]}{reference_text}"
        )

    def _next_collaboration_sequence_locked(self) -> int:
        self._collaboration_sequence += 1
        return self._collaboration_sequence

    def _append_collaboration_event_locked(self, event: Mapping[str, Any]) -> None:
        payload = dict(event)
        payload.setdefault("sequence", self._next_collaboration_sequence_locked())
        payload.setdefault("timestamp", _now())
        self._collaboration_events.append(_json_safe(payload))

    @staticmethod
    def _claimed_path_key(path: str) -> str:
        return str(path or "").strip().replace("\\", "/").rstrip("/")

    @classmethod
    def _paths_overlap(cls, left: str, right: str) -> bool:
        left_key = cls._claimed_path_key(left)
        right_key = cls._claimed_path_key(right)
        if not left_key or not right_key:
            return False
        return (
            left_key == right_key
            or left_key.startswith(f"{right_key}/")
            or right_key.startswith(f"{left_key}/")
        )

    def _assert_write_paths_available_locked(self, paths: Sequence[str]) -> None:
        for path in paths:
            for record in self._agents.values():
                if record.status in _TERMINAL_STATUSES:
                    continue
                if any(self._paths_overlap(path, claimed) for claimed in record.write_paths):
                    raise ValueError(
                        f"write path '{path}' is already claimed by {record.name}"
                    )

    def _file_claims_locked(self) -> list[dict[str, Any]]:
        return [
            {
                "agent_id": record.agent_id,
                "agent_name": record.name,
                "paths": list(record.write_paths),
                "workdir": record.workdir,
                "active": record.status not in _TERMINAL_STATUSES,
            }
            for record in self._agents.values()
            if record.write_paths
        ]

    def _dependencies_terminal_locked(self, dependencies: Sequence[str]) -> bool:
        return all(
            self._require_agent_locked(agent_id).status in _TERMINAL_STATUSES
            for agent_id in dependencies
        )

    def _invoke_worker(
        self,
        request: dict[str, Any],
        cancel_event: threading.Event,
        activity: ActivityCallback,
        inbox: queue.Queue[str],
    ) -> Any:
        try:
            signature = inspect.signature(self.worker)
        except (TypeError, ValueError):
            return self.worker(request, cancel_event, activity)
        candidates = (
            (request, cancel_event, activity, inbox),
            (request, cancel_event, activity),
        )
        for candidate in candidates:
            try:
                signature.bind(*candidate)
            except TypeError:
                continue
            return self.worker(*candidate)
        raise TypeError(
            "worker must accept (agent, cancel_event, activity) or "
            "(agent, cancel_event, activity, inbox)"
        )

    def _require_agent_locked(self, agent_id: str) -> _AgentRecord:
        normalized_id = str(agent_id or "").strip()
        record = self._agents.get(normalized_id)
        if record is None:
            raise KeyError(f"unknown agent_id: {normalized_id}")
        return record

    @staticmethod
    def _normalize_agent_ids(
        agent_ids: Sequence[str] | None,
    ) -> tuple[str, ...]:
        if agent_ids is None:
            return ()
        if isinstance(agent_ids, str):
            agent_ids = [agent_ids]
        normalized: list[str] = []
        for raw_id in agent_ids:
            agent_id = str(raw_id or "").strip()
            if agent_id and agent_id not in normalized:
                normalized.append(agent_id)
        return tuple(normalized)

    def _all_terminal_locked(self, agent_ids: Sequence[str]) -> bool:
        return all(
            self._require_agent_locked(agent_id).status in _TERMINAL_STATUSES
            for agent_id in agent_ids
        )


__all__ = [
    "MAX_TEAM_AGENTS",
    "MULTI_AGENT_TOOL_NAMES",
    "MultiAgentTeam",
]
