"""Core regression tests for the LangChain/LangGraph execution layer."""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Sequence
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.runnables import Runnable
from langchain_core.utils.function_calling import convert_to_openai_tool

from agent.core.ai_engine import ToolCall
from agent.core.langchain_model import AIEngineChatModel
from agent.core.langgraph_runner import (
    LangGraphRunner,
    create_checkpoint_saver,
    normalize_question_payload,
)
from agent.core.tool_loop_guard import ToolLoopGuard


class FakeGraphModel(BaseChatModel):
    responses: list[AIMessage]
    position: int = 0

    @property
    def _llm_type(self) -> str:
        return "os-agent-test"

    def _generate(
        self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs: Any
    ) -> ChatResult:
        message = self.responses[self.position]
        self.position += 1
        return ChatResult(generations=[ChatGeneration(message=message)])

    def _stream(
        self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs: Any
    ):
        message = self.responses[self.position]
        self.position += 1
        yield ChatGenerationChunk(
            message=AIMessageChunk(
                content=message.content,
                additional_kwargs=message.additional_kwargs,
                tool_call_chunks=[
                    {
                        "name": call["name"],
                        "args": json.dumps(call["args"]),
                        "id": call["id"],
                        "index": index,
                        "type": "tool_call_chunk",
                    }
                    for index, call in enumerate(message.tool_calls)
                ],
            )
        )

    def bind_tools(
        self, tools: Sequence[Any], **kwargs: Any
    ) -> Runnable[Any, AIMessage]:
        return self.bind(
            tools=[convert_to_openai_tool(tool) for tool in tools], **kwargs
        )


def _tool_definition(name: str) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": name,
            "parameters": {"type": "object", "properties": {}},
        },
    }


def test_ai_engine_adapter_yields_before_transport_finishes() -> None:
    class StreamingEngine:
        model = "fake"
        max_tokens = 100
        temperature = 0.0
        api_base_url = "http://fake"

        def _post_chat_completion_stream(self, *args, on_content=None, **kwargs):
            on_content("<think>")
            on_content("reasoning")
            time.sleep(0.2)
            on_content("</think>\n")
            on_content("answer")
            return {
                "content": "<think>reasoning</think>\nanswer",
                "tool_calls": [],
                "finish_reason": "stop",
            }

        def call_messages(self, *args, **kwargs):
            return {"content": "answer", "tool_calls": [], "finish_reason": "stop"}

    model = AIEngineChatModel(engine=StreamingEngine())
    stream = model.stream([HumanMessage(content="hello")])
    started = time.monotonic()
    first = next(stream)
    assert time.monotonic() - started < 0.15
    assert first.additional_kwargs["reasoning_content"] == "reasoning"
    list(stream)


def test_ai_engine_adapter_splits_inline_think_tags_across_chunks() -> None:
    class InlineReasoningEngine:
        model = "fake"
        max_tokens = 100
        temperature = 0.0
        api_base_url = "http://fake"

        def _post_chat_completion_stream(self, *args, on_content=None, **kwargs):
            for chunk in ("<thi", "nk>private", " plan</thi", "nk>\nOK"):
                on_content(chunk)
            return {
                "content": "<think>private plan</think>\nOK",
                "tool_calls": [],
                "finish_reason": "stop",
            }

        def call_messages(self, *args, **kwargs):
            return {"content": "OK", "tool_calls": [], "finish_reason": "stop"}

    chunks = list(
        AIEngineChatModel(engine=InlineReasoningEngine()).stream(
            [HumanMessage(content="hello")]
        )
    )
    reasoning = "".join(
        str(chunk.additional_kwargs.get("reasoning_content", ""))
        for chunk in chunks
    )
    content = "".join(
        str(chunk.content) for chunk in chunks if isinstance(chunk.content, str)
    )

    assert reasoning == "private plan"
    assert content.strip() == "OK"


