"""Regression tests for the shared LangGraph task runtime."""

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessageChunk, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGenerationChunk

from agent.core.langgraph_runner import LangGraphRunner


def tool_definition(name: str) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": f"Test {name}",
            "parameters": {"type": "object", "properties": {}},
        },
    }


class ScriptedModel(BaseChatModel):
    script: list[list[AIMessageChunk]]
    turn: int = 0
    seen_messages: list[list] = []

    @property
    def _llm_type(self) -> str:
        return "scripted-test-model"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, **kwargs):
        raise NotImplementedError

    def _stream(self, messages, **kwargs):
        self.seen_messages.append(list(messages))
        chunks = self.script[self.turn]
        self.turn += 1
        for chunk in chunks:
            yield ChatGenerationChunk(message=chunk)


def tool_chunk(name: str, arguments: str, call_id: str) -> AIMessageChunk:
    return AIMessageChunk(
        content="",
        tool_call_chunks=[
            {
                "name": name,
                "args": arguments,
                "id": call_id,
                "index": 0,
                "type": "tool_call_chunk",
            }
        ],
    )


def test_tool_result_remains_in_message_sequence():
    model = ScriptedModel(
        script=[
            [tool_chunk("read", '{"path":"demo.txt"}', "read-1")],
            [AIMessageChunk(content="已读取文件")],
        ]
    )
    runner = LangGraphRunner(
        model,
        [tool_definition("read")],
        lambda name, args, runtime: "file contents",
    )

    result = runner.run("task-1", "读取文件", run_id="run-1")
    snapshot = runner.graph.get_state({"configurable": {"thread_id": "task-1"}})

    assert result.status == "complete"
    assert result.content == "已读取文件"
    assert isinstance(snapshot.values["messages"][2], ToolMessage)
    assert snapshot.values["messages"][2].content == "file contents"


def test_mid_task_compression_replaces_context_and_continues() -> None:
    large_result = "large tool output " * 2000
    model = ScriptedModel(
        script=[
            [tool_chunk("read", '{"path":"large.txt"}', "read-large")],
            [AIMessageChunk(content="压缩后继续完成")],
        ],
        seen_messages=[],
    )
    events = []
    handler_calls = []

    def compression_handler(state, snapshot, progress):
        handler_calls.append((state["step_count"], snapshot["tokens_before"]))
        progress("summarizing", "正在生成摘要")
        return {
            "success": True,
            "status": "success",
            "message": "已压缩并继续",
            "tokens_before": snapshot["tokens_before"],
            "tokens_after": 40,
            "released_tokens": snapshot["tokens_before"] - 40,
            "step_count": 2,
            "replacement_messages": [
                HumanMessage(content="COMPACT SUMMARY: read large.txt completed")
            ],
            "system_prompt": "refreshed system prompt",
        }

    runner = LangGraphRunner(
        model,
        [tool_definition("read")],
        lambda *_args: large_result,
    )
    result = runner.run(
        "task-compact",
        "读取大文件后继续",
        run_id="run-compact",
        emit=events.append,
        runtime={
            "compression_check": lambda state: (
                {
                    "tokens_before": 5000,
                    "step_count": 2,
                    "threshold": 1000,
                }
                if state["step_count"] == 1
                else None
            ),
            "compression_handler": compression_handler,
        },
    )

    assert result.status == "complete"
    assert result.content == "压缩后继续完成"
    assert handler_calls == [(1, 5000)]
    event_types = [event["type"] for event in events]
    assert event_types.index("tool_end") < event_types.index("compression_start")
    assert event_types.index("compression_end") < event_types.index(
        "model_start", event_types.index("compression_end")
    )
    compression_end = next(
        event for event in events if event["type"] == "compression_end"
    )
    assert compression_end["task_continues"] is True
    second_input = model.seen_messages[1]
    assert second_input[0].content == "refreshed system prompt"
    assert "COMPACT SUMMARY" in str(second_input)
    assert large_result not in str(second_input)


def test_failed_mid_task_compression_keeps_context_and_does_not_retry_same_step() -> None:
    large_result = "large context"
    attempts = []
    model = ScriptedModel(
        script=[
            [tool_chunk("read", "{}", "read-failure")],
            [AIMessageChunk(content="仍然继续")],
        ],
        seen_messages=[],
    )
    runner = LangGraphRunner(
        model,
        [tool_definition("read")],
        lambda *_args: large_result,
    )

    result = runner.run(
        "task-compact-failure",
        "start",
        runtime={
            "compression_check": lambda state: (
                {
                    "tokens_before": 5000,
                    "step_count": 1,
                    "threshold": 1000,
                }
                if state["step_count"] == 1
                else None
            ),
            "compression_handler": lambda *_args: attempts.append("attempt")
            or {
                "success": False,
                "status": "error",
                "message": "summary service unavailable",
                "tokens_before": 5000,
                "tokens_after": 5000,
                "released_tokens": 0,
                "step_count": 1,
            },
        },
    )

    assert result.status == "complete"
    assert attempts == ["attempt"]
    assert large_result in str(model.seen_messages[1])


