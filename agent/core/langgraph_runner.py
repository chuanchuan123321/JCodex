"""Resumable LangGraph execution core shared by desktop and terminal modes."""

from __future__ import annotations

import inspect
import json
import re
import sqlite3
import threading
import time
import uuid
from contextlib import nullcontext
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    AnyMessage,
    BaseMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
    ToolMessage,
    convert_to_messages,
)
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import REMOVE_ALL_MESSAGES, add_messages
from langgraph.types import Command, interrupt
from typing_extensions import Annotated, NotRequired, TypedDict

from agent.core.tool_loop_guard import ToolLoopGuard
from agent.core.tool_result import ToolExecutionResult


EventCallback = Callable[[dict[str, Any]], None]
ToolExecutor = Callable[..., Any]
ApprovalPredicate = Callable[[str, dict[str, Any]], bool]


_MULTIPLE_CHOICE_CUE = re.compile(
    r"(?:可|允许|支持)?\s*(?:多选|多项选择|选择多个|可选多个)"
)
_FREE_TEXT_CUE = re.compile(
    r"(?:可(?:在)?(?:下方|下面)?(?:文字)?补充|(?:下方|下面)(?:文字)?补充|"
    r"直接补充文字|自由(?:文本)?(?:填写|输入)|其他(?:说明|内容)?(?:请)?(?:补充|填写))"
)