def test_runner_resumes_question_and_does_not_checkpoint_reasoning() -> None:
    question = {
        "name": "question",
        "args": {
            "questions": [
                {
                    "header": "Choice",
                    "question": "Choose",
                    "options": [{"label": "A", "description": "First"}],
                }
            ]
        },
        "id": "question-1",
        "type": "tool_call",
    }
    model = FakeGraphModel(
        responses=[
            AIMessage(
                content="<think>private</think>",
                additional_kwargs={"reasoning_content": "private"},
                tool_calls=[question],
            ),
            AIMessage(content="finished"),
        ]
    )
    events: list[dict[str, Any]] = []
    runner = LangGraphRunner(model, [_tool_definition("question")], lambda *args: "")
    paused = runner.run("thread-1", "start", run_id="run-1", emit=events.append)
    assert paused.status == "waiting"
    assert len([event for event in events if event["type"] == "interrupt"]) == 1

    completed = runner.resume(
        "thread-1",
        {"kind": "question", "answers": [["A"]]},
        run_id="run-1",
        emit=events.append,
    )
    assert completed.status == "complete"
    assert completed.content == "finished"
    snapshot = runner.graph.get_state({"configurable": {"thread_id": "thread-1"}})
    assert "private" not in str(snapshot.values["messages"])


def test_question_normalization_keeps_choice_modes_and_text_supplements() -> None:
    questions = normalize_question_payload(
        [
            {
                "header": "页面",
                "question": "选择要包含的页面（可多选）",
                "multiple": False,
                "options": [{"label": "首页"}],
            },
            {
                "header": "名称",
                "question": "请填写名称（可下面文字补充）",
                "multiple": False,
                "options": [{"label": "直接补充文字"}],
            },
            {
                "header": "说明",
                "question": "补充说明",
                "multiple": False,
                "allow_free_text": True,
                "selection_required": False,
                "free_text_label": "项目要求",
                "free_text_placeholder": "例如：偏好深色模式",
                "options": [],
            },
        ]
    )

    assert questions[0]["multiple"] is True
    assert questions[1]["allow_free_text"] is True
    assert questions[2] == {
        "header": "说明",
        "question": "补充说明",
        "multiple": False,
        "selection_required": False,
        "allow_free_text": True,
        "free_text_label": "项目要求",
        "free_text_placeholder": "例如：偏好深色模式",
        "free_text_required": False,
        "options": [],
    }


def test_tool_executor_type_error_is_not_retried() -> None:
    calls: list[str] = []

    def executor(name: str, args: dict[str, Any]) -> str:
        calls.append(name)
        raise TypeError("raised inside the tool")

    runner = object.__new__(LangGraphRunner)
    runner.tool_executor = executor
    binding = type("Binding", (), {"runtime": {}})()
    try:
        runner._execute_tool("write", {}, binding)
    except TypeError as exc:
        assert str(exc) == "raised inside the tool"
    else:
        raise AssertionError("tool TypeError should propagate")
    assert calls == ["write"]


def test_cancelled_tool_result_is_not_checkpointed_or_emitted() -> None:
    model = FakeGraphModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "write",
                        "args": {"path": "late.txt"},
                        "id": "write-late",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="must not run"),
        ]
    )
    tool_started = threading.Event()
    release_tool = threading.Event()
    cancel_event = threading.Event()
    events: list[dict[str, Any]] = []
    results = []

    def executor(name: str, args: dict[str, Any], runtime: dict[str, Any]) -> str:
        tool_started.set()
        release_tool.wait(timeout=2)
        return "late result"

    runner = LangGraphRunner(model, [_tool_definition("write")], executor)
    worker = threading.Thread(
        target=lambda: results.append(
            runner.run(
                "thread-cancel-tool",
                "start",
                runtime={"cancel_event": cancel_event},
                run_id="run-cancel-tool",
                emit=events.append,
            )
        )
    )
    worker.start()
    assert tool_started.wait(timeout=1)
    cancel_event.set()
    release_tool.set()
    worker.join(timeout=2)

    assert not worker.is_alive()
    assert results[0].status == "cancelled"
    assert not any(event["type"] == "tool_end" for event in events)
    snapshot = runner.graph.get_state(
        {"configurable": {"thread_id": "thread-cancel-tool"}}
    )
    assert "late result" not in str(snapshot.values.get("messages", []))


def test_approval_wait_time_is_not_included_in_tool_duration() -> None:
    tool_call = {
        "name": "write",
        "args": {},
        "id": "write-1",
        "type": "tool_call",
    }
    model = FakeGraphModel(
        responses=[
            AIMessage(content="", tool_calls=[tool_call]),
            AIMessage(content="done"),
        ]
    )
    events: list[dict[str, Any]] = []
    runner = LangGraphRunner(
        model,
        [_tool_definition("write")],
        lambda name, args: "written",
        requires_approval=lambda name, args: True,
    )
    paused = runner.run("thread-approval", "start", run_id="approval-1")
    assert paused.status == "waiting"
    time.sleep(0.12)
    completed = runner.resume(
        "thread-approval",
        {"kind": "approval", "action": "approve"},
        run_id="approval-1",
        emit=events.append,
    )
    assert completed.status == "complete"
    tool_end = next(event for event in events if event["type"] == "tool_end")
    assert tool_end["duration_ms"] < 100


