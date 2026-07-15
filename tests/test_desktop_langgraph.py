"""Desktop protocol regressions for the shared LangGraph runner."""

from __future__ import annotations

import json
import time

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessageChunk
from langchain_core.outputs import ChatGenerationChunk

from agent.core.langgraph_runner import LangGraphRunner
from agent.core.memory_manager import MemoryManager
from agent.core.conversation_store import ConversationStore
from agent.ui.desktop import main as desktop


class _DataIntegrator:
    def __init__(self) -> None:
        self.statuses = []

    def end_task(self, status: str) -> None:
        self.statuses.append(status)

    def start_task(self, _request: str) -> str:
        return "test-task"


class _CheckpointCleanupRunner:
    """Record desktop lifecycle calls without needing a real model run."""

    def __init__(self, removed_threads: int = 2) -> None:
        self.prefixes: list[str] = []
        self.vacuum_calls = 0
        self.removed_threads = removed_threads

    def delete_threads_with_prefix(self, prefix: str) -> int:
        self.prefixes.append(prefix)
        return self.removed_threads

    def vacuum_checkpoint_store(self) -> bool:
        self.vacuum_calls += 1
        return True


class _FinalModel(BaseChatModel):
    @property
    def _llm_type(self) -> str:
        return "desktop-final-test"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, **kwargs):
        raise NotImplementedError

    def _stream(self, messages, **kwargs):
        yield ChatGenerationChunk(
            message=AIMessageChunk(
                content="",
                additional_kwargs={"reasoning_content": "private plan"},
            )
        )
        yield ChatGenerationChunk(message=AIMessageChunk(content="visible answer"))


class _QuestionModel(BaseChatModel):
    turn: int = 0

    @property
    def _llm_type(self) -> str:
        return "desktop-question-test"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, **kwargs):
        raise NotImplementedError

    def _stream(self, messages, **kwargs):
        if self.turn == 0:
            self.turn += 1
            yield ChatGenerationChunk(
                message=AIMessageChunk(
                    content="请选择",
                    tool_call_chunks=[
                        {
                            "name": "question",
                            "args": (
                                '{"questions":[{"header":"模式",'
                                '"question":"请选择模式",'
                                '"options":[{"label":"A",'
                                '"description":"方案 A"}]}]}'
                            ),
                            "id": "question-1",
                            "index": 0,
                            "type": "tool_call_chunk",
                        }
                    ],
                )
            )
            return
        self.turn += 1
        yield ChatGenerationChunk(message=AIMessageChunk(content="已收到 A"))


class _MultiRoundToolModel(BaseChatModel):
    turn: int = 0

    @property
    def _llm_type(self) -> str:
        return "desktop-multi-round-test"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, **kwargs):
        raise NotImplementedError

    def _stream(self, messages, **kwargs):
        scripts = [
            ("plan one", "先读取文件", "read", "read-1"),
            ("plan two", "再修改文件", "write", "write-1"),
            ("plan three", "任务完成", "", ""),
        ]
        reasoning, content, tool_name, tool_id = scripts[self.turn]
        self.turn += 1
        yield ChatGenerationChunk(
            message=AIMessageChunk(
                content="",
                additional_kwargs={"reasoning_content": reasoning},
            )
        )
        yield ChatGenerationChunk(message=AIMessageChunk(content=content))
        if tool_name:
            yield ChatGenerationChunk(
                message=AIMessageChunk(
                    content="",
                    tool_call_chunks=[
                        {
                            "name": tool_name,
                            "args": "{}",
                            "id": tool_id,
                            "index": 0,
                            "type": "tool_call_chunk",
                        }
                    ],
                )
            )


def _question_tool() -> dict:
    return {
        "type": "function",
        "function": {
            "name": "question",
            "description": "Ask one selectable question",
            "parameters": {
                "type": "object",
                "properties": {"questions": {"type": "array"}},
            },
        },
    }


def _simple_tool(name: str) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": name,
            "parameters": {"type": "object", "properties": {}},
        },
    }