def _question_bool(value: Any, default: bool = False) -> bool:
    """Coerce tool-call booleans without treating ``\"false\"`` as true."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off", ""}:
            return False
    return default


def _question_text(value: Any, default: str) -> str:
    """Return a compact, user-visible question field."""
    text = str(value or "").strip()
    return text or default


def normalize_question_payload(raw_questions: Any) -> list[dict[str, Any]]:
    """Normalize question-tool data shared by every interaction surface.

    Older model calls sometimes describe a multi-select or text supplement in
    prose but omit its structured flag.  The wording fallback keeps those
    calls usable while current calls use the explicit schema fields.
    """
    if not isinstance(raw_questions, list):
        return []

    questions: list[dict[str, Any]] = []
    for index, item in enumerate(raw_questions):
        if not isinstance(item, dict):
            continue

        options = []
        for option in item.get("options") or []:
            if isinstance(option, str):
                label, description = option.strip(), ""
            elif isinstance(option, dict):
                label = _question_text(option.get("label"), "")
                description = str(option.get("description", "")).strip()
            else:
                continue
            if label:
                options.append({"label": label, "description": description})

        header = _question_text(item.get("header"), f"问题 {index + 1}")
        question = _question_text(item.get("question"), header)
        option_text = " ".join(
            f"{option['label']} {option['description']}" for option in options
        )
        wording = f"{header} {question} {option_text}"

        # Explicit false plus a visible "可多选" is internally inconsistent.
        # Favor the visible instruction so the UI does not prohibit the choice.
        multiple = _question_bool(item.get("multiple"), False) or bool(
            _MULTIPLE_CHOICE_CUE.search(wording)
        )

        raw_free_text = item.get("free_text")
        free_text_config = raw_free_text if isinstance(raw_free_text, dict) else {}
        allow_free_text = _question_bool(
            item.get(
                "allow_free_text",
                free_text_config.get("enabled", free_text_config.get("allow")),
            ),
            False,
        ) or bool(_FREE_TEXT_CUE.search(wording))
        free_text_required = _question_bool(
            item.get("free_text_required", free_text_config.get("required")),
            False,
        )
        selection_required = _question_bool(
            item.get("selection_required"),
            True,
        )

        # A text-only prompt is valid when the tool explicitly requests it.
        if not options and not allow_free_text:
            continue

        questions.append(
            {
                "header": header,
                "question": question,
                "multiple": multiple,
                "selection_required": selection_required,
                "allow_free_text": allow_free_text,
                "free_text_label": _question_text(
                    item.get("free_text_label", free_text_config.get("label")),
                    "补充说明",
                ),
                "free_text_placeholder": _question_text(
                    item.get(
                        "free_text_placeholder",
                        free_text_config.get("placeholder"),
                    ),
                    "可补充具体要求、名称或未列出的信息",
                ),
                "free_text_required": free_text_required,
                "options": options,
            }
        )
    return questions


class AgentState(TypedDict):
    """Serializable graph state persisted by the configured checkpointer."""

    messages: Annotated[list[AnyMessage], add_messages]
    system_prompt: str
    pending_calls: list[dict[str, Any]]
    pending_index: int
    loop_guard: dict[str, Any]
    step_count: int
    max_steps: int
    status: str
    final_content: str
    allow_all: bool
    thread_id: str
    run_id: str
    tool_prepared_at: dict[str, int]
    last_compression_step: NotRequired[int]
    error: NotRequired[str]


@dataclass(frozen=True)
class PendingInterrupt:
    kind: Literal["question", "approval"]
    value: dict[str, Any]
    interrupt_id: str = ""


@dataclass(frozen=True)
class RunResult:
    status: Literal["complete", "waiting", "cancelled", "error"]
    thread_id: str
    run_id: str
    content: str = ""
    pending: Optional[PendingInterrupt] = None
    error: str = ""


@dataclass
class _RuntimeBinding:
    emit: EventCallback
    runtime: dict[str, Any]
    pending_model_inputs: list[dict[str, Any]] = field(default_factory=list)


def create_checkpoint_saver(
    path: Optional[str | Path] = None,
) -> BaseCheckpointSaver[Any]:
    """Create an in-memory saver or a durable SQLite saver."""
    if path is None:
        return InMemorySaver()
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
    except ImportError as exc:
        raise RuntimeError(
            "SQLite checkpoints require langgraph-checkpoint-sqlite"
        ) from exc

    checkpoint_path = Path(path).expanduser().resolve()
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(checkpoint_path), check_same_thread=False)
    return SqliteSaver(connection)


class LangGraphRunner:
    """Run a model/tool loop with ordered tools and durable human interrupts.

    ``thread_id`` is the task/conversation identifier. ``run_id`` identifies one
    user submission and is included in emitted events, but does not affect the
    checkpoint namespace.
    """

    def __init__(
        self,
        model: BaseChatModel,
        tool_definitions: Sequence[dict[str, Any] | BaseTool],
        tool_executor: ToolExecutor,
        *,
        checkpointer: Optional[BaseCheckpointSaver[Any]] = None,
        requires_approval: Optional[ApprovalPredicate] = None,
        max_steps: int = 20,
    ) -> None:
        self.model = model
        self.tool_executor = tool_executor
        self.requires_approval = requires_approval or (lambda _name, _args: False)
        self.max_steps = max(1, int(max_steps))
        self.checkpointer = checkpointer or InMemorySaver()
        self.tools = self._build_tools(tool_definitions)
        self.tools_by_name = {tool.name: tool for tool in self.tools}
        self.model_with_tools = self._bind_tools(self.tools)
        self.tools_without_plan = [
            tool
            for tool in self.tools
            if tool.name not in {"todo_write", "update_plan"}
        ]
        self.model_without_plan = (
            self.model_with_tools
            if len(self.tools_without_plan) == len(self.tools)
            else self._bind_tools(self.tools_without_plan)
        )
        self.tools_without_question = [
            tool for tool in self.tools if tool.name != "question"
        ]
        self.model_without_question = (
            self.model_with_tools
            if len(self.tools_without_question) == len(self.tools)
            else self._bind_tools(self.tools_without_question)
        )
        self.tools_without_plan_or_question = [
            tool for tool in self.tools_without_plan if tool.name != "question"
        ]
        if len(self.tools_without_plan_or_question) == len(self.tools_without_plan):
            self.model_without_plan_or_question = self.model_without_plan
        elif len(self.tools_without_plan_or_question) == len(
            self.tools_without_question
        ):
            self.model_without_plan_or_question = self.model_without_question
        else:
            self.model_without_plan_or_question = self._bind_tools(
                self.tools_without_plan_or_question
            )
        self._bindings: dict[str, _RuntimeBinding] = {}
        self._bindings_lock = threading.RLock()
        self.graph = self._build_graph()

    def run(
        self,
        thread_id: str,
        messages: str | BaseMessage | Sequence[BaseMessage | Mapping[str, Any]],
        *,
        system_prompt: str = "",
        runtime: Optional[dict[str, Any]] = None,
        emit: Optional[EventCallback] = None,
        run_id: Optional[str] = None,
    ) -> RunResult:
        """Start one new run and stream events to ``emit`` synchronously."""
        normalized_thread = self._validate_thread_id(thread_id)
        if self.get_pending(normalized_thread):
            raise RuntimeError(
                "This conversation is waiting for a question or approval response"
            )
        normalized_run = str(run_id or uuid.uuid4().hex)
        input_messages = self._normalize_messages(messages)
        state: AgentState = {
            "messages": input_messages,
            "system_prompt": str(system_prompt or ""),
            "pending_calls": [],
            "pending_index": 0,
            "loop_guard": {},
            "step_count": 0,
            "max_steps": self.max_steps,
            "status": "running",
            "final_content": "",
            "allow_all": bool((runtime or {}).get("allow_all", False)),
            "thread_id": normalized_thread,
            "run_id": normalized_run,
            "tool_prepared_at": {},
        }
        return self._execute(
            normalized_thread,
            state,
            runtime=runtime,
            emit=emit,
            run_id=normalized_run,
        )

    def resume(
        self,
        thread_id: str,
        resume: dict[str, Any],
        *,
        runtime: Optional[dict[str, Any]] = None,
        emit: Optional[EventCallback] = None,
        run_id: Optional[str] = None,
    ) -> RunResult:
        """Resume the interrupt currently pending for ``thread_id``."""
        normalized_thread = self._validate_thread_id(thread_id)
        pending = self.get_pending(normalized_thread)
        if not pending:
            raise RuntimeError("This conversation has no pending interrupt")
        state = self.graph.get_state(self._config(normalized_thread))
        current_run = str(
            run_id or state.values.get("run_id") or uuid.uuid4().hex
        )
        resume_value = dict(resume or {})
        if pending.kind == "approval" and "preparation_duration_ms" in pending.value:
            resume_value.setdefault(
                "_preparation_duration_ms",
                int(pending.value.get("preparation_duration_ms", 0) or 0),
            )
        return self._execute(
            normalized_thread,
            Command(resume=resume_value),
            runtime=runtime,
            emit=emit,
            run_id=current_run,
        )

    def get_pending(self, thread_id: str) -> Optional[PendingInterrupt]:
        snapshot = self.graph.get_state(self._config(self._validate_thread_id(thread_id)))
        for task in snapshot.tasks:
            for item in task.interrupts:
                value = item.value if isinstance(item.value, dict) else {}
                kind = value.get("kind")
                if kind in {"question", "approval"}:
                    return PendingInterrupt(kind, dict(value), str(item.id))
        return None

    def delete_thread(self, thread_id: str) -> None:
        normalized_thread = self._validate_thread_id(thread_id)
        self.checkpointer.delete_thread(normalized_thread)
        with self._bindings_lock:
            self._bindings.pop(normalized_thread, None)

    def list_checkpoint_thread_ids(self) -> list[str]:
        """Return checkpoint thread IDs without loading their saved state."""
        sqlite_saver = self._sqlite_checkpointer()
        if sqlite_saver is not None:
            with sqlite_saver.cursor(transaction=False) as cursor:
                rows = cursor.execute(
                    "SELECT DISTINCT thread_id FROM checkpoints "
                    "UNION SELECT DISTINCT thread_id FROM writes"
                ).fetchall()
            return [str(row[0]) for row in rows if row and row[0] is not None]

        storage = getattr(self.checkpointer, "storage", None)
        if isinstance(storage, Mapping):
            return [str(thread_id) for thread_id in storage]

        thread_ids: set[str] = set()
        for checkpoint in self.checkpointer.list(None):
            configurable = checkpoint.config.get("configurable", {})
            thread_id = configurable.get("thread_id")
            if thread_id:
                thread_ids.add(str(thread_id))
        return sorted(thread_ids)

    def delete_threads_with_prefix(self, prefix: str) -> int:
        """Delete every checkpoint thread whose ID starts with ``prefix``.

        Desktop tasks use one graph thread for each submitted message, so an
        exact ``delete_thread`` call cannot remove all interrupted runs for a
        deleted task.  The SQLite path deliberately uses SQL rather than the
        saver iterator so large snapshots are never deserialized just to find
        their thread IDs.
        """
        normalized_prefix = str(prefix or "").strip()
        if not normalized_prefix:
            raise ValueError("thread prefix is required")

        sqlite_saver = self._sqlite_checkpointer()
        if sqlite_saver is not None:
            pattern = self._sqlite_like_prefix(normalized_prefix)
            with sqlite_saver.cursor() as cursor:
                rows = cursor.execute(
                    "SELECT DISTINCT thread_id FROM checkpoints "
                    "WHERE thread_id LIKE ? ESCAPE '\\' "
                    "UNION SELECT DISTINCT thread_id FROM writes "
                    "WHERE thread_id LIKE ? ESCAPE '\\'",
                    (pattern, pattern),
                ).fetchall()
                cursor.execute(
                    "DELETE FROM writes WHERE thread_id LIKE ? ESCAPE '\\'",
                    (pattern,),
                )
                cursor.execute(
                    "DELETE FROM checkpoints WHERE thread_id LIKE ? ESCAPE '\\'",
                    (pattern,),
                )
            removed = len(rows)
        else:
            thread_ids = [
                thread_id
                for thread_id in self.list_checkpoint_thread_ids()
                if thread_id.startswith(normalized_prefix)
            ]
            for thread_id in thread_ids:
                self.delete_thread(thread_id)
            removed = len(thread_ids)

        with self._bindings_lock:
            for thread_id in tuple(self._bindings):
                if thread_id.startswith(normalized_prefix):
                    self._bindings.pop(thread_id, None)
        return removed

    def vacuum_checkpoint_store(self) -> bool:
        """Compact the durable SQLite checkpoint file after explicit cleanup."""
        sqlite_saver = self._sqlite_checkpointer()
        if sqlite_saver is None:
            return False

        connection = sqlite_saver.conn
        lock = getattr(sqlite_saver, "lock", None)
        if not isinstance(connection, sqlite3.Connection) or lock is None:
            return False

        try:
            with lock:
                setup = getattr(sqlite_saver, "setup", None)
                if callable(setup):
                    setup()
                connection.commit()
                connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").close()
                connection.execute("VACUUM").close()
            return True
        except (sqlite3.Error, OSError):
            # Deletion has already committed.  A busy second process or an
            # insufficient temporary-disk budget must not undo task removal.
            return False

    def cancel(self, thread_id: str) -> None:
        """Request cancellation when the active runtime exposes a cancel event."""
        with self._bindings_lock:
            binding = self._bindings.get(self._validate_thread_id(thread_id))
        if not binding:
            return
        cancel_event = binding.runtime.get("cancel_event")
        if hasattr(cancel_event, "set"):
            cancel_event.set()

    def _build_graph(self) -> Any:
        builder = StateGraph(AgentState)
        builder.add_node("model", self._model_node)
        builder.add_node("tools", self._tools_node)
        builder.add_node("compact", self._compact_node)
        builder.add_node("finish", self._finish_node)
        # Check persistent recent memory before the first model turn as well as
        # between tool batches, so an already-full context never enters the API.
        builder.add_edge(START, "compact")
        builder.add_conditional_edges(
            "model",
            self._route_after_model,
            {"tools": "tools", "finish": "finish"},
        )
        builder.add_conditional_edges(
            "tools",
            self._route_after_tools,
            {"compact": "compact", "tools": "tools", "finish": "finish"},
        )
        builder.add_edge("compact", "model")
        builder.add_edge("finish", END)
        return builder.compile(checkpointer=self.checkpointer)

    def _model_node(self, state: AgentState) -> dict[str, Any]:
        binding = self._binding(state)
        self._raise_if_cancelled(binding)
        next_step = int(state.get("step_count", 0)) + 1
        if next_step > int(state.get("max_steps", self.max_steps)):
            content = f"任务已达到最大步数限制（{state.get('max_steps', self.max_steps)}）"
            return {"status": "complete", "final_content": content}

        stream_id = f"{state.get('run_id', '')}:{next_step}"
        self._emit(binding, "model_start", stream_id=stream_id, step=next_step)
        messages: list[BaseMessage] = []
        if state.get("system_prompt"):
            messages.append(SystemMessage(content=state["system_prompt"]))
        messages.extend(state["messages"])
        transient_inputs = self._take_model_inputs(binding)
        if transient_inputs:
            messages.append(
                HumanMessage(
                    content=[
                        {
                            "type": "text",
                            "text": (
                                "The image requested with view_image is attached below. "
                                "Inspect it and continue the current task."
                            ),
                        },
                        *transient_inputs,
                    ]
                )
            )

        assembled: Optional[AIMessageChunk] = None
        announced_tools: set[tuple[int, str]] = set()
        prepared_at: dict[str, int] = {}
        cancellation_scope = getattr(self.model, "cancellation_scope", None)
        scope = (
            cancellation_scope(lambda: self._is_binding_cancelled(binding))
            if callable(cancellation_scope)
            else nullcontext()
        )
        if binding.runtime.get("voice_mode", False):
            model = (
                self.model_without_question
                if binding.runtime.get("plan_enabled", True)
                else self.model_without_plan_or_question
            )
        else:
            model = (
                self.model_with_tools
                if binding.runtime.get("plan_enabled", True)
                else self.model_without_plan
            )
        with scope:
            for chunk in model.stream(messages):
                self._raise_if_cancelled(binding)
                if not isinstance(chunk, AIMessageChunk):
                    continue
                clean_chunk = chunk.model_copy(
                    update={
                        "additional_kwargs": self._strip_reasoning_metadata(
                            chunk.additional_kwargs
                        )
                    }
                )
                assembled = (
                    clean_chunk if assembled is None else assembled + clean_chunk
                )
                self._emit_message_chunk(
                    binding, chunk, stream_id, announced_tools, prepared_at
                )
        self._raise_if_cancelled(binding)

        response = (
            AIMessage(content="")
            if assembled is None
            else AIMessage(
                content=assembled.content,
                additional_kwargs=assembled.additional_kwargs,
                response_metadata=assembled.response_metadata,
                tool_calls=assembled.tool_calls,
                invalid_tool_calls=assembled.invalid_tool_calls,
            )
        )
        response = response.model_copy(
            update={
                "content": self._strip_reasoning(self._message_text(response)),
                "additional_kwargs": self._strip_reasoning_metadata(
                    response.additional_kwargs
                ),
            }
        )
        pending_calls = []
        for index, raw_call in enumerate(response.tool_calls):
            call = dict(raw_call)
            if not call.get("id"):
                call["id"] = f"call-{state.get('run_id', '')}-{next_step}-{index}"
            pending_calls.append(call)
        if pending_calls != response.tool_calls:
            response = response.model_copy(update={"tool_calls": pending_calls})
        self._emit(
            binding,
            "model_end",
            stream_id=stream_id,
            content=self._message_text(response),
            tool_calls=pending_calls,
        )
        if pending_calls:
            return {
                "messages": [response],
                "pending_calls": pending_calls,
                "pending_index": 0,
                "step_count": next_step,
                "status": "running",
                "tool_prepared_at": prepared_at,
            }
        return {
            "messages": [response],
            "pending_calls": [],
            "pending_index": 0,
            "step_count": next_step,
            "status": "complete",
            "final_content": self._message_text(response),
            "tool_prepared_at": prepared_at,
        }

    def _tools_node(self, state: AgentState) -> dict[str, Any]:
        binding = self._binding(state)
        self._raise_if_cancelled(binding)
        calls = list(state.get("pending_calls") or [])
        index = int(state.get("pending_index", 0))
        if index >= len(calls):
            return {"pending_calls": [], "pending_index": 0}

        call = calls[index]
        name = str(call.get("name", ""))
        args = dict(call.get("args") or {})
        tool_call_id = str(call.get("id", ""))
        prepared_id = f"{state.get('run_id', '')}:{state.get('step_count', 0)}:{index}"
        stream_id = f"{state.get('run_id', '')}:{state.get('step_count', 0)}"

        if (
            name in {"todo_write", "update_plan"}
            and not binding.runtime.get("plan_enabled", True)
        ):
            content = f"Error: {name} is disabled because Plan Mode is off"
            self._emit(
                binding,
                "tool_end",
                tool=name,
                params=args,
                result=content,
                failed=True,
                disabled=True,
                tool_call_id=tool_call_id,
                prepared_tool_call_id=prepared_id,
                stream_id=stream_id,
                duration_ms=0,
                execution_duration_ms=0,
            )
            return {
                "messages": [
                    ToolMessage(
                        content=content,
                        name=name,
                        tool_call_id=tool_call_id,
                        status="error",
                    )
                ],
                "pending_index": index + 1,
            }

        if name == "question" and binding.runtime.get("voice_mode", False):
            content = "Error: question is disabled in voice conversation mode"
            self._emit(
                binding,
                "tool_end",
                tool=name,
                params=args,
                result=content,
                failed=True,
                disabled=True,
                tool_call_id=tool_call_id,
                prepared_tool_call_id=prepared_id,
                stream_id=stream_id,
                duration_ms=0,
                execution_duration_ms=0,
            )
            return {
                "messages": [
                    ToolMessage(
                        content=content,
                        name=name,
                        tool_call_id=tool_call_id,
                        status="error",
                    )
                ],
                "pending_index": index + 1,
            }

        if name == "question":
            questions = self._normalize_questions(args)
            if not questions:
                content = "question 工具没有提供可显示的选项，请重新发起提问"
                self._emit(
                    binding,
                    "tool_end",
                    tool=name,
                    params=args,
                    result=content,
                    failed=True,
                    tool_call_id=tool_call_id,
                    prepared_tool_call_id=prepared_id,
                    stream_id=stream_id,
                    duration_ms=0,
                    execution_duration_ms=0,
                )
                return {
                    "messages": [
                        ToolMessage(
                            content=content,
                            name=name,
                            tool_call_id=tool_call_id,
                            status="error",
                        )
                    ],
                    "pending_index": index + 1,
                }
            payload = {
                "kind": "question",
                "questions": questions,
                "tool": name,
                "params": args,
                "tool_call_id": tool_call_id,
                "prepared_tool_call_id": prepared_id,
                "stream_id": stream_id,
            }
            answer = interrupt(payload)
            content = self._question_result(answer)
            self._emit(
                binding,
                "question_answered",
                tool_call_id=tool_call_id,
                prepared_tool_call_id=prepared_id,
                stream_id=stream_id,
                content=content,
                resume=answer,
            )
            return {
                "messages": [
                    ToolMessage(
                        content=content, name=name, tool_call_id=tool_call_id
                    )
                ],
                "pending_index": index + 1,
            }

        guard = ToolLoopGuard()
        guard.restore(state.get("loop_guard"))
        guard_decision = guard.before_call(name, args)

        preparation_duration_ms: Optional[int] = None
        if (
            guard_decision["action"] == "execute"
            and self.requires_approval(name, args)
            and not state.get("allow_all", False)
        ):
            prepared_started_at_ms = int(
                state.get("tool_prepared_at", {}).get(prepared_id)
                or int(time.time() * 1000)
            )
            preparation_duration_ms = max(
                0, int(time.time() * 1000) - prepared_started_at_ms
            )
            payload = {
                "kind": "approval",
                "tool": name,
                "params": args,
                "tool_call_id": tool_call_id,
                "prepared_tool_call_id": prepared_id,
                "stream_id": stream_id,
                "preparation_duration_ms": preparation_duration_ms,
            }
            decision = interrupt(payload)
            preparation_duration_ms = max(
                0,
                int(
                    (decision or {}).get(
                        "_preparation_duration_ms", preparation_duration_ms
                    )
                    or 0
                ),
            )
            action = str((decision or {}).get("action", "deny")).lower()
            if action == "deny":
                content = "用户拒绝执行此操作"
                self._emit(
                    binding,
                    "tool_end",
                    tool=name,
                    params=args,
                    result=content,
                    failed=True,
                    tool_call_id=tool_call_id,
                    prepared_tool_call_id=prepared_id,
                    stream_id=stream_id,
                    duration_ms=0,
                    execution_duration_ms=0,
                )
                return {
                    "messages": [
                        ToolMessage(
                            content=content,
                            name=name,
                            tool_call_id=tool_call_id,
                            status="error",
                        )
                    ],
                    "pending_index": index + 1,
                }
            allow_all = action == "all"
        else:
            allow_all = bool(state.get("allow_all", False))

        started_at = time.monotonic()
        if preparation_duration_ms is None:
            started_at_ms = int(
                state.get("tool_prepared_at", {}).get(prepared_id)
                or int(time.time() * 1000)
            )
        else:
            started_at_ms = int(time.time() * 1000) - preparation_duration_ms
        self._emit(
            binding,
            "tool_start",
            tool=name,
            params=args,
            tool_call_id=tool_call_id,
            prepared_tool_call_id=prepared_id,
            stream_id=stream_id,
            started_at_ms=started_at_ms,
        )
        model_inputs: list[dict[str, Any]] = []
        if guard_decision["action"] == "execute":
            self._raise_if_cancelled(binding)
            raw_result = self._execute_tool(name, args, binding)
            # A non-cooperative tool may return after the user has already
            # cancelled. Never checkpoint or emit that stale result.
            self._raise_if_cancelled(binding)
            result = self._tool_result_text(raw_result)
            model_inputs = self._tool_result_model_inputs(raw_result)
            guard.record_result(
                name,
                args,
                result,
                guard_decision["signature"],
                guard_decision["kind"],
            )
        else:
            result = str(guard_decision["result"])
        self._raise_if_cancelled(binding)
        execution_duration_ms = int(max(0.0, time.monotonic() - started_at) * 1000)
        duration_ms = max(0, int(time.time() * 1000) - started_at_ms)
        failed = not ToolLoopGuard._succeeded(result)
        self._emit(
            binding,
            "tool_end",
            tool=name,
            params=args,
            result=result,
            failed=failed,
            tool_call_id=tool_call_id,
            prepared_tool_call_id=prepared_id,
            stream_id=stream_id,
            duration_ms=duration_ms,
            execution_duration_ms=execution_duration_ms,
        )
        if model_inputs and not failed:
            self._queue_model_inputs(binding, model_inputs)
        return {
            "messages": [
                ToolMessage(
                    content=result,
                    name=name,
                    tool_call_id=tool_call_id,
                    status="error" if failed else "success",
                )
            ],
            "pending_index": index + 1,
            "loop_guard": guard.snapshot(),
            "allow_all": allow_all,
        }

    def _finish_node(self, state: AgentState) -> dict[str, Any]:
        binding = self._binding(state)
        self._raise_if_cancelled(binding)
        content = str(state.get("final_content", ""))
        self._emit(binding, "final", content=content)
        return {"status": "complete"}

    def _compact_node(self, state: AgentState) -> dict[str, Any]:
        """Compact task context at the safe boundary before the next model turn."""
        binding = self._binding(state)
        self._raise_if_cancelled(binding)
        step = int(state.get("step_count", 0) or 0)
        base_update: dict[str, Any] = {
            "pending_calls": [],
            "pending_index": 0,
            "tool_prepared_at": {},
            "last_compression_step": step,
        }
        last_compression_step = state.get("last_compression_step")
        if (
            last_compression_step is not None
            and int(last_compression_step) == step
        ):
            return base_update

        check = binding.runtime.get("compression_check")
        handler = binding.runtime.get("compression_handler")
        if not callable(check) or not callable(handler):
            return base_update

        try:
            snapshot = check(dict(state))
        except Exception:
            return base_update
        self._raise_if_cancelled(binding)
        if not isinstance(snapshot, Mapping) or not snapshot:
            return base_update

        compression_id = str(
            snapshot.get("compression_id")
            or f"auto:{state.get('run_id', '')}:{step}"
        )
        start_payload = {
            "compression_id": compression_id,
            "mode": "auto",
            "task_continues": True,
            "step": step,
            "tokens_before": int(snapshot.get("tokens_before", 0) or 0),
            "step_count": int(snapshot.get("step_count", 0) or 0),
            "threshold": int(snapshot.get("threshold", 0) or 0),
            "started_at_ms": int(time.time() * 1000),
        }
        self._emit(binding, "compression_start", **start_payload)

        def progress(stage: str, content: str) -> None:
            self._raise_if_cancelled(binding)
            self._emit(
                binding,
                "compression_progress",
                compression_id=compression_id,
                mode="auto",
                task_continues=True,
                step=step,
                stage=str(stage or ""),
                content=str(content or ""),
            )

        try:
            raw_result = handler(dict(state), dict(snapshot), progress)
            result = dict(raw_result or {})
        except _Cancelled:
            raise
        except Exception as exc:
            result = {
                "success": False,
                "status": "error",
                "message": f"自动压缩失败: {exc}",
                "tokens_before": int(snapshot.get("tokens_before", 0) or 0),
                "tokens_after": int(snapshot.get("tokens_before", 0) or 0),
                "released_tokens": 0,
                "step_count": int(snapshot.get("step_count", 0) or 0),
            }
        self._raise_if_cancelled(binding)

        replacement_messages = result.pop("replacement_messages", None)
        refreshed_system_prompt = result.pop("system_prompt", None)
        for reserved_key in ("compression_id", "mode", "task_continues", "step"):
            result.pop(reserved_key, None)
        if result.get("success") and not replacement_messages:
            result.update(
                {
                    "success": False,
                    "status": "error",
                    "message": "压缩摘要已生成，但未能重建任务上下文",
                    "tokens_after": int(snapshot.get("tokens_before", 0) or 0),
                    "released_tokens": 0,
                }
            )

        self._emit(
            binding,
            "compression_end",
            compression_id=compression_id,
            mode="auto",
            task_continues=True,
            step=step,
            **result,
        )
        if not result.get("success"):
            return base_update

        messages = list(replacement_messages or [])
        base_update.update(
            {
                "messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), *messages],
                "status": "running",
                "final_content": "",
            }
        )
        if refreshed_system_prompt is not None:
            base_update["system_prompt"] = str(refreshed_system_prompt)
        return base_update

    @staticmethod
    def _route_after_model(state: AgentState) -> str:
        if state.get("status") == "complete":
            return "finish"
        return "tools"

    @staticmethod
    def _route_after_tools(state: AgentState) -> str:
        if state.get("status") == "complete":
            return "finish"
        if int(state.get("pending_index", 0)) < len(state.get("pending_calls") or []):
            return "tools"
        return "compact"

    def _execute(
        self,
        thread_id: str,
        graph_input: AgentState | Command[Any],
        *,
        runtime: Optional[dict[str, Any]],
        emit: Optional[EventCallback],
        run_id: str,
    ) -> RunResult:
        callback = emit or (lambda _event: None)
        runtime_values = dict(runtime or {})
        runtime_values["thread_id"] = thread_id
        runtime_values["run_id"] = run_id
        with self._bindings_lock:
            self._bindings[thread_id] = _RuntimeBinding(callback, runtime_values)
        try:
            for update in self.graph.stream(
                graph_input,
                self._config(thread_id),
                stream_mode="updates",
                durability="sync",
            ):
                interrupts = update.get("__interrupt__") if isinstance(update, dict) else None
                if interrupts:
                    item = interrupts[0]
                    value = item.value if isinstance(item.value, dict) else {}
                    pending = PendingInterrupt(
                        value.get("kind", "approval"), dict(value), str(item.id)
                    )
                    callback(
                        self._event(
                            "interrupt", thread_id, run_id, **pending.value
                        )
                    )
                    return RunResult("waiting", thread_id, run_id, pending=pending)
            snapshot = self.graph.get_state(self._config(thread_id))
            status = str(snapshot.values.get("status", "complete"))
            if status == "cancelled":
                return RunResult("cancelled", thread_id, run_id)
            return RunResult(
                "complete",
                thread_id,
                run_id,
                content=str(snapshot.values.get("final_content", "")),
            )
        except _Cancelled:
            callback(self._event("cancelled", thread_id, run_id))
            return RunResult("cancelled", thread_id, run_id)
        except Exception as exc:
            callback(self._event("error", thread_id, run_id, error=str(exc)))
            return RunResult("error", thread_id, run_id, error=str(exc))
        finally:
            with self._bindings_lock:
                self._bindings.pop(thread_id, None)

    def _binding(self, state: AgentState) -> _RuntimeBinding:
        thread_id = str(state.get("thread_id", ""))
        with self._bindings_lock:
            binding = self._bindings.get(thread_id)
            if binding:
                return binding
        raise RuntimeError("No active runtime binding for graph execution")

    def _execute_tool(
        self, name: str, args: dict[str, Any], binding: _RuntimeBinding
    ) -> Any:
        runtime = binding.runtime
        try:
            signature = inspect.signature(self.tool_executor)
        except (TypeError, ValueError) as exc:
            raise TypeError("tool_executor must have an inspectable signature") from exc
        candidates = (
            (name, args, runtime),
            (name, args),
            ({"tool": name, "params": args},),
        )
        for candidate in candidates:
            try:
                signature.bind(*candidate)
            except TypeError:
                continue
            return self.tool_executor(*candidate)
        raise TypeError(
            "tool_executor must accept (name, args, runtime), (name, args), "
            "or one {'tool', 'params'} mapping"
        )

    @staticmethod
    def _tool_result_text(result: Any) -> str:
        if isinstance(result, ToolExecutionResult):
            return str(result.content)
        return str(result or "")

    @staticmethod
    def _tool_result_model_inputs(result: Any) -> list[dict[str, Any]]:
        if not isinstance(result, ToolExecutionResult):
            return []
        return [
            dict(item)
            for item in result.model_inputs
            if isinstance(item, Mapping)
        ]

    @staticmethod
    def _queue_model_inputs(
        binding: _RuntimeBinding, inputs: Sequence[Mapping[str, Any]]
    ) -> None:
        binding.pending_model_inputs.extend(
            dict(item) for item in inputs if isinstance(item, Mapping)
        )

    @staticmethod
    def _take_model_inputs(binding: _RuntimeBinding) -> list[dict[str, Any]]:
        inputs = binding.pending_model_inputs
        binding.pending_model_inputs = []
        return inputs

    def _build_tools(
        self, definitions: Sequence[dict[str, Any] | BaseTool]
    ) -> list[BaseTool]:
        tools: list[BaseTool] = []
        for definition in definitions:
            if isinstance(definition, BaseTool):
                tools.append(definition)
                continue
            function = definition.get("function", definition)
            name = str(function.get("name", "")).strip()
            if not name:
                continue
            description = str(function.get("description", name))
            schema = dict(function.get("parameters") or {"type": "object"})

            def placeholder(**_kwargs: Any) -> str:
                raise RuntimeError("Tools are executed by LangGraphRunner")

            tools.append(
                StructuredTool(
                    name=name,
                    description=description,
                    args_schema=schema,
                    func=placeholder,
                )
            )
        return tools

    def _bind_tools(self, tools: Sequence[BaseTool]) -> Any:
        """Bind one immutable tool set for a runtime policy."""
        if not tools:
            return self.model
        return self.model.bind_tools(
            list(tools), tool_choice="auto", parallel_tool_calls=False
        )

    def _emit_message_chunk(
        self,
        binding: _RuntimeBinding,
        chunk: AIMessageChunk,
        stream_id: str,
        announced_tools: set[tuple[int, str]],
        prepared_at: dict[str, int],
    ) -> None:
        reasoning = str(chunk.additional_kwargs.get("reasoning_content", "") or "")
        if reasoning:
            self._emit(binding, "reasoning_delta", stream_id=stream_id, content=reasoning)
        text = self._message_text(chunk)
        if text:
            self._emit(binding, "content_delta", stream_id=stream_id, content=text)
        tool_delta = chunk.additional_kwargs.get("tool_delta")
        if isinstance(tool_delta, dict):
            name = str(tool_delta.get("name", ""))
            index = int(tool_delta.get("index", 0) or 0)
            key = (index, name)
            if name in self.tools_by_name and key not in announced_tools:
                announced_tools.add(key)
                prepared_id = f"{stream_id}:{index}"
                started_at_ms = int(time.time() * 1000)
                prepared_at[prepared_id] = started_at_ms
                self._emit(
                    binding,
                    "tool_preparing",
                    stream_id=stream_id,
                    tool=name,
                    tool_call_id=prepared_id,
                    prepared_tool_call_id=prepared_id,
                    started_at_ms=started_at_ms,
                    arguments_length=int(
                        tool_delta.get("arguments_length", 0) or 0
                    ),
                )

    def _emit(self, binding: _RuntimeBinding, event_type: str, **payload: Any) -> None:
        runtime = binding.runtime
        event = self._event(
            event_type,
            str(runtime.get("thread_id", "")),
            str(runtime.get("run_id", "")),
            **payload,
        )
        binding.emit(event)

    @staticmethod
    def _event(
        event_type: str, thread_id: str, run_id: str, **payload: Any
    ) -> dict[str, Any]:
        return {"type": event_type, "thread_id": thread_id, "run_id": run_id, **payload}

    @staticmethod
    def _normalize_messages(
        messages: str | BaseMessage | Sequence[BaseMessage | Mapping[str, Any]],
    ) -> list[BaseMessage]:
        if isinstance(messages, str):
            return [HumanMessage(content=messages)]
        if isinstance(messages, BaseMessage):
            return [messages]
        return list(convert_to_messages(list(messages)))

    @staticmethod
    def _normalize_questions(args: dict[str, Any]) -> list[dict[str, Any]]:
        normalized_args: Any = args
        if set(args) == {"_raw"} and isinstance(args.get("_raw"), str):
            try:
                normalized_args = json.loads(args["_raw"])
            except json.JSONDecodeError:
                return []
        if isinstance(normalized_args, list):
            raw_questions = normalized_args
        elif isinstance(normalized_args, dict):
            raw_questions = normalized_args.get("questions")
            if raw_questions is None:
                raw_questions = normalized_args.get("_items")
            if raw_questions is None and "options" in normalized_args:
                raw_questions = [normalized_args]
        else:
            return []
        if not isinstance(raw_questions, list):
            return []

        return normalize_question_payload(raw_questions)

    @staticmethod
    def _question_result(answer: Any) -> str:
        if isinstance(answer, dict):
            if answer.get("content"):
                return str(answer["content"])
            answers = answer.get("answers")
            if isinstance(answers, list):
                supplements = answer.get("supplements", [])
                lines = []
                for index, raw_answer in enumerate(answers, 1):
                    if isinstance(raw_answer, list):
                        selected = [str(item).strip() for item in raw_answer]
                    elif raw_answer is None:
                        selected = []
                    else:
                        selected = [str(raw_answer).strip()]
                    supplement = ""
                    if isinstance(supplements, list) and index - 1 < len(supplements):
                        supplement = str(supplements[index - 1] or "").strip()
                    parts = [", ".join(item for item in selected if item)]
                    if supplement:
                        parts.append(f"补充：{supplement}")
                    lines.append(f"- 问题 {index}: {'；'.join(part for part in parts if part)}")
                return "用户已回答 question 工具：\n" + "\n".join(lines)
        return f"用户已回答 question 工具：{answer}"

    @staticmethod
    def _message_text(message: BaseMessage) -> str:
        if isinstance(message.content, str):
            return message.content
        parts = []
        for block in message.content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts)

    @staticmethod
    def _strip_reasoning(content: str) -> str:
        return re.sub(r"<think>[\s\S]*?</think>\s*", "", content).strip()

    @staticmethod
    def _strip_reasoning_metadata(value: Mapping[str, Any]) -> dict[str, Any]:
        return {
            str(key): item
            for key, item in value.items()
            if key
            not in {
                "reasoning_content",
                "reasoning",
                "thinking",
                "tool_delta",
            }
        }

    @staticmethod
    def _config(thread_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": thread_id}}

    def _sqlite_checkpointer(self) -> Any | None:
        """Return the SQLite saver when this runner uses the bundled backend."""
        saver = self.checkpointer
        connection = getattr(saver, "conn", None)
        cursor = getattr(saver, "cursor", None)
        if isinstance(connection, sqlite3.Connection) and callable(cursor):
            return saver
        return None

    @staticmethod
    def _sqlite_like_prefix(prefix: str) -> str:
        """Escape a literal prefix for SQLite LIKE with a backslash escape."""
        escaped = prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        return f"{escaped}%"

    @staticmethod
    def _validate_thread_id(thread_id: str) -> str:
        value = str(thread_id or "").strip()
        if not value:
            raise ValueError("thread_id is required")
        return value

    @staticmethod
    def _raise_if_cancelled(binding: _RuntimeBinding) -> None:
        runtime = binding.runtime
        predicate = runtime.get("cancelled")
        if callable(predicate) and predicate():
            raise _Cancelled()
        cancel_event = runtime.get("cancel_event")
        if hasattr(cancel_event, "is_set") and cancel_event.is_set():
            raise _Cancelled()

    @staticmethod
    def _is_binding_cancelled(binding: _RuntimeBinding) -> bool:
        runtime = binding.runtime
        predicate = runtime.get("cancelled")
        if callable(predicate):
            try:
                if predicate():
                    return True
            except Exception:
                pass
        cancel_event = runtime.get("cancel_event")
        return bool(
            hasattr(cancel_event, "is_set") and cancel_event.is_set()
        )


class _Cancelled(RuntimeError):
    pass


__all__ = [
    "AgentState",
    "LangGraphRunner",
    "PendingInterrupt",
    "RunResult",
    "create_checkpoint_saver",
]