def test_guarded_duplicate_does_not_request_approval_twice() -> None:
    calls = [
        {"name": "write", "args": {}, "id": "write-1", "type": "tool_call"},
        {"name": "write", "args": {}, "id": "write-2", "type": "tool_call"},
    ]
    model = FakeGraphModel(
        responses=[AIMessage(content="", tool_calls=calls), AIMessage(content="done")]
    )
    events: list[dict[str, Any]] = []
    executions: list[str] = []
    runner = LangGraphRunner(
        model,
        [_tool_definition("write")],
        lambda name, args: executions.append(name) or "written",
        requires_approval=lambda name, args: True,
    )
    paused = runner.run(
        "thread-duplicate", "start", run_id="duplicate-1", emit=events.append
    )
    assert paused.status == "waiting"
    completed = runner.resume(
        "thread-duplicate",
        {"kind": "approval", "action": "approve"},
        run_id="duplicate-1",
        emit=events.append,
    )
    assert completed.status == "complete"
    assert executions == ["write"]
    assert len([event for event in events if event["type"] == "interrupt"]) == 1


def test_runner_uses_thread_specific_runtime_binding() -> None:
    barrier = threading.Barrier(2)
    seen: list[tuple[str, str]] = []

    def executor(name: str, args: dict[str, Any], runtime: dict[str, Any]) -> str:
        barrier.wait(timeout=2)
        seen.append((runtime["thread_id"], runtime["run_id"]))
        return "ok"

    def make_runner_response(call_id: str) -> FakeGraphModel:
        return FakeGraphModel(
            responses=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "echo",
                            "args": {},
                            "id": call_id,
                            "type": "tool_call",
                        }
                    ],
                ),
                AIMessage(content="done"),
            ]
        )

    # One runner owns the registry; use a model that provides enough ordered responses.
    model = FakeGraphModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "echo", "args": {}, "id": "a", "type": "tool_call"}
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "echo", "args": {}, "id": "b", "type": "tool_call"}
                ],
            ),
            AIMessage(content="done-a"),
            AIMessage(content="done-b"),
        ]
    )
    runner = LangGraphRunner(model, [_tool_definition("echo")], executor)
    threads = [
        threading.Thread(
            target=runner.run,
            args=(thread_id, "start"),
            kwargs={"run_id": run_id},
        )
        for thread_id, run_id in (("thread-a", "run-a"), ("thread-b", "run-b"))
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=3)
    assert sorted(seen) == [("thread-a", "run-a"), ("thread-b", "run-b")]


def test_tool_loop_guard_snapshot_round_trip() -> None:
    guard = ToolLoopGuard()
    decision = guard.before_call("read", {"filePath": "/tmp/example"})
    guard.record_result(
        "read",
        {"filePath": "/tmp/example"},
        "content",
        decision["signature"],
        decision["kind"],
    )
    restored = ToolLoopGuard()
    restored.restore(guard.snapshot())
    assert restored.before_call("read", {"filePath": "/tmp/example"})[
        "action"
    ] == "reuse"


def test_tool_loop_guard_repeat_threshold_is_configurable(monkeypatch) -> None:
    def run_repeats():
        guard = ToolLoopGuard()
        decision = guard.before_call("read", {"filePath": "/tmp/example"})
        guard.record_result(
            "read",
            {"filePath": "/tmp/example"},
            "content",
            decision["signature"],
            decision["kind"],
        )
        return [
            guard.before_call("read", {"filePath": "/tmp/example"})["action"]
            for _ in range(7)
        ]

    monkeypatch.delenv("MAX_SAME_TOOL_REPEATS", raising=False)
    assert run_repeats() == ["reuse", "block", "block", "block", "block", "block", "block"]

    monkeypatch.setenv("MAX_SAME_TOOL_REPEATS", "8")
    assert run_repeats() == ["reuse"] * 6 + ["block"]