class _PlanModel(BaseChatModel):
    turn: int = 0

    @property
    def _llm_type(self) -> str:
        return "desktop-plan-test"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, **kwargs):
        raise NotImplementedError

    def _stream(self, messages, **kwargs):
        if self.turn == 0:
            self.turn += 1
            yield ChatGenerationChunk(
                message=AIMessageChunk(
                    content="",
                    tool_call_chunks=[
                        {
                            "name": "update_plan",
                            "args": (
                                '{"explanation":"先实现，再验证。","plan":['
                                '{"step":"实现功能","status":"in_progress"},'
                                '{"step":"运行验证","status":"pending"}]}'
                            ),
                            "id": "plan-1",
                            "index": 0,
                            "type": "tool_call_chunk",
                        }
                    ],
                )
            )
            return
        self.turn += 1
        yield ChatGenerationChunk(message=AIMessageChunk(content="完成"))


def _plan_tool() -> dict:
    return {
        "type": "function",
        "function": {
            "name": "update_plan",
            "description": "Replace the task plan",
            "parameters": {
                "type": "object",
                "properties": {
                    "explanation": {"type": "string"},
                    "plan": {"type": "array"},
                },
                "required": ["plan"],
            },
        },
    }


def _prepare_desktop(
    monkeypatch,
    tmp_path,
    runner: LangGraphRunner,
    *,
    persist_steps: bool = False,
    reset_state: bool = True,
) -> desktop.DesktopTaskExecutor:
    if not persist_steps:
        monkeypatch.setattr(desktop, "_persist_step", lambda *args: None)
    if reset_state:
        desktop.conversation_runs.clear()
        desktop.conversation_executors.clear()
        desktop.conversation_generations.clear()
    executor = desktop.DesktopTaskExecutor()
    executor.memory_manager = MemoryManager(str(tmp_path / "memory"))
    executor.data_integrator = _DataIntegrator()
    executor.langgraph_runner = runner
    executor._langgraph_max_steps = executor.max_steps
    executor.show_knowledge_appendix = False
    executor.compress_at = 999999
    executor.pending_question = None
    executor.pending_approval = None
    return executor


def _register_executor(
    conversation_id: str, executor: desktop.DesktopTaskExecutor
) -> None:
    executor.conversation_id = conversation_id
    desktop.conversation_executors[conversation_id] = executor


