"""Desktop protocol regressions for the shared LangGraph runner."""

from __future__ import annotations

import json
import time
from types import SimpleNamespace

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessageChunk, HumanMessage
from langchain_core.outputs import ChatGenerationChunk

from agent.core.langgraph_runner import LangGraphRunner
from agent.core.memory_manager import MemoryManager
from agent.core.conversation_store import ConversationStore
from agent.core.memory_store import MemoryStore
from agent.core.project_store import ProjectStore
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


class _TargetToolModel(BaseChatModel):
    @property
    def _llm_type(self) -> str:
        return "desktop-tool-target-test"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, **kwargs):
        raise NotImplementedError

    def _stream(self, messages, **kwargs):
        yield ChatGenerationChunk(
            message=AIMessageChunk(
                content="",
                tool_call_chunks=[
                    {
                        "name": "write",
                        "args": '{"path":"/project/src/app.py","content":"secret"}',
                        "id": "write-target-1",
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
                            "name": "todo_write",
                            "args": (
                                '{"merge":false,"todos":['
                                '{"id":"implement","content":"实现功能",'
                                '"status":"in_progress"},'
                                '{"id":"verify","content":"运行验证",'
                                '"status":"pending"}]}'
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
            "name": "todo_write",
            "description": "Update the task todo plan",
            "parameters": {
                "type": "object",
                "properties": {
                    "merge": {"type": "boolean"},
                    "todos": {"type": "array"},
                },
                "required": ["todos"],
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


def test_desktop_conversation_memory_store_is_task_scoped(monkeypatch, tmp_path) -> None:
    store = ConversationStore(tmp_path / "conversations")
    first = store.active_id()
    second = store.create("second")["id"]
    monkeypatch.setattr(desktop, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(desktop, "conversation_store", store)

    executor = desktop.DesktopTaskExecutor()
    executor.conversation_id = first
    first_memory = executor._create_conversation_memory_store()
    executor.conversation_id = second
    second_memory = executor._create_conversation_memory_store()

    assert first_memory.workspace_dir != second_memory.workspace_dir
    assert first_memory.include_global is False
    assert second_memory.include_global is False


def test_desktop_memory_cleanup_preserves_tasks_projects_and_cli_scope(
    monkeypatch, tmp_path
) -> None:
    conversation_store = ConversationStore(tmp_path / "workspace" / "conversations")
    project_store = ProjectStore(tmp_path / "workspace" / "projects")
    project_root = tmp_path / "bound-project"
    project_root.mkdir()
    project_store.create("Bound", str(project_root))
    conversation_id = conversation_store.active_id()
    conversation_scope = conversation_store.memory_dir(conversation_id)
    memory_root = tmp_path / "workspace" / "memory"
    task_memory = MemoryStore(memory_root, conversation_scope)
    project_memory = MemoryStore(memory_root, project_root)
    cli_memory = MemoryStore(memory_root, tmp_path)
    orphan_memory = MemoryStore(memory_root, tmp_path / "deleted-task" / "memory")
    for index, memory in enumerate(
        (task_memory, project_memory, cli_memory, orphan_memory), 1
    ):
        memory.upsert_conversation_record(
            session_id=f"scope-{index}",
            title=f"Scope {index}",
            user_requests=[f"memory {index}"],
        )
    monkeypatch.setattr(desktop, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(desktop, "conversation_store", conversation_store)
    monkeypatch.setattr(desktop, "project_store", project_store)

    result = desktop._cleanup_orphaned_long_term_memory()

    assert task_memory.workspace_dir.is_dir()
    assert project_memory.workspace_dir.is_dir()
    assert cli_memory.workspace_dir.is_dir()
    assert not orphan_memory.workspace_dir.exists()
    assert result["removed_scopes"] == [orphan_memory.workspace_dir.name]


def test_desktop_project_memory_store_is_shared_between_project_tasks(
    monkeypatch, tmp_path
) -> None:
    store = ConversationStore(tmp_path / "conversations")
    first = store.active_id()
    second = store.create("second")["id"]
    project_root = tmp_path / "project"
    project_root.mkdir()
    monkeypatch.setattr(desktop, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(desktop, "conversation_store", store)

    executor = desktop.DesktopTaskExecutor()
    executor.project = {"id": "project", "available": True}
    executor.project_root = project_root
    executor.conversation_id = first
    first_memory = executor._create_conversation_memory_store()
    executor.conversation_id = second
    second_memory = executor._create_conversation_memory_store()

    assert first_memory.workspace_dir == second_memory.workspace_dir
    assert first_memory.include_global is False


def test_desktop_split_task_long_term_store_is_isolated_for_ordinary_tasks(
    monkeypatch, tmp_path
) -> None:
    store = ConversationStore(tmp_path / "conversations")
    parent = store.create("parent")
    child = store.create_split(parent["id"])
    monkeypatch.setattr(desktop, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(desktop, "conversation_store", store)

    parent_memory = desktop._memory_store_for_conversation(store.load(parent["id"]))
    child_memory = desktop._memory_store_for_conversation(store.load(child["id"]))

    assert parent_memory.workspace_dir != child_memory.workspace_dir
    assert parent_memory.workspace_path == store.memory_dir(parent["id"])
    assert child_memory.workspace_path == store.memory_dir(child["id"])
    assert store.short_term_memory_dir(parent["id"]) != store.short_term_memory_dir(
        child["id"]
    )


def test_desktop_lists_primary_and_split_tasks_in_separate_views(
    monkeypatch, tmp_path
) -> None:
    store = ConversationStore(tmp_path / "conversations")
    parent = store.create("parent")
    child = store.create_split(parent["id"])
    monkeypatch.setattr(desktop, "conversation_store", store)

    primary = desktop.list_conversations()
    split = desktop.list_conversations(child["id"])

    assert parent["id"] in {item["id"] for item in primary["conversations"]}
    assert child["id"] not in {item["id"] for item in primary["conversations"]}
    assert [item["id"] for item in split["conversations"]] == [child["id"]]
    assert split["active_id"] == child["id"]

    store.set_active(parent["id"])
    monkeypatch.setattr(desktop, "_executor_for_conversation", lambda _id: object())
    activated = desktop.set_active_conversation(child["id"])
    assert activated["success"] is True
    assert store.active_id() == parent["id"]


def test_desktop_delete_split_routes_to_exact_internal_child(
    monkeypatch, tmp_path
) -> None:
    store = ConversationStore(tmp_path / "conversations")
    parent = store.create("parent")
    child = store.create_split(parent["id"])
    monkeypatch.setattr(desktop, "conversation_store", store)
    deleted = []
    monkeypatch.setattr(
        desktop,
        "delete_conversation",
        lambda conversation_id: deleted.append(conversation_id) or {"success": True},
    )

    result = desktop.delete_split_conversation(parent["id"])

    assert result["success"] is True
    assert deleted == [child["id"]]


def test_desktop_split_response_distinguishes_create_from_restore(
    monkeypatch, tmp_path
) -> None:
    store = ConversationStore(tmp_path / "conversations")
    parent = store.create("parent")
    monkeypatch.setattr(desktop, "conversation_store", store)
    monkeypatch.setattr(desktop, "_executor_for_conversation", lambda _id: object())

    created = desktop.create_split_conversation(parent["id"])
    child_id = created["conversation"]["id"]
    child_history = store.short_term_memory_dir(child_id) / "execution_history.md"
    child_history.write_text("keep child branch\n", encoding="utf-8")
    store.set_split_state(parent["id"], is_open=False)
    restored = desktop.create_split_conversation(parent["id"])

    assert created["created"] is True
    assert restored["created"] is False
    assert restored["conversation"]["id"] == child_id
    assert child_history.read_text(encoding="utf-8") == "keep child branch\n"


def test_desktop_security_headers_allow_only_same_origin_split_tasks(
    monkeypatch,
) -> None:
    class _Response:
        def __init__(self) -> None:
            self.headers = {}

        def add_header(self, name, value) -> None:
            self.headers[name] = value

        def set_header(self, name, value) -> None:
            self.headers[name] = value

    original_routes = dict(desktop.eel.BOTTLE_ROUTES)
    try:
        monkeypatch.setattr(
            desktop.eel,
            "BOTTLE_ROUTES",
            {
                "/eel.js": (lambda: "websocket_addr += ('?page=' + page);", {}),
                "/eel": (lambda _ws: None, {}),
            },
        )
        app, _token = desktop._create_secured_eel_app(8123)
        after_request = next(
            callback
            for callback in app._hooks["after_request"]
            if callback.__name__ == "add_security_headers"
        )
        response = _Response()
        monkeypatch.setattr(desktop.bottle, "response", response)
        after_request()

        assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
        assert "frame-ancestors 'self'" in response.headers[
            "Content-Security-Policy"
        ]
    finally:
        desktop.eel.BOTTLE_ROUTES = original_routes


def test_desktop_task_switch_discards_stale_retrieval_cache(monkeypatch, tmp_path) -> None:
    store = ConversationStore(tmp_path / "conversations")
    conversation_id = store.active_id()
    monkeypatch.setattr(desktop, "conversation_store", store)

    executor = desktop.DesktopTaskExecutor()
    executor.tool_executor = SimpleNamespace(clear_plan_snapshots=lambda _id: None)
    executor.memory_manager = MemoryManager(str(store.memory_dir(conversation_id)))
    executor.memory_manager.save_memory_context("<memory-context>old</memory-context>")

    executor.activate_conversation(conversation_id)

    assert executor._memory_context_block == ""


def test_desktop_memory_file_map_includes_injected_memory_context() -> None:
    assert desktop.MEMORY_FILE_NAMES["memory_context"] == "memory_context.md"


def test_desktop_eel_connection_guards_and_close_callback_keep_server_alive() -> None:
    source = (
        "_import_py_function: function(name) {\n"
        "        let func_name = name;\n"
        "        eel[name] = function() {\n"
        "            let call_object = eel._call_object(func_name, arguments);\n"
        "            eel._websocket.send(eel._toJSON(call_object));\n"
        "            return eel._call_return(call_object);\n"
        "        }\n"
        "    },"
    )

    guarded = desktop._inject_eel_connection_guards(source)

    assert "readyState !== WebSocket.OPEN" in guarded
    assert "Eel connection is unavailable" in guarded
    assert desktop._keep_desktop_server_alive("index.html", []) is None


def test_desktop_eel_connection_guards_reject_unexpected_runtime_source() -> None:
    try:
        desktop._inject_eel_connection_guards("unrecognized Eel source")
    except RuntimeError as error:
        assert "connection guards" in str(error)
    else:
        raise AssertionError("Expected Eel bootstrap validation to fail")


def test_desktop_serializes_concurrent_eel_websocket_sends(monkeypatch) -> None:
    import gevent

    active = 0
    max_active = 0
    delivered = []

    def overlapping_send(_ws, message):
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        gevent.sleep(0.001)
        delivered.append(message)
        active -= 1

    monkeypatch.setattr(desktop.eel, "_repeated_send", overlapping_send)

    desktop._install_eel_send_serialization()
    jobs = [
        gevent.spawn(desktop.eel._repeated_send, object(), str(index))
        for index in range(20)
    ]
    gevent.joinall(jobs)

    assert max_active == 1
    assert sorted(delivered, key=int) == [str(index) for index in range(20)]
    first_wrapper = desktop.eel._repeated_send
    desktop._install_eel_send_serialization()
    assert desktop.eel._repeated_send is first_wrapper


def test_desktop_main_disables_eel_auto_shutdown(monkeypatch) -> None:
    started = {}

    monkeypatch.setattr(desktop.eel, "init", lambda _path: None)
    monkeypatch.setenv("MINIBOT_DESKTOP_PORT", "8123")
    monkeypatch.setattr(
        desktop,
        "_find_available_desktop_port",
        lambda port: started.setdefault("preferred_port", port) or port,
    )
    monkeypatch.setattr(
        desktop,
        "_create_secured_eel_app",
        lambda _port: (object(), "test-session"),
    )
    monkeypatch.setattr(desktop.os_agent, "preview_manager", None)
    monkeypatch.setattr(desktop, "conversation_runs", {})

    def fake_start(*args, **kwargs):
        started["args"] = args
        started["kwargs"] = kwargs

    monkeypatch.setattr(desktop.eel, "start", fake_start)

    desktop.main()

    assert started["args"] == ("index.html#eel_session=test-session",)
    assert started["preferred_port"] == 8123
    assert started["kwargs"]["port"] == 8123
    assert started["kwargs"]["close_callback"] is desktop._keep_desktop_server_alive
    assert started["kwargs"]["host"] == "127.0.0.1"


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


def test_desktop_persists_safe_tool_target_without_raw_arguments(
    monkeypatch, tmp_path
) -> None:
    store = ConversationStore(tmp_path / "conversations")
    conversation = store.create("tool target")
    monkeypatch.setattr(desktop, "conversation_store", store)

    desktop._persist_step(
        {
            "type": "tool",
            "tool": "write",
            "result": "File written",
            "target": "/project/src/app.py",
            "duration_ms": 125,
        },
        304,
        conversation["id"],
    )

    saved = store.load(conversation["id"])["messages"][-1]
    assert saved["target"] == "/project/src/app.py"
    assert "params" not in saved
    assert desktop._tool_target(
        "write", {"path": "/project/src/app.py", "content": "secret"}
    ) == "/project/src/app.py"
    assert desktop._tool_target(
        "bash", {"command": "echo secret", "workdir": "/project"}
    ) == "/project"


def test_desktop_emits_one_persisted_modified_files_summary_at_task_end(
    monkeypatch, tmp_path
) -> None:
    store = ConversationStore(tmp_path / "conversations")
    conversation = store.create("edited files")
    monkeypatch.setattr(desktop, "conversation_store", store)
    monkeypatch.setattr(desktop, "PROJECT_ROOT", tmp_path)
    executor = _prepare_desktop(
        monkeypatch,
        tmp_path,
        LangGraphRunner(_FinalModel(), [], lambda *_args: ""),
        persist_steps=True,
    )
    _register_executor(conversation["id"], executor)
    run = desktop._begin_execution(901, conversation["id"])
    assert run is not None
    publish = desktop._graph_event_publisher(run)

    edited_path = tmp_path / "agent" / "ui" / "desktop" / "app.js"
    edited_path.parent.mkdir(parents=True)
    edited_path.write_text("alpha\nbeta\n", encoding="utf-8")
    created_path = tmp_path / "tests" / "new_test.py"

    publish(
        {
            "type": "tool_start",
            "tool": "write",
            "params": {"path": str(edited_path), "content": "hidden"},
            "tool_call_id": "write-edited-1",
        }
    )
    edited_path.write_text("alpha\nmiddle\n", encoding="utf-8")
    publish(
        {
            "type": "tool_end",
            "tool": "write",
            "params": {"path": str(edited_path), "content": "hidden"},
            "result": "File written",
            "failed": False,
            "tool_call_id": "write-edited-1",
        }
    )
    # A second write must collapse into the same net task-end diff.
    publish(
        {
            "type": "tool_start",
            "tool": "edit",
            "params": {"filePath": str(edited_path)},
            "tool_call_id": "edit-edited-2",
        }
    )
    edited_path.write_text("alpha\nnew\nextra\n", encoding="utf-8")
    publish(
        {
            "type": "tool_end",
            "tool": "edit",
            "params": {"filePath": str(edited_path)},
            "result": "Edit applied successfully.",
            "failed": False,
            "tool_call_id": "edit-edited-2",
        }
    )
    publish(
        {
            "type": "tool_start",
            "tool": "write",
            "params": {"path": str(created_path), "content": "hidden"},
            "tool_call_id": "write-created-1",
        }
    )
    created_path.parent.mkdir(parents=True)
    created_path.write_text("first\nsecond\nthird\n", encoding="utf-8")
    publish(
        {
            "type": "tool_end",
            "tool": "write",
            "params": {"path": str(created_path), "content": "hidden"},
            "result": "File written",
            "failed": False,
            "tool_call_id": "write-created-1",
        }
    )

    desktop._finish_execution(run, "complete")
    events = desktop.get_next_results(conversation["id"], 901, 64)
    summaries = [event for event in events if event["type"] == "modified_files"]
    saved = store.load(conversation["id"])["messages"]
    persisted = [event for event in saved if event["type"] == "modified_files"]

    assert events[-1]["type"] == "modified_files"
    assert len(summaries) == 1
    assert summaries[0]["additions"] == 5
    assert summaries[0]["deletions"] == 1
    assert [
        {
            "path": item["path"],
            "additions": item["additions"],
            "deletions": item["deletions"],
        }
        for item in summaries[0]["files"]
    ] == [
        {
            "path": "agent/ui/desktop/app.js",
            "additions": 2,
            "deletions": 1,
        },
        {"path": "tests/new_test.py", "additions": 3, "deletions": 0},
    ]
    assert len(persisted) == 1
    assert persisted[0]["message_id"] == 901
    assert persisted[0]["files"] == summaries[0]["files"]
    desktop._finish_execution(run, "complete")
    assert not desktop.get_next_results(conversation["id"], 901, 64)


def test_subagent_edits_are_included_in_the_parent_task_review(
    monkeypatch, tmp_path
) -> None:
    executor = _prepare_desktop(
        monkeypatch,
        tmp_path,
        LangGraphRunner(_FinalModel(), [], lambda *_args: ""),
    )
    executor.project_root = tmp_path
    run = desktop.DesktopRunContext(
        "subagent-review", 907, 1, executor, multi_agent_enabled=True
    )
    first_path = tmp_path / "src" / "first.py"
    second_path = tmp_path / "src" / "second.py"
    first_path.parent.mkdir()
    first_path.write_text("old_first\n", encoding="utf-8")
    second_path.write_text("old_second\n", encoding="utf-8")

    def edit_from(agent_id, path, content):
        publish = desktop._subagent_event_publisher(
            lambda *_args, **_kwargs: None,
            lambda event: desktop._track_subagent_file_mutation(run, agent_id, event),
        )
        # Child runners can generate matching call ids independently. The
        # per-agent mutation scope keeps their pre-edit snapshots separate.
        event = {
            "tool": "edit",
            "params": {"filePath": str(path)},
            "tool_call_id": "child-edit-1",
        }
        publish({"type": "tool_start", **event})
        path.write_text(content, encoding="utf-8")
        publish({"type": "tool_end", "result": "Edit applied", **event})

    edit_from("first", first_path, "new_first\n")
    edit_from("second", second_path, "new_second\n")

    summary = desktop._modified_files_payload(run)

    assert summary is not None
    assert summary["additions"] == 2
    assert summary["deletions"] == 2
    assert [file["path"] for file in summary["files"]] == [
        "src/first.py",
        "src/second.py",
    ]
    assert all(file["reviewable"] and file["hunks"] for file in summary["files"])


def test_modified_file_totals_count_created_and_deleted_text_lines(tmp_path) -> None:
    path = tmp_path / "multiline.txt"
    missing_before = desktop._modified_file_snapshot(str(path), path)
    path.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
    created = desktop._modified_file_snapshot(str(path), path)

    assert desktop._modified_file_line_totals(missing_before, created) == (3, 0)

    path.unlink()
    missing_after = desktop._modified_file_snapshot(str(path), path)
    assert desktop._modified_file_line_totals(created, missing_after) == (0, 3)


def test_modified_files_payload_contains_restorable_structured_diff(tmp_path) -> None:
    path = tmp_path / "review.py"
    path.write_text("def greet():\n    return 'old'\n", encoding="utf-8")
    before = desktop._modified_file_snapshot(str(path), path)
    path.write_text(
        "def greet():\n    message = 'new'\n    return message\n",
        encoding="utf-8",
    )
    after = desktop._modified_file_snapshot(str(path), path)
    run = desktop.DesktopRunContext(
        conversation_id="review-conversation",
        message_id=904,
        generation=1,
        executor=object(),
    )
    run.modified_file_changes[str(path)] = desktop._ModifiedFileChange(before, after)

    payload = desktop._modified_files_payload(run)

    assert payload is not None
    assert payload["additions"] == 2
    assert payload["deletions"] == 1
    assert len(payload["files"]) == 1
    file_review = payload["files"][0]
    assert file_review["reviewable"] is True
    assert file_review["review_reason"] == ""
    assert file_review["hunks"]
    hunk = file_review["hunks"][0]
    assert {
        "old_start",
        "old_count",
        "new_start",
        "new_count",
        "lines",
    } <= set(hunk)
    assert any(
        line == {
            "type": "delete",
            "old_line": 2,
            "new_line": None,
            "content": "    return 'old'",
        }
        for line in hunk["lines"]
    )
    assert any(
        line["type"] == "add"
        and line["old_line"] is None
        and line["new_line"] == 2
        and line["content"] == "    message = 'new'"
        for line in hunk["lines"]
    )


def test_modified_files_diff_is_persisted_instead_of_read_from_current_disk(
    monkeypatch, tmp_path
) -> None:
    store = ConversationStore(tmp_path / "conversations")
    conversation = store.create("durable code review")
    monkeypatch.setattr(desktop, "conversation_store", store)
    step = {
        "type": "modified_files",
        "files": [
            {
                "path": "src/example.py",
                "additions": 1,
                "deletions": 1,
                "reviewable": True,
                "review_reason": "",
                "hunks": [
                    {
                        "old_start": 7,
                        "old_count": 1,
                        "new_start": 7,
                        "new_count": 1,
                        "lines": [
                            {
                                "type": "delete",
                                "old_line": 7,
                                "new_line": None,
                                "content": "old_value = 1",
                            },
                            {
                                "type": "add",
                                "old_line": None,
                                "new_line": 7,
                                "content": "new_value = 2",
                            },
                        ],
                    }
                ],
            }
        ],
    }

    desktop._persist_step(step, 905, conversation["id"])
    saved = store.load(conversation["id"])["messages"][-1]

    assert saved["type"] == "modified_files"
    assert saved["message_id"] == 905
    assert saved["files"][0]["reviewable"] is True
    assert saved["files"][0]["review_reason"] == ""
    assert saved["files"][0]["hunks"] == step["files"][0]["hunks"]


def test_desktop_finalization_barrier_opens_after_task_end_summary_persists(
    monkeypatch, tmp_path
) -> None:
    """Keep polling alive while the final task-end event is being persisted."""
    store = ConversationStore(tmp_path / "conversations")
    conversation = store.create("completion barrier")
    monkeypatch.setattr(desktop, "conversation_store", store)
    monkeypatch.setattr(desktop, "PROJECT_ROOT", tmp_path)
    executor = _prepare_desktop(
        monkeypatch,
        tmp_path,
        LangGraphRunner(_FinalModel(), [], lambda *_args: ""),
        persist_steps=True,
    )
    _register_executor(conversation["id"], executor)
    run = desktop._begin_execution(903, conversation["id"])
    assert run is not None

    path = tmp_path / "workspace" / "output" / "result.txt"
    before = desktop._modified_file_snapshot("workspace/output/result.txt", path)
    path.parent.mkdir(parents=True)
    path.write_text("done\n", encoding="utf-8")
    after = desktop._modified_file_snapshot("workspace/output/result.txt", path)
    run.modified_file_changes[str(path)] = desktop._ModifiedFileChange(before, after)

    # The final stream event is intentionally queued before finish-time work.
    desktop.push_step(
        {"type": "stream_end", "target": "final", "content": "done"},
        run.message_id,
        run.conversation_id,
        run.generation,
    )

    observed = {}
    original_mark_completed = store.mark_completed

    def observe_completion(conversation_id, message_id, unread=None):
        observed["status"] = desktop.get_execution_status(conversation_id, message_id)
        observed["events"] = desktop.get_next_results(conversation_id, message_id, 64)
        observed["history"] = store.load(conversation_id)["messages"]
        return original_mark_completed(conversation_id, message_id, unread)

    monkeypatch.setattr(store, "mark_completed", observe_completion)

    desktop._finish_execution(run, "complete")

    assert observed["status"]["running"] is False
    assert observed["status"]["finalized"] is False
    assert [event["type"] for event in observed["events"]] == [
        "stream_end",
        "modified_files",
    ]
    assert observed["history"][-1]["type"] == "modified_files"
    assert desktop.get_execution_status(conversation["id"], 903)["finalized"] is True


def test_desktop_ignores_failed_file_mutations_in_task_summary(
    monkeypatch, tmp_path
) -> None:
    store = ConversationStore(tmp_path / "conversations")
    conversation = store.create("failed write")
    monkeypatch.setattr(desktop, "conversation_store", store)
    executor = _prepare_desktop(
        monkeypatch,
        tmp_path,
        LangGraphRunner(_FinalModel(), [], lambda *_args: ""),
        persist_steps=True,
    )
    _register_executor(conversation["id"], executor)
    run = desktop._begin_execution(902, conversation["id"])
    assert run is not None
    path = tmp_path / "unchanged.py"
    publish = desktop._graph_event_publisher(run)
    publish(
        {
            "type": "tool_start",
            "tool": "write",
            "params": {"path": str(path)},
            "tool_call_id": "failed-write",
        }
    )
    publish(
        {
            "type": "tool_end",
            "tool": "write",
            "params": {"path": str(path)},
            "result": "Error: permission denied",
            "failed": True,
            "tool_call_id": "failed-write",
        }
    )

    desktop._finish_execution(run, "complete")
    events = desktop.get_next_results(conversation["id"], 902, 64)

    assert not any(event["type"] == "modified_files" for event in events)
    assert not any(
        event["type"] == "modified_files"
        for event in store.load(conversation["id"])["messages"]
    )


def test_desktop_stop_persists_completed_file_changes_once(
    monkeypatch, tmp_path
) -> None:
    """Stop returns a card for completed writes without waiting for the worker."""
    store = ConversationStore(tmp_path / "conversations")
    conversation = store.create("stopped write")
    monkeypatch.setattr(desktop, "conversation_store", store)
    monkeypatch.setattr(desktop, "PROJECT_ROOT", tmp_path)
    executor = _prepare_desktop(
        monkeypatch,
        tmp_path,
        LangGraphRunner(_FinalModel(), [], lambda *_args: ""),
        persist_steps=True,
    )
    _register_executor(conversation["id"], executor)
    run = desktop._begin_execution(906, conversation["id"])
    assert run is not None

    path = tmp_path / "workspace" / "output" / "result.txt"
    before = desktop._modified_file_snapshot("workspace/output/result.txt", path)
    path.parent.mkdir(parents=True)
    path.write_text("finished write\n", encoding="utf-8")
    after = desktop._modified_file_snapshot("workspace/output/result.txt", path)
    run.modified_file_changes[str(path)] = desktop._ModifiedFileChange(before, after)

    stopped = desktop.stop_execution(conversation["id"], 906)
    events = desktop.get_next_results(conversation["id"], 906, 64)
    saved = store.load(conversation["id"])["messages"]

    assert stopped["success"] is True
    assert stopped["modified_files"] is not None
    assert stopped["modified_files"]["message_id"] == 906
    assert stopped["modified_files"]["conversation_id"] == conversation["id"]
    assert [event["type"] for event in events] == ["modified_files"]
    assert events[0]["files"][0]["hunks"]
    assert [event["type"] for event in saved] == ["modified_files"]

    desktop._finish_execution(run, "stopped")
    assert desktop.get_next_results(conversation["id"], 906, 64) == []
    saved = store.load(conversation["id"])["messages"]
    assert [event["type"] for event in saved] == ["modified_files"]


def test_desktop_tool_events_expose_only_a_safe_target(monkeypatch, tmp_path) -> None:
    runner = LangGraphRunner(
        _TargetToolModel(),
        [_simple_tool("write")],
        lambda *_args: "File written",
    )
    executor = _prepare_desktop(monkeypatch, tmp_path, runner)
    _register_executor("conversation", executor)
    run = desktop._begin_execution(305, "conversation")
    assert run is not None

    assert desktop._run_graph_task("write it", "system", run) == "complete"
    events = desktop.get_next_results("conversation", 305, 64)
    started = next(event for event in events if event["type"] == "tool_start")
    completed = next(event for event in events if event["type"] == "tool")

    assert started["target"] == "/project/src/app.py"
    assert started["params"] == {"path": "/project/src/app.py"}
    assert "content" not in started["params"]
    assert completed["target"] == "/project/src/app.py"
    assert "params" not in completed
    desktop._finish_execution(run, "complete")


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
        "todos": [
            {"id": "implement", "content": "实现功能", "status": "in_progress"},
            {"id": "verify", "content": "运行验证", "status": "pending"},
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
    run = desktop._begin_execution(
        306,
        conversation["id"],
        plan_enabled=True,
        plan_policy="manual",
    )
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
        and event.get("tool") == "todo_write"
        for event in events
    )
    persisted = [event for event in saved if event["type"] == "plan_update"]
    assert len(persisted) == 1
    assert persisted[0]["plan"] == [
        {"step": "实现功能", "status": "in_progress"},
        {"step": "运行验证", "status": "pending"},
    ]


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
    run = desktop._begin_execution(
        307,
        conversation["id"],
        plan_enabled=True,
        plan_policy="manual",
    )
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


def test_plan_mode_only_auto_enables_for_exceptionally_complex_projects() -> None:
    assert desktop._resolve_plan_mode(False, "读取这个文件并修复一个拼写错误") == (
        False,
        "off",
    )
    assert desktop._resolve_plan_mode("true", "回复用户的问题") == (True, "manual")

    complex_request = """开发一个完整的全栈项目：
    - 设计系统架构和认证授权
    - 实现多个前端页面和后台模块
    - 建立数据库数据模型与迁移
    - 编写集成测试并用 Docker 部署
    """
    assert desktop._resolve_plan_mode(False, complex_request) == (True, "auto")


def test_plan_mode_is_removed_from_the_runtime_tool_binding_when_off() -> None:
    bound_tool_sets: list[list[str]] = []

    class _BindingPlanModel(_PlanModel):
        def bind_tools(self, tools, **kwargs):
            bound_tool_sets.append([tool.name for tool in tools])
            return self

    executed = []
    events = []
    runner = LangGraphRunner(
        _BindingPlanModel(),
        [_plan_tool(), _simple_tool("read")],
        lambda name, *_args: executed.append(name) or "unexpected",
    )

    result = runner.run(
        "plan-disabled",
        "continue",
        runtime={"plan_enabled": False},
        emit=events.append,
    )

    assert bound_tool_sets == [["todo_write", "read"], ["read"]]
    assert result.status == "complete"
    assert executed == []
    disabled = [
        event
        for event in events
        if event["type"] == "tool_end" and event.get("tool") == "todo_write"
    ]
    assert len(disabled) == 1
    assert disabled[0]["disabled"] is True


def test_voice_mode_removes_question_from_runtime_tool_binding() -> None:
    bound_tool_sets: list[list[str]] = []

    class _BindingQuestionModel(_QuestionModel):
        def bind_tools(self, tools, **kwargs):
            bound_tool_sets.append([tool.name for tool in tools])
            return self

    events = []
    runner = LangGraphRunner(
        _BindingQuestionModel(),
        [_question_tool(), _simple_tool("read")],
        lambda *_args: "unexpected",
    )

    result = runner.run(
        "voice-question-disabled",
        "continue",
        runtime={"voice_mode": True, "plan_enabled": True},
        emit=events.append,
    )

    assert bound_tool_sets == [["question", "read"], ["read"]]
    assert result.status == "complete"
    disabled = [
        event
        for event in events
        if event["type"] == "tool_end" and event.get("tool") == "question"
    ]
    assert len(disabled) == 1
    assert disabled[0]["disabled"] is True
    assert "disabled in voice conversation mode" in disabled[0]["result"]


def test_plan_mode_prompt_requires_a_plan_only_when_enabled(
    monkeypatch, tmp_path
) -> None:
    executor = _prepare_desktop(
        monkeypatch,
        tmp_path,
        LangGraphRunner(_FinalModel(), [], lambda *args: ""),
    )

    enabled_prompt, _ = executor.build_system_prompt(
        "实现功能", plan_enabled=True, plan_policy="manual"
    )
    disabled_prompt, _ = executor.build_system_prompt(
        "实现功能", plan_enabled=False, plan_policy="off"
    )

    assert "Plan Mode was explicitly selected by the user." in enabled_prompt
    assert "MUST call `todo_write`" in enabled_prompt
    assert "Plan Mode is off for this task." in disabled_prompt
    assert "`todo_write` is unavailable" in disabled_prompt
    assert "{plan_mode_instruction}" not in enabled_prompt
    assert "{plan_mode_instruction}" not in disabled_prompt
    assert "{runtime_mode_instruction}" not in enabled_prompt
    assert "running locally in the desktop app" in enabled_prompt


def test_multi_agent_prompt_and_runtime_tools_are_task_scoped(
    monkeypatch, tmp_path
) -> None:
    executor = _prepare_desktop(
        monkeypatch,
        tmp_path,
        LangGraphRunner(_FinalModel(), [], lambda *args: ""),
    )

    enabled_prompt, _ = executor.build_system_prompt(
        "并行检查项目", multi_agent_enabled=True
    )
    disabled_prompt, _ = executor.build_system_prompt(
        "检查项目", multi_agent_enabled=False
    )

    assert "Multi-Agent Mode was explicitly selected by the user." in enabled_prompt
    assert "isolated model history" in enabled_prompt
    assert "do not use primary-agent tools to duplicate or replace work" in enabled_prompt
    assert "integration, conflict resolution, and final verification" in enabled_prompt
    assert "Do not finish while a required child" in enabled_prompt
    assert "MUST assign one or more implementation children scoped write access" in enabled_prompt
    assert "write_access: true" in enabled_prompt
    assert "Do not make all children read-only" in enabled_prompt
    assert "Project contract v1" in enabled_prompt
    assert "single source of truth for shared state/configuration" in enabled_prompt
    assert "change proposal" in enabled_prompt
    assert "Multi-Agent Mode is off for this task." in disabled_prompt
    assert "{multi_agent_mode_instruction}" not in enabled_prompt
    assert "{multi_agent_mode_instruction}" not in disabled_prompt

    collaboration_tools = desktop.ExtendedToolExecutor._multi_agent_tool_definitions()
    monkeypatch.setattr(
        executor,
        "get_available_tools",
        lambda: [_simple_tool("read"), *collaboration_tools],
    )
    disabled_names = {
        tool["function"]["name"]
        for tool in executor.get_runtime_tools(multi_agent_enabled=False)
    }
    enabled_names = {
        tool["function"]["name"]
        for tool in executor.get_runtime_tools(multi_agent_enabled=True)
    }

    assert disabled_names == {"read"}
    assert desktop._MULTI_AGENT_TOOL_NAMES.issubset(enabled_names)

    _register_executor("multi-runtime", executor)
    run = desktop._begin_execution(
        1201,
        "multi-runtime",
        multi_agent_enabled=True,
    )
    assert run is not None
    runtime = desktop._graph_runtime(run)
    assert runtime["multi_agent_enabled"] is True
    assert callable(runtime["multi_agent_dispatch"])
    assert callable(runtime["finish_guard"])
    assert runtime["multi_agent_dispatch"]("list_agents", {}) == {
        "team_id": "",
        "version": 0,
        "status": "idle",
        "active_count": 0,
        "agents": [],
    }


def test_primary_tool_events_are_explicitly_attributed(
    monkeypatch, tmp_path
) -> None:
    store = ConversationStore(tmp_path / "conversations")
    conversation = store.create("primary tool attribution")
    monkeypatch.setattr(desktop, "conversation_store", store)
    executor = _prepare_desktop(
        monkeypatch,
        tmp_path,
        LangGraphRunner(_FinalModel(), [], lambda *args: ""),
        persist_steps=True,
    )
    _register_executor(conversation["id"], executor)
    run = desktop._begin_execution(1203, conversation["id"], multi_agent_enabled=True)
    assert run is not None
    publish = desktop._graph_event_publisher(run)

    publish(
        {
            "type": "tool_preparing",
            "tool": "read",
            "prepared_tool_call_id": "read-primary",
        }
    )
    publish(
        {
            "type": "tool_start",
            "tool": "read",
            "params": {"path": "README.md"},
            "tool_call_id": "read-primary",
        }
    )
    publish(
        {
            "type": "tool_end",
            "tool": "read",
            "params": {"path": "README.md"},
            "result": "contents",
            "failed": False,
            "tool_call_id": "read-primary",
        }
    )

    events = desktop.get_next_results(conversation["id"], 1203, 64)
    tool_events = [
        event
        for event in events
        if event["type"] in {"tool_preparing", "tool_start", "tool"}
    ]
    assert [event["type"] for event in tool_events] == [
        "tool_preparing",
        "tool_start",
        "tool",
    ]
    assert all(event["actor"] == "primary" for event in tool_events)
    persisted = [
        event
        for event in store.load(conversation["id"])["messages"]
        if event["type"] == "tool"
    ]
    assert len(persisted) == 1
    assert persisted[0]["actor"] == "primary"


def test_message_access_mode_is_captured_atomically_for_the_task(
    monkeypatch, tmp_path
) -> None:
    store = ConversationStore(tmp_path / "conversations")
    conversation_id = store.active_id()
    assert conversation_id
    monkeypatch.setattr(desktop, "conversation_store", store)
    executor = _prepare_desktop(
        monkeypatch,
        tmp_path,
        LangGraphRunner(_FinalModel(), [], lambda *args: ""),
    )
    executor.auto_allow_all_commands = False
    executor.allow_all_commands = False
    _register_executor(conversation_id, executor)

    class _DormantThread:
        def __init__(self, *, target, daemon=False) -> None:
            self.target = target
            self.daemon = daemon

        def start(self) -> None:
            return None

    monkeypatch.setattr(desktop.threading, "Thread", _DormantThread)

    result = desktop.send_message(
        "delegate an implementation task",
        message_id=1202,
        conversation_id=conversation_id,
        multi_agent_mode=True,
        allow_all=True,
    )

    assert result == {"status": "processing"}
    run = desktop._run_for(conversation_id)
    assert run is not None
    assert run.executor.allow_all_commands is True
    assert desktop._graph_runtime(run)["allow_all"] is True


def test_subagent_runtime_has_private_memory_prompt_and_tool_context(
    monkeypatch, tmp_path
) -> None:
    class _Engine:
        def clear_history(self) -> None:
            pass

    monkeypatch.setattr(desktop, "AIEngine", _Engine)
    monkeypatch.setattr(desktop, "AIEngineChatModel", lambda engine: object())
    monkeypatch.setattr(
        "agent.core.data_integrator.DataIntegrator",
        lambda **_kwargs: _DataIntegrator(),
    )

    parent = desktop.DesktopTaskExecutor()
    parent.ai_engine = _Engine()
    parent.tool_executor = object()
    parent.memory_manager = MemoryManager(str(tmp_path / "parent-memory"))
    parent.memory_store = None
    parent.preview_manager = object()
    parent.langgraph_checkpointer = object()
    parent.project_root = tmp_path / "project"
    parent.project_root.mkdir()
    parent.conversation_id = "parent-conversation"
    parent.current_user_request = "PUBLIC_PARENT_GOAL_71D4"
    parent.memory_manager.append_execution_step("PRIVATE_PARENT_TRACE_8A31")

    first = desktop.DesktopTaskExecutor(shared_from=parent)
    first.initialize_subagent_runtime(
        parent,
        team_id="team-isolation",
        agent_id="first-agent",
    )
    second = desktop.DesktopTaskExecutor(shared_from=parent)
    second.initialize_subagent_runtime(
        parent,
        team_id="team-isolation",
        agent_id="second-agent",
    )
    first.memory_manager.append_execution_step("FIRST_AGENT_ONLY_42B7")
    second.memory_manager.append_execution_step("SECOND_AGENT_ONLY_99C2")

    run = desktop.DesktopRunContext(
        "parent-conversation",
        1202,
        1,
        parent,
        multi_agent_enabled=True,
    )
    contract = desktop._dispatch_multi_agent_tool(
        run,
        "publish_agent_artifact",
        {
            "title": "Project contract v1",
            "summary": "CONTRACT_PACKET_5C72: config.py owns shared state and API v1.",
            "paths": ["src/config.py"],
        },
    )
    assert contract["success"] is True
    assert run.agent_team is not None
    claimed = run.agent_team.spawn(
        "Contract consumer",
        "API implementer",
        "Use the published contract",
        write_access=True,
        write_paths=["src/consumer.py"],
    )
    system_prompt, user_message = desktop._subagent_prompt(
        run,
        first,
        {
            "agent_id": claimed["agent_id"],
            "name": "Reviewer",
            "role": "Read-only reviewer",
            "task": "Inspect the API boundary",
            "context": "Only inspect authentication code",
        },
        "Inspect the API boundary",
    )
    combined_prompt = f"{system_prompt}\n{user_message}"

    assert first.ai_engine is not parent.ai_engine
    assert first.tool_executor is not parent.tool_executor
    assert first.tool_executor is not second.tool_executor
    assert first.tool_loop_guard is not second.tool_loop_guard
    assert first.memory_manager.memory_dir != parent.memory_manager.memory_dir
    assert first.memory_manager.memory_dir != second.memory_manager.memory_dir
    assert first.memory_manager.memory_dir == (
        parent.memory_manager.memory_dir
        / "agents"
        / "team-isolation"
        / "first-agent"
    )
    assert parent.memory_manager.load_execution_history() == [
        "PRIVATE_PARENT_TRACE_8A31"
    ]
    assert first.memory_manager.load_execution_history() == [
        "FIRST_AGENT_ONLY_42B7"
    ]
    assert second.memory_manager.load_execution_history() == [
        "SECOND_AGENT_ONLY_99C2"
    ]
    assert "PUBLIC_PARENT_GOAL_71D4" in combined_prompt
    assert "Inspect the API boundary" in combined_prompt
    assert "Only inspect authentication code" in combined_prompt
    assert "Project contract v1" in combined_prompt
    assert "CONTRACT_PACKET_5C72" in combined_prompt
    assert "Active file ownership" in combined_prompt
    assert "src/consumer.py" in combined_prompt
    assert "change proposal" in combined_prompt
    assert "FIRST_AGENT_ONLY_42B7" in combined_prompt
    assert "PRIVATE_PARENT_TRACE_8A31" not in combined_prompt
    assert "SECOND_AGENT_ONLY_99C2" not in combined_prompt

    read_only_names = {
        tool["function"]["name"]
        for tool in first.get_subagent_tools(write_access=False)
    }
    writable_names = {
        tool["function"]["name"]
        for tool in first.get_subagent_tools(write_access=True)
    }
    assert {"read", "glob", "grep"}.issubset(read_only_names)
    assert {"edit", "write"}.isdisjoint(read_only_names)
    assert {"edit", "write"}.issubset(writable_names)
    assert desktop._SUBAGENT_COLLABORATION_TOOLS.issubset(writable_names)
    assert {"spawn_agent", "wait_agents", "list_agents", "cancel_agent"}.isdisjoint(
        writable_names
    )
    assert {"bash", "question", "todo_write"}.isdisjoint(writable_names)


def test_subagent_workdir_binds_relative_writes_to_generated_project(
    monkeypatch, tmp_path
) -> None:
    class _Engine:
        def clear_history(self) -> None:
            pass

    monkeypatch.setattr(desktop, "AIEngine", _Engine)
    monkeypatch.setattr(desktop, "AIEngineChatModel", lambda engine: object())
    monkeypatch.setattr(
        "agent.core.data_integrator.DataIntegrator",
        lambda **_kwargs: _DataIntegrator(),
    )

    parent = desktop.DesktopTaskExecutor()
    parent.ai_engine = _Engine()
    parent.tool_executor = object()
    parent.memory_manager = MemoryManager(str(tmp_path / "parent-memory"))
    parent.memory_store = None
    parent.preview_manager = object()
    parent.project_root = tmp_path / "jcodex-root"
    parent.project_root.mkdir()
    parent.conversation_id = "parent-workdir"

    generated_project = tmp_path / "workspace" / "output" / "ski-safari"
    child = desktop.DesktopTaskExecutor(shared_from=parent)
    child.initialize_subagent_runtime(
        parent,
        team_id="team-workdir",
        agent_id="engine-agent",
        write_access=True,
        write_paths=["src/engine"],
        workdir=str(generated_project),
    )

    inside = child.tool_executor.execute(
        {
            "tool": "write",
            "params": {"path": "src/engine/core.js", "content": "export const ok = true;\n"},
        }
    )
    outside = child.tool_executor.execute(
        {
            "tool": "write",
            "params": {"path": "src/ui/view.js", "content": "not allowed\n"},
        }
    )

    assert child.project_root == generated_project
    assert "Error:" not in inside
    assert (generated_project / "src" / "engine" / "core.js").is_file()
    assert "outside this agent's allowed write paths" in outside
    assert not (generated_project / "src" / "ui" / "view.js").exists()


def test_subagent_scope_prepares_generated_project_root_before_spawn(tmp_path) -> None:
    executor = SimpleNamespace(project_root=tmp_path / "jcodex-root")
    executor.project_root.mkdir()
    generated_project = executor.project_root / "workspace" / "output" / "new-app"

    workdir, write_paths = desktop._prepare_subagent_write_scope(
        executor,
        str(generated_project),
        ["src/engine/", "src/ui/"],
        True,
    )

    assert workdir == generated_project
    assert generated_project.is_dir()
    assert write_paths == [
        str(generated_project / "src" / "engine"),
        str(generated_project / "src" / "ui"),
    ]

    _, prefixed_write_paths = desktop._prepare_subagent_write_scope(
        executor,
        str(generated_project),
        ["workspace/output/new-app/src/ui.js", "new-app/src/game.js"],
        True,
    )
    assert prefixed_write_paths == [
        str(generated_project / "src" / "ui.js"),
        str(generated_project / "src" / "game.js"),
    ]
    assert desktop._display_subagent_paths(
        prefixed_write_paths, generated_project
    ) == ["src/ui.js", "src/game.js"]

    _, wildcard_directory_paths = desktop._prepare_subagent_write_scope(
        executor,
        str(generated_project),
        ["src/world/**", "src/engine/**/*"],
        True,
    )
    assert wildcard_directory_paths == [
        str(generated_project / "src" / "world"),
        str(generated_project / "src" / "engine"),
    ]


def test_voice_mode_prompt_is_scoped_to_spoken_tasks(monkeypatch, tmp_path) -> None:
    executor = _prepare_desktop(
        monkeypatch,
        tmp_path,
        LangGraphRunner(_FinalModel(), [], lambda *args: ""),
    )

    enabled_prompt, _ = executor.build_system_prompt(
        "讲个笑话", voice_mode=True
    )
    disabled_prompt, _ = executor.build_system_prompt(
        "讲个笑话", voice_mode=False
    )

    assert "Voice conversation mode is active." in enabled_prompt
    assert "one to three short sentences" in enabled_prompt
    assert "Never expose private reasoning" in enabled_prompt
    assert "URLs, file-system paths" in enabled_prompt
    assert "Do not call the `question` tool in voice mode" in enabled_prompt
    assert "wait for the user's next voice message" in enabled_prompt
    assert "Voice conversation mode is active." not in disabled_prompt


def test_voice_mode_survives_run_and_compression_prompt_rebuild(
    monkeypatch, tmp_path
) -> None:
    executor = _prepare_desktop(
        monkeypatch,
        tmp_path,
        LangGraphRunner(_FinalModel(), [], lambda *args: ""),
    )
    _register_executor("voice-conversation", executor)
    run = desktop._begin_execution(
        1099,
        "voice-conversation",
        voice_mode=True,
    )
    assert run is not None
    assert run.voice_mode is True
    assert desktop._graph_runtime(run)["voice_mode"] is True

    executor.current_user_request = "继续回答"
    monkeypatch.setattr(
        executor,
        "_compress_current_task_manual",
        lambda *args, **kwargs: {"success": True},
    )
    monkeypatch.setattr(executor, "_build_context", lambda: "compressed context")
    monkeypatch.setattr(
        executor.memory_manager,
        "load_accumulated_compression",
        lambda: "compressed summary",
    )
    captured = {}

    def build_prompt(user_request, context="", **kwargs):
        captured.update(kwargs)
        return "rebuilt system", "rebuilt user"

    monkeypatch.setattr(executor, "build_system_prompt", build_prompt)

    result = desktop._graph_compression_handler(
        run,
        {"step_count": 4},
        {"tokens_before": 999},
        lambda *_args: None,
    )

    assert captured["voice_mode"] is True
    assert result["system_prompt"] == "rebuilt system"
    assert result["tokens_after"] == executor.get_current_tokens()
    assert result["tokens_after"] > 0


def test_dynamic_compaction_reminder_keeps_live_jcodex_task_state(
    monkeypatch, tmp_path
) -> None:
    executor = _prepare_desktop(
        monkeypatch,
        tmp_path,
        LangGraphRunner(_FinalModel(), [], lambda *args: ""),
    )
    executor.tool_executor = SimpleNamespace(
        get_todo_snapshot=lambda *_args: [
            {"id": "implement", "content": "实现世界生成", "status": "in_progress"}
        ],
        get_running_background_tasks=lambda: [
            {"task_id": "server", "command": "npm run dev"}
        ],
        get_loaded_skills=lambda *_args: ["frontend-design"],
    )
    executor.preview_manager = SimpleNamespace(
        status=lambda **_kwargs: {
            "previews": [{"name": "Game", "url": "http://127.0.0.1:3000", "status": "ready"}]
        }
    )
    before = desktop._ModifiedFileSnapshot(
        path=tmp_path / "world.ts",
        display_path="world.ts",
        exists=True,
        is_file=True,
        text="old",
        fingerprint="old",
    )
    after = desktop._ModifiedFileSnapshot(
        path=tmp_path / "world.ts",
        display_path="world.ts",
        exists=True,
        is_file=True,
        text="new",
        fingerprint="new",
    )
    run = desktop.DesktopRunContext("conversation", 1, 1, executor)
    run.reference_folder_paths = [str(tmp_path / "reference")]
    run.modified_file_changes["world.ts"] = desktop._ModifiedFileChange(before, after)

    reminder = desktop._dynamic_compaction_reminder(run)

    assert reminder.startswith("<system-reminder>")
    assert "Files Edited This Task" in reminder
    assert "Todo List" in reminder
    assert "npm run dev" in reminder
    assert "frontend-design" in reminder
    assert "Active Project Previews" in reminder


def test_desktop_token_indicator_uses_compaction_snapshot_metric(
    monkeypatch, tmp_path
) -> None:
    executor = _prepare_desktop(
        monkeypatch,
        tmp_path,
        LangGraphRunner(_FinalModel(), [], lambda *args: ""),
    )
    executor.tool_executor = SimpleNamespace(
        get_available_tools=lambda: [_simple_tool("read")]
    )
    _register_executor("token-metric", executor)
    snapshot = executor.get_graph_compression_snapshot(
        {
            "system_prompt": "system rules " * 100,
            "messages": [HumanMessage(content="current task " * 200)],
            "step_count": 3,
        }
    )

    usage = executor.get_current_token_usage()
    response = desktop.get_token_count("token-metric")

    assert usage["source"] == "graph_snapshot"
    assert usage["tokens"] == snapshot["tokens_before"]
    assert usage["tokens"] == (
        usage["system_tokens"]
        + usage["message_tokens"]
        + usage["tool_tokens"]
    )
    assert response["tokens"] == snapshot["tokens_before"]
    assert response["compress_at"] == snapshot["threshold"]
    assert response["tool_tokens"] > 0


def test_desktop_compaction_metric_uses_plan_mode_tool_binding(
    monkeypatch, tmp_path
) -> None:
    executor = _prepare_desktop(
        monkeypatch,
        tmp_path,
        LangGraphRunner(_FinalModel(), [], lambda *args: ""),
    )
    executor.tool_executor = SimpleNamespace(
        get_available_tools=lambda: [_plan_tool(), _simple_tool("read")]
    )
    state = {
        "system_prompt": "system",
        "messages": [HumanMessage(content="task")],
        "step_count": 1,
    }

    enabled = executor.get_graph_compression_snapshot(
        state, plan_enabled=True
    )
    disabled = executor.get_graph_compression_snapshot(
        state, plan_enabled=False
    )

    assert [
        tool["function"]["name"]
        for tool in executor.get_runtime_tools(plan_enabled=False)
    ] == ["read"]
    assert enabled["context_snapshot"].tool_tokens > disabled[
        "context_snapshot"
    ].tool_tokens
    assert executor.get_current_tokens() == disabled["tokens_before"]


def test_desktop_prompt_only_protects_os_agent_source_from_normal_tasks(
    monkeypatch, tmp_path
) -> None:
    executor = _prepare_desktop(
        monkeypatch,
        tmp_path,
        LangGraphRunner(_FinalModel(), [], lambda *args: ""),
    )
    executor.project = None
    executor.project_root = desktop.PROJECT_ROOT

    prompt, _ = executor.build_system_prompt("编辑桌面上的文件")

    assert "Protect the JCodex application source tree" in prompt
    assert "This restriction applies only to the JCodex source tree" in prompt
    assert "Desktop, Documents, Downloads, dropped reference folders" in prompt
    assert "Treat the project as read-only except" not in prompt


def test_desktop_project_prompt_allows_explicit_external_and_reference_writes(
    monkeypatch, tmp_path
) -> None:
    executor = _prepare_desktop(
        monkeypatch,
        tmp_path,
        LangGraphRunner(_FinalModel(), [], lambda *args: ""),
    )
    project_root = tmp_path / "bound-project"
    project_root.mkdir()
    executor.project = {
        "id": "project-a",
        "name": "Bound Project",
        "root_path": str(project_root),
        "instructions": "",
        "available": True,
    }
    executor.project_root = project_root

    prompt, _ = executor.build_system_prompt("编辑参考文件夹")

    assert "Paths outside the bound project are not globally read-only" in prompt
    assert "Dropped reference folders have the same mutation permissions" in prompt
    assert "JCodex application source tree" in prompt
    assert "always protected from file-tool mutations" in prompt


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


def test_desktop_stop_cascades_to_the_active_agent_team(
    monkeypatch, tmp_path
) -> None:
    executor = _prepare_desktop(
        monkeypatch,
        tmp_path,
        LangGraphRunner(_FinalModel(), [], lambda *args: ""),
    )
    _register_executor("multi-stop", executor)
    run = desktop._begin_execution(
        623,
        "multi-stop",
        multi_agent_enabled=True,
    )
    assert run is not None

    class _Team:
        def __init__(self) -> None:
            self.cancel_calls = 0

        def cancel_all(self) -> dict:
            self.cancel_calls += 1
            return {"all_terminal": False, "active_count": 1}

    team = _Team()
    run.agent_team = team

    stopped = desktop.stop_execution("multi-stop", 623)

    assert stopped["success"] is True
    assert stopped["running"] is False
    assert run.cancel_event.is_set()
    assert team.cancel_calls == 1


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


def test_deleting_primary_desktop_task_cleans_internal_split_runtime_state(
    monkeypatch, tmp_path
) -> None:
    store = ConversationStore(tmp_path / "conversations")
    parent = store.create("parent")
    child = store.create_split(parent["id"])
    monkeypatch.setattr(desktop, "conversation_store", store)

    class _Runner:
        def __init__(self) -> None:
            self.prefixes = []

        def delete_threads_with_prefix(self, prefix):
            self.prefixes.append(prefix)
            return 1

        def vacuum_checkpoint_store(self):
            return True

    class _PreviewManager:
        def __init__(self) -> None:
            self.cleared = []

        def clear_conversation(self, conversation_id):
            self.cleared.append(conversation_id)

    runner = _Runner()
    preview = _PreviewManager()
    monkeypatch.setattr(desktop.os_agent, "preview_manager", preview)
    monkeypatch.setattr(desktop.os_agent, "langgraph_runner", runner)
    desktop.conversation_runs.clear()
    desktop.conversation_executors.clear()
    desktop.conversation_generations.clear()
    desktop.conversation_generations[parent["id"]] = 1
    desktop.conversation_generations[child["id"]] = 1
    monkeypatch.setattr(desktop, "_executor_for_conversation", lambda _id: object())

    result = desktop.delete_conversation(parent["id"])

    assert result["success"] is True
    assert result["deleted_conversation_ids"] == sorted([parent["id"], child["id"]])
    assert sorted(preview.cleared) == sorted([parent["id"], child["id"]])
    assert sorted(runner.prefixes) == sorted(
        [f"{parent['id']}:", f"{child['id']}:"]
    )
    assert parent["id"] not in desktop.conversation_generations
    assert child["id"] not in desktop.conversation_generations


def test_initialize_ignores_deleted_base_executor_conversation(
    monkeypatch, tmp_path
) -> None:
    store = ConversationStore(tmp_path / "conversations")
    deleted = store.create("deleted")
    store.set_active(deleted["id"])
    replacement_id = store.delete(deleted["id"])["active_id"]
    monkeypatch.setattr(desktop, "conversation_store", store)

    class _BaseExecutor:
        conversation_id = deleted["id"]

        @staticmethod
        def initialize():
            return True, "Already initialized"

    requested = []
    monkeypatch.setattr(desktop, "os_agent", _BaseExecutor())
    monkeypatch.setattr(
        desktop,
        "_executor_for_conversation",
        lambda conversation_id: requested.append(conversation_id),
    )

    result = desktop.initialize()

    assert result == (True, "Already initialized")
    assert requested == [replacement_id]


def test_initialize_returns_stale_split_as_normal_failure(
    monkeypatch, tmp_path
) -> None:
    store = ConversationStore(tmp_path / "conversations")
    parent = store.create("parent")
    child = store.create_split(parent["id"])
    store.delete(parent["id"])
    monkeypatch.setattr(desktop, "conversation_store", store)

    class _BaseExecutor:
        conversation_id = parent["id"]

        @staticmethod
        def initialize():
            return True, "Already initialized"

    monkeypatch.setattr(desktop, "os_agent", _BaseExecutor())

    assert desktop.initialize(child["id"]) == (False, "Conversation not found")


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