def test_sqlite_checkpoint_survives_runner_recreation(tmp_path) -> None:
    class RestartAwareModel(FakeGraphModel):
        def _stream(self, messages, stop=None, run_manager=None, **kwargs):
            if any(message.type == "tool" for message in messages):
                yield ChatGenerationChunk(message=AIMessageChunk(content="resumed"))
                return
            yield from super()._stream(messages, stop, run_manager, **kwargs)

    question = {
        "name": "question",
        "args": {
            "questions": [
                {
                    "header": "Choice",
                    "question": "Choose",
                    "options": [{"label": "A"}],
                }
            ]
        },
        "id": "question-restart",
        "type": "tool_call",
    }
    definition = [_tool_definition("question")]
    checkpoint_path = tmp_path / "checkpoints.sqlite3"
    saver = create_checkpoint_saver(checkpoint_path)
    first = LangGraphRunner(
        RestartAwareModel(responses=[AIMessage(content="", tool_calls=[question])]),
        definition,
        lambda *args: "",
        checkpointer=saver,
    )

    paused = first.run("restart-thread", "start", run_id="restart-run")
    assert paused.status == "waiting"

    second = LangGraphRunner(
        RestartAwareModel(responses=[AIMessage(content="", tool_calls=[question])]),
        definition,
        lambda *args: "",
        checkpointer=saver,
    )
    completed = second.resume(
        "restart-thread",
        {"kind": "question", "answers": [["A"]]},
        run_id="restart-run",
    )
    assert completed.status == "complete"
    assert completed.content == "resumed"
    second.delete_thread("restart-thread")


def test_sqlite_checkpoint_prefix_cleanup_preserves_other_tasks(tmp_path) -> None:
    """Removing one desktop task must not touch another task or CLI history."""
    checkpoint_path = tmp_path / "checkpoints.sqlite3"
    saver = create_checkpoint_saver(checkpoint_path)
    runner = LangGraphRunner(
        FakeGraphModel(
            responses=[
                AIMessage(content="first"),
                AIMessage(content="second"),
                AIMessage(content="other desktop task"),
                AIMessage(content="cli task"),
            ]
        ),
        [],
        lambda *args: "",
        checkpointer=saver,
    )

    task_id = "desktop-task-a"
    for thread_id in (
        f"{task_id}:101",
        f"{task_id}:202",
        "desktop-task-b:303",
        "cli:terminal-task",
    ):
        assert runner.run(thread_id, "start").status == "complete"

    removed = runner.delete_threads_with_prefix(f"{task_id}:")

    with saver.cursor(transaction=False) as cursor:
        checkpoint_threads = {
            row[0]
            for row in cursor.execute("SELECT DISTINCT thread_id FROM checkpoints")
        }
        write_threads = {
            row[0] for row in cursor.execute("SELECT DISTINCT thread_id FROM writes")
        }
    assert removed == 2
    assert checkpoint_threads == {"desktop-task-b:303", "cli:terminal-task"}
    assert write_threads == {"desktop-task-b:303", "cli:terminal-task"}


def test_sqlite_checkpoint_vacuum_reclaims_pages_after_task_cleanup(tmp_path) -> None:
    """Explicit task cleanup should return deleted SQLite pages to the filesystem."""
    checkpoint_path = tmp_path / "checkpoints.sqlite3"
    saver = create_checkpoint_saver(checkpoint_path)
    runner = LangGraphRunner(
        FakeGraphModel(responses=[AIMessage(content="x" * 512_000)]),
        [],
        lambda *args: "",
        checkpointer=saver,
    )

    assert runner.run("desktop-large-task:101", "start").status == "complete"
    with saver.cursor(transaction=False) as cursor:
        pages_before = cursor.execute("PRAGMA page_count").fetchone()[0]

    assert runner.delete_threads_with_prefix("desktop-large-task:") == 1
    with saver.cursor(transaction=False) as cursor:
        free_pages_before = cursor.execute("PRAGMA freelist_count").fetchone()[0]
    assert free_pages_before > 0

    assert runner.vacuum_checkpoint_store() is True
    with saver.cursor(transaction=False) as cursor:
        pages_after = cursor.execute("PRAGMA page_count").fetchone()[0]
        free_pages_after = cursor.execute("PRAGMA freelist_count").fetchone()[0]
    assert pages_after < pages_before
    assert free_pages_after == 0