def test_compression_waits_for_every_tool_in_the_model_batch() -> None:
    model = ScriptedModel(
        script=[
            [
                AIMessageChunk(
                    content="",
                    tool_call_chunks=[
                        {
                            "name": "read",
                            "args": "{}",
                            "id": "read-batch",
                            "index": 0,
                            "type": "tool_call_chunk",
                        },
                        {
                            "name": "write",
                            "args": "{}",
                            "id": "write-batch",
                            "index": 1,
                            "type": "tool_call_chunk",
                        },
                    ],
                )
            ],
            [AIMessageChunk(content="batch complete")],
        ],
        seen_messages=[],
    )
    events = []
    executions = []
    runner = LangGraphRunner(
        model,
        [tool_definition("read"), tool_definition("write")],
        lambda name, *_args: executions.append(name) or f"{name} result",
    )

    result = runner.run(
        "task-batch-compact",
        "run both",
        emit=events.append,
        runtime={
            "compression_check": lambda state: (
                {
                    "tokens_before": 4000,
                    "step_count": 2,
                    "threshold": 1000,
                }
                if state["step_count"] == 1
                else None
            ),
            "compression_handler": lambda _state, snapshot, _progress: {
                "success": True,
                "status": "success",
                "message": "compacted batch",
                "tokens_before": snapshot["tokens_before"],
                "tokens_after": 20,
                "released_tokens": snapshot["tokens_before"] - 20,
                "step_count": 2,
                "replacement_messages": [HumanMessage(content="batch summary")],
            },
        },
    )

    assert result.status == "complete"
    assert executions == ["read", "write"]
    types = [event["type"] for event in events]
    second_tool_end = [
        index for index, event_type in enumerate(types) if event_type == "tool_end"
    ][1]
    assert second_tool_end < types.index("compression_start")


def test_compression_before_first_model_keeps_current_user_request() -> None:
    model = ScriptedModel(
        script=[[AIMessageChunk(content="new task completed")]],
        seen_messages=[],
    )
    runner = LangGraphRunner(model, [], lambda *_args: "")

    result = runner.run(
        "task-initial-compact",
        "CURRENT USER REQUEST",
        runtime={
            "compression_check": lambda state: (
                {
                    "tokens_before": 5000,
                    "step_count": 12,
                    "threshold": 1000,
                }
                if state["step_count"] == 0
                else None
            ),
            "compression_handler": lambda _state, snapshot, _progress: {
                "success": True,
                "status": "success",
                "message": "old memory compacted",
                "tokens_before": snapshot["tokens_before"],
                "tokens_after": 20,
                "released_tokens": snapshot["tokens_before"] - 20,
                "step_count": 12,
                "replacement_messages": [
                    HumanMessage(
                        content="CURRENT USER REQUEST\n\nOLD MEMORY SUMMARY"
                    )
                ],
            },
        },
    )

    assert result.status == "complete"
    assert "CURRENT USER REQUEST" in str(model.seen_messages[0])


def test_question_interrupt_resumes_without_restarting_task():
    model = ScriptedModel(
        script=[
            [
                tool_chunk(
                    "question",
                    '{"questions":[{"header":"模式","question":"选择？",'
                    '"options":[{"label":"A"}]}]}',
                    "question-1",
                )
            ],
            [AIMessageChunk(content="收到选择")],
        ]
    )
    runner = LangGraphRunner(
        model,
        [tool_definition("question")],
        lambda *args: "question must not execute as a normal tool",
    )

    waiting = runner.run("task-q", "开始", run_id="run-q")
    completed = runner.resume(
        "task-q",
        {"answers": [["A"]], "content": "用户选择 A"},
        run_id="run-q",
    )

    assert waiting.status == "waiting"
    assert waiting.pending and waiting.pending.kind == "question"
    assert completed.status == "complete"
    assert completed.content == "收到选择"
    assert model.turn == 2


def test_denied_approval_does_not_execute_tool():
    model = ScriptedModel(
        script=[
            [tool_chunk("write", '{"path":"demo.txt"}', "write-1")],
            [AIMessageChunk(content="已取消写入")],
        ]
    )
    calls = []
    runner = LangGraphRunner(
        model,
        [tool_definition("write")],
        lambda name, args, runtime: calls.append((name, args)) or "written",
        requires_approval=lambda name, args: True,
    )

    waiting = runner.run("task-a", "写文件", run_id="run-a")
    completed = runner.resume(
        "task-a", {"action": "deny"}, run_id="run-a"
    )

    assert waiting.status == "waiting"
    assert waiting.pending and waiting.pending.kind == "approval"
    assert completed.status == "complete"
    assert calls == []


def test_reasoning_is_emitted_but_not_checkpointed():
    model = ScriptedModel(
        script=[
            [
                AIMessageChunk(
                    content="",
                    additional_kwargs={"reasoning_content": "hidden plan"},
                ),
                AIMessageChunk(content="visible answer"),
            ]
        ]
    )
    events = []
    runner = LangGraphRunner(model, [], lambda *args: "")

    runner.run("task-r", "回答", emit=events.append, run_id="run-r")
    snapshot = runner.graph.get_state({"configurable": {"thread_id": "task-r"}})
    assistant = snapshot.values["messages"][-1]

    assert any(event["type"] == "reasoning_delta" for event in events)
    assert assistant.content == "visible answer"
    assert "reasoning_content" not in assistant.additional_kwargs