def test_desktop_startup_does_not_import_terminal_memory(
    monkeypatch, tmp_path
) -> None:
    terminal_memory = tmp_path / "Memory"
    terminal_memory.mkdir()
    terminal_history = terminal_memory / "execution_history.md"
    terminal_history.write_text("terminal-only history\n", encoding="utf-8")

    store = ConversationStore(tmp_path / "workspace" / "conversations")
    original_id = store.active_id()
    assert original_id
    replacement_id = store.delete(original_id)["active_id"]

    class _AIEngine:
        def clear_history(self) -> None:
            pass

    class _SkillsLoader:
        def __init__(self, _workspace_path) -> None:
            pass

    class _PreviewManager:
        def __init__(self, **_kwargs) -> None:
            pass

    class _ToolExecutor:
        def __init__(self, **_kwargs) -> None:
            pass

    monkeypatch.setattr(desktop, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(desktop, "conversation_store", store)
    monkeypatch.setattr(desktop, "AIEngine", _AIEngine)
    monkeypatch.setattr(desktop, "SkillsLoader", _SkillsLoader)
    monkeypatch.setattr(desktop, "PreviewManager", _PreviewManager)
    monkeypatch.setattr(desktop, "ExtendedToolExecutor", _ToolExecutor)
    monkeypatch.setattr(desktop, "create_checkpoint_saver", lambda _path: object())
    monkeypatch.setattr(
        desktop.DesktopTaskExecutor, "rebuild_langgraph_runner", lambda _self: None
    )
    monkeypatch.setattr(
        desktop.DesktopTaskExecutor,
        "cleanup_orphaned_desktop_checkpoints",
        lambda _self: {"removed_threads": 0, "compacted": False, "error": ""},
    )

    executor = desktop.DesktopTaskExecutor()
    success, _message = executor.initialize()

    assert success is True
    assert executor.conversation_id == replacement_id
    assert executor.memory_manager.load_execution_history() == []
    assert not (store.memory_dir(replacement_id) / "execution_history.md").exists()
    assert terminal_history.read_text(encoding="utf-8") == "terminal-only history\n"


def _prepare_checkpoint_cleanup_desktop(monkeypatch, tmp_path):
    store = ConversationStore(tmp_path / "conversations")
    conversation = store.create("checkpoint cleanup")
    runner = _CheckpointCleanupRunner()
    monkeypatch.setattr(desktop, "conversation_store", store)
    desktop.conversation_runs.clear()
    desktop.conversation_executors.clear()
    desktop.conversation_generations.clear()
    monkeypatch.setattr(desktop.os_agent, "preview_manager", None)
    monkeypatch.setattr(desktop.os_agent, "langgraph_runner", runner)
    executor = desktop.DesktopTaskExecutor()
    executor.preview_manager = None
    executor.langgraph_runner = runner
    executor.conversation_id = conversation["id"]
    executor.memory_manager = MemoryManager(
        str(store.memory_dir(conversation["id"]))
    )
    desktop.conversation_executors[conversation["id"]] = executor
    monkeypatch.setattr(
        desktop,
        "_executor_for_conversation",
        lambda conversation_id: desktop.conversation_executors.setdefault(
            conversation_id, executor
        ),
    )
    return conversation, runner


def test_desktop_streams_reasoning_but_keeps_it_out_of_memory(
    monkeypatch, tmp_path
) -> None:
    runner = LangGraphRunner(_FinalModel(), [], lambda *args: "")
    executor = _prepare_desktop(monkeypatch, tmp_path, runner)
    _register_executor("conversation", executor)
    run = desktop._begin_execution(101, "conversation")
    assert run is not None

    outcome = desktop._run_graph_task("hello", "system", run)
    events = desktop.get_next_results("conversation", 101, 64)

    assert outcome == "complete"
    assert [event["type"] for event in events] == [
        "stream",
        "stream",
        "stream",
        "stream",
        "stream_end",
    ]
    assert events[-1]["content"] == "<think>private plan</think>\nvisible answer"
    assert events[-1]["thinking_duration_ms"] >= 0
    assert executor.memory_manager.load_execution_history() == [
        "最终回应: visible answer"
    ]
    desktop._finish_execution(run, outcome)


def test_desktop_persists_thinking_duration_for_history_reload(
    monkeypatch, tmp_path
) -> None:
    store = ConversationStore(tmp_path / "conversations")
    conversation = store.create("duration")
    monkeypatch.setattr(desktop, "conversation_store", store)

    desktop._persist_step(
        {
            "type": "stream_end",
            "target": "final",
            "content": "<think>plan</think>\nanswer",
            "thinking_duration_ms": 2345,
        },
        303,
        conversation["id"],
    )

    saved = store.load(conversation["id"])["messages"][-1]
    assert saved["type"] == "assistant"
    assert saved["thinking_duration_ms"] == 2345


def test_desktop_history_keeps_plan_snapshots_for_latest_only_restore(
    monkeypatch, tmp_path
) -> None:
    store = ConversationStore(tmp_path / "conversations")
    conversation = store.create("history plans")
    monkeypatch.setattr(desktop, "conversation_store", store)

    desktop._persist_step(
        {
            "type": "plan_update",
            "version": 1,
            "plan": [{"step": "旧步骤", "status": "in_progress"}],
        },
        304,
        conversation["id"],
    )
    desktop._persist_step(
        {
            "type": "plan_update",
            "version": 2,
            "plan": [
                {"step": "旧步骤", "status": "completed"},
                {"step": "最新步骤", "status": "in_progress"},
            ],
        },
        304,
        conversation["id"],
    )

    saved = store.load(conversation["id"])["messages"]
    assert [event["version"] for event in saved] == [2]
    assert saved[0]["plan"][-1]["step"] == "最新步骤"


def test_desktop_emits_and_persists_plan_as_dedicated_snapshot(
    monkeypatch, tmp_path
) -> None:
    store = ConversationStore(tmp_path / "conversations")
    conversation = store.create("plan")
    snapshot = {
        "success": True,
        "version": 1,
        "completed": 0,
        "total": 2,
        "current_step": "实现功能",
        "explanation": "先实现，再验证。",
        "plan": [
            {"step": "实现功能", "status": "in_progress"},
            {"step": "运行验证", "status": "pending"},
        ],
    }
    runner = LangGraphRunner(
        _PlanModel(),
        [_plan_tool()],
        lambda *_args: json.dumps(snapshot, ensure_ascii=False),
    )
    monkeypatch.setattr(desktop, "conversation_store", store)
    executor = _prepare_desktop(monkeypatch, tmp_path, runner, persist_steps=True)
    executor.memory_manager = MemoryManager(str(store.memory_dir(conversation["id"])))
    _register_executor(conversation["id"], executor)
    run = desktop._begin_execution(306, conversation["id"])
    assert run is not None

    outcome = desktop._run_graph_task("implement", "system", run)
    events = desktop.get_next_results(conversation["id"], 306, 64)
    saved = store.load(conversation["id"])["messages"]

    assert outcome == "complete"
    plan_events = [event for event in events if event["type"] == "plan_update"]
    assert len(plan_events) == 1
    assert plan_events[0]["current_step"] == "实现功能"
    assert not any(
        event.get("type") in {"tool", "tool_start", "tool_preparing"}
        and event.get("tool") == "update_plan"
        for event in events
    )
    persisted = [event for event in saved if event["type"] == "plan_update"]
    assert len(persisted) == 1
    assert persisted[0]["plan"] == snapshot["plan"]


def test_desktop_plan_error_is_live_only_and_not_persisted(
    monkeypatch, tmp_path
) -> None:
    store = ConversationStore(tmp_path / "conversations")
    conversation = store.create("invalid plan")
    runner = LangGraphRunner(
        _PlanModel(),
        [_plan_tool()],
        lambda *_args: "Error: only one plan step may be in_progress",
    )
    monkeypatch.setattr(desktop, "conversation_store", store)
    executor = _prepare_desktop(monkeypatch, tmp_path, runner, persist_steps=True)
    executor.memory_manager = MemoryManager(str(store.memory_dir(conversation["id"])))
    _register_executor(conversation["id"], executor)
    run = desktop._begin_execution(307, conversation["id"])
    assert run is not None

    assert desktop._run_graph_task("implement", "system", run) == "complete"
    events = desktop.get_next_results(conversation["id"], 307, 64)
    errors = [event for event in events if event["type"] == "plan_update"]

    assert len(errors) == 1
    assert errors[0]["error"].startswith("Error:")
    assert not any(
        event["type"] == "plan_update"
        for event in store.load(conversation["id"])["messages"]
    )


def test_desktop_persists_intermediate_reasoning_before_commentary(
    monkeypatch, tmp_path
) -> None:
    store = ConversationStore(tmp_path / "conversations")
    conversation = store.create("multi-round")
    monkeypatch.setattr(desktop, "conversation_store", store)

    desktop._persist_step(
        {
            "type": "stream_end",
            "target": "commentary",
            "content": "<think>first private plan</think>\n正在读取项目文件",
            "thinking_duration_ms": 1234,
        },
        404,
        conversation["id"],
    )
    desktop._persist_step(
        {
            "type": "stream_end",
            "target": "commentary",
            "content": "<think>second private plan</think>\n正在修改代码",
            "thinking_duration_ms": 2345,
        },
        404,
        conversation["id"],
    )

    saved = store.load(conversation["id"])["messages"]
    assert [event["type"] for event in saved] == [
        "thinking",
        "commentary",
        "thinking",
        "commentary",
    ]
    assert [event["content"] for event in saved] == [
        "first private plan",
        "正在读取项目文件",
        "second private plan",
        "正在修改代码",
    ]
    assert saved[0]["thinking_duration_ms"] == 1234
    assert saved[2]["thinking_duration_ms"] == 2345


def test_desktop_reload_keeps_every_tool_round_reasoning(
    monkeypatch, tmp_path
) -> None:
    root = tmp_path / "conversations"
    store = ConversationStore(root)
    conversation = store.create("full-chain")
    runner = LangGraphRunner(
        _MultiRoundToolModel(),
        [_simple_tool("read"), _simple_tool("write")],
        lambda name, _args, _runtime: f"{name} complete",
    )
    monkeypatch.setattr(desktop, "conversation_store", store)
    executor = _prepare_desktop(
        monkeypatch, tmp_path, runner, persist_steps=True
    )
    executor.memory_manager = MemoryManager(str(store.memory_dir(conversation["id"])))
    _register_executor(conversation["id"], executor)
    run = desktop._begin_execution(505, conversation["id"])
    assert run is not None

    outcome = desktop._run_graph_task("run all steps", "system", run)
    reloaded = ConversationStore(root).load(conversation["id"])["messages"]

    assert outcome == "complete"
    assert [event["type"] for event in reloaded] == [
        "thinking",
        "commentary",
        "tool",
        "thinking",
        "commentary",
        "tool",
        "assistant",
    ]
    assert [reloaded[index]["content"] for index in (0, 3)] == [
        "plan one",
        "plan two",
    ]
    final_thoughts, final_answer = desktop.MemoryManager.strip_reasoning(
        reloaded[-1]["content"]
    ), reloaded[-1]["content"]
    assert "plan three" in final_answer
    assert final_thoughts == "任务完成"
    assert [reloaded[index]["content"] for index in (1, 4)] == [
        "先读取文件",
        "再修改文件",
    ]
    assert all(event["message_id"] == 505 for event in reloaded)
    assert all(
        reloaded[index]["thinking_duration_ms"] >= 0 for index in (0, 3, 6)
    )
    memory = "\n".join(executor.memory_manager.load_execution_history())
    assert all(plan not in memory for plan in ("plan one", "plan two", "plan three"))
    desktop._finish_execution(run, outcome)


def test_desktop_question_resumes_same_graph_and_retains_invalid_prompt(
    monkeypatch, tmp_path
) -> None:
    runner = LangGraphRunner(
        _QuestionModel(), [_question_tool()], lambda *args: ""
    )
    executor = _prepare_desktop(monkeypatch, tmp_path, runner)
    _register_executor("conversation", executor)
    run = desktop._begin_execution(202, "conversation")
    assert run is not None

    assert desktop._run_graph_task("start", "system", run) == "waiting"
    assert desktop.get_execution_status("conversation", 202)["awaiting_question"] is True
    assert desktop.answer_question([[]], None, "conversation", 202)["success"] is False
    assert desktop.get_execution_status("conversation", 202)["awaiting_question"] is True

    assert desktop.answer_question([["A"]], None, "conversation", 202)["success"] is True
    for _ in range(100):
        if not desktop.get_execution_status("conversation", 202)["running"]:
            break
        time.sleep(0.01)

    events = desktop.get_next_results("conversation", 202, 64)
    assert desktop.get_execution_status("conversation", 202)["running"] is False
    assert any(event["type"] == "pending_question" for event in events)
    answered = next(
        event for event in events if event["type"] == "question_answered"
    )
    assert answered["answers"] == [["A"]]
    assert events[-1]["type"] == "stream_end"
    assert events[-1]["target"] == "final"


def test_desktop_question_accepts_text_supplement_and_persists_it(
    monkeypatch, tmp_path
) -> None:
    runner = LangGraphRunner(
        _QuestionModel(), [_question_tool()], lambda *args: ""
    )
    executor = _prepare_desktop(monkeypatch, tmp_path, runner)
    _register_executor("conversation", executor)
    run = desktop._begin_execution(203, "conversation")
    assert run is not None

    assert desktop._run_graph_task("start", "system", run) == "waiting"
    pending = executor.pending_question
    assert pending is not None
    pending["questions"] = [
        {
            "header": "项目名称",
            "question": "填写项目名称",
            "multiple": False,
            "selection_required": False,
            "allow_free_text": True,
            "free_text_label": "名称",
            "free_text_placeholder": "输入名称",
            "free_text_required": True,
            "options": [],
        }
    ]

    assert desktop.answer_question([[]], [""], "conversation", 203)["success"] is False
    assert desktop.answer_question([[]], ["星图"], "conversation", 203)["success"] is True
    for _ in range(100):
        if not desktop.get_execution_status("conversation", 203)["running"]:
            break
        time.sleep(0.01)

    events = desktop.get_next_results("conversation", 203, 64)
    answered = next(
        event for event in events if event["type"] == "question_answered"
    )
    assert answered["answers"] == [[]]
    assert answered["supplements"] == ["星图"]
    assert "补充：星图" in answered["content"]


def test_desktop_runs_different_conversations_concurrently(
    monkeypatch, tmp_path
) -> None:
    first_executor = _prepare_desktop(
        monkeypatch,
        tmp_path / "first",
        LangGraphRunner(_FinalModel(), [], lambda *args: ""),
    )
    second_executor = _prepare_desktop(
        monkeypatch,
        tmp_path / "second",
        LangGraphRunner(_FinalModel(), [], lambda *args: ""),
        reset_state=False,
    )
    _register_executor("first-conversation", first_executor)
    _register_executor("second-conversation", second_executor)

    first_run = desktop._begin_execution(601, "first-conversation")
    second_run = desktop._begin_execution(602, "second-conversation")

    assert first_run is not None
    assert second_run is not None
    assert first_run is not second_run
    assert first_run.executor is first_executor
    assert second_run.executor is second_executor
    assert desktop.get_execution_status("first-conversation", 601)["running"]
    assert desktop.get_execution_status("second-conversation", 602)["running"]


def test_desktop_event_queues_are_isolated_per_conversation(
    monkeypatch, tmp_path
) -> None:
    first_executor = _prepare_desktop(
        monkeypatch,
        tmp_path / "first",
        LangGraphRunner(_FinalModel(), [], lambda *args: ""),
    )
    second_executor = _prepare_desktop(
        monkeypatch,
        tmp_path / "second",
        LangGraphRunner(_FinalModel(), [], lambda *args: ""),
        reset_state=False,
    )
    _register_executor("first-conversation", first_executor)
    _register_executor("second-conversation", second_executor)
    first_run = desktop._begin_execution(611, "first-conversation")
    second_run = desktop._begin_execution(612, "second-conversation")
    assert first_run is not None
    assert second_run is not None

    desktop.push_step(
        {"type": "stream", "content": "first only"},
        first_run.message_id,
        first_run.conversation_id,
        first_run.generation,
    )
    desktop.push_step(
        {"type": "stream", "content": "second only"},
        second_run.message_id,
        second_run.conversation_id,
        second_run.generation,
    )

    first_events = desktop.get_next_results("first-conversation", 611, 64)
    second_events = desktop.get_next_results("second-conversation", 612, 64)
    assert [event["content"] for event in first_events] == ["first only"]
    assert [event["content"] for event in second_events] == ["second only"]
    assert all(
        event["conversation_id"] == "first-conversation"
        for event in first_events
    )
    assert all(
        event["conversation_id"] == "second-conversation"
        for event in second_events
    )


def test_desktop_plan_registry_is_cleared_on_activation_and_finish(
    monkeypatch, tmp_path
) -> None:
    store = ConversationStore(tmp_path / "conversations")
    conversation = store.create("plan lifecycle")
    monkeypatch.setattr(desktop, "conversation_store", store)
    executor = _prepare_desktop(
        monkeypatch,
        tmp_path,
        LangGraphRunner(_FinalModel(), [], lambda *args: ""),
    )

    class _PlanRegistry:
        def __init__(self) -> None:
            self.cleared = []
            self.discarded = []

        def clear_plan_snapshots(self, conversation_id) -> None:
            self.cleared.append(conversation_id)

        def discard_plan_snapshot(self, conversation_id, message_id) -> None:
            self.discarded.append((conversation_id, message_id))

    registry = _PlanRegistry()
    executor.tool_executor = registry
    executor.activate_conversation(conversation["id"])
    _register_executor(conversation["id"], executor)
    run = desktop._begin_execution(613, conversation["id"])
    assert run is not None

    desktop._finish_execution(run, "complete")

    assert registry.cleared == [conversation["id"]]
    assert registry.discarded == [(conversation["id"], 613)]


def test_desktop_stop_allows_immediate_new_run_while_old_worker_unwinds(
    monkeypatch, tmp_path
) -> None:
    executor = _prepare_desktop(
        monkeypatch,
        tmp_path / "old",
        LangGraphRunner(_FinalModel(), [], lambda *args: ""),
    )
    _register_executor("conversation", executor)
    old_run = desktop._begin_execution(621, "conversation")
    assert old_run is not None

    class _UnwindingWorker:
        @staticmethod
        def is_alive() -> bool:
            return True

    old_run.worker = _UnwindingWorker()
    fresh_executor = _prepare_desktop(
        monkeypatch,
        tmp_path / "fresh",
        LangGraphRunner(_FinalModel(), [], lambda *args: ""),
        reset_state=False,
    )
    monkeypatch.setattr(
        fresh_executor,
        "initialize_conversation_runtime",
        lambda conversation_id, shared_from: None,
    )
    monkeypatch.setattr(
        desktop,
        "DesktopTaskExecutor",
        lambda shared_from=None: fresh_executor,
    )

    stopped = desktop.stop_execution("conversation", 621)
    new_run = desktop._begin_execution(622, "conversation")

    assert stopped["success"] is True
    assert stopped["running"] is False
    assert old_run.cancel_event.is_set()
    assert old_run.status == "cancelled"
    assert new_run is not None
    assert new_run.message_id == 622
    assert new_run.generation == old_run.generation + 1
    assert new_run.executor is fresh_executor
    assert desktop.get_execution_status("conversation", 622)["running"] is True


def test_desktop_suppresses_late_events_from_an_old_generation(
    monkeypatch, tmp_path
) -> None:
    store = ConversationStore(tmp_path / "conversations")
    conversation = store.create("generation isolation")
    monkeypatch.setattr(desktop, "conversation_store", store)
    executor = _prepare_desktop(
        monkeypatch,
        tmp_path,
        LangGraphRunner(_FinalModel(), [], lambda *args: ""),
        persist_steps=True,
    )
    _register_executor(conversation["id"], executor)
    old_run = desktop._begin_execution(631, conversation["id"])
    assert old_run is not None

    assert desktop.stop_execution(conversation["id"], 631)["success"] is True
    new_run = desktop._begin_execution(632, conversation["id"])
    assert new_run is not None

    desktop.push_step(
        {"type": "final", "content": "stale result"},
        old_run.message_id,
        old_run.conversation_id,
        old_run.generation,
    )

    assert store.load(conversation["id"])["messages"] == []
    assert desktop.get_next_results(conversation["id"], 632, 64) == []


def test_clearing_a_desktop_task_cleans_its_graph_checkpoints(
    monkeypatch, tmp_path
) -> None:
    conversation, runner = _prepare_checkpoint_cleanup_desktop(monkeypatch, tmp_path)

    class _PreviewManager:
        def __init__(self) -> None:
            self.cleared = []

        def clear_conversation(self, conversation_id: str) -> None:
            self.cleared.append(conversation_id)

    preview_manager = _PreviewManager()
    monkeypatch.setattr(desktop.os_agent, "preview_manager", preview_manager)

    result = desktop.clear_conversation(conversation["id"])

    assert result["success"] is True
    assert preview_manager.cleared == [conversation["id"]]
    assert runner.prefixes == [f"{conversation['id']}:"]
    assert runner.vacuum_calls == 1


def test_deleting_a_desktop_task_cleans_its_graph_checkpoints(
    monkeypatch, tmp_path
) -> None:
    conversation, runner = _prepare_checkpoint_cleanup_desktop(monkeypatch, tmp_path)

    result = desktop.delete_conversation(conversation["id"])

    assert result["success"] is True
    assert runner.prefixes == [f"{conversation['id']}:"]
    assert runner.vacuum_calls == 1


def test_deleting_a_completed_desktop_task_reclaims_existing_free_pages(
    monkeypatch, tmp_path
) -> None:
    conversation, runner = _prepare_checkpoint_cleanup_desktop(monkeypatch, tmp_path)
    runner.removed_threads = 0

    result = desktop.delete_conversation(conversation["id"])

    assert result["success"] is True
    assert runner.prefixes == [f"{conversation['id']}:"]
    assert runner.vacuum_calls == 1


def test_clear_command_cleans_the_active_task_graph_checkpoints(
    monkeypatch, tmp_path
) -> None:
    conversation, runner = _prepare_checkpoint_cleanup_desktop(monkeypatch, tmp_path)

    result = desktop.send_message(
        "/clear", message_id=999, conversation_id=conversation["id"]
    )

    assert result == {"status": "done", "command": "clear"}
    assert runner.prefixes == [f"{conversation['id']}:"]
    assert runner.vacuum_calls == 1
