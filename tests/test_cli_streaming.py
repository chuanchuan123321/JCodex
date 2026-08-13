"""Regression tests for terminal streaming output."""

from types import SimpleNamespace

import pytest

import chat
from agent.core.langgraph_runner import RunResult
from agent.core.memory_manager import MemoryManager


def _reset_spinner(monkeypatch) -> None:
    monkeypatch.setattr(chat, "_spinner_running", False)
    monkeypatch.setattr(chat, "_spinner_thread", None)


def test_stopping_an_inactive_spinner_does_not_clear_output(
    monkeypatch, capsys
) -> None:
    _reset_spinner(monkeypatch)

    chat.stop_spinner()

    assert capsys.readouterr().out == ""


def test_successive_content_chunks_are_not_erased(monkeypatch, capsys) -> None:
    _reset_spinner(monkeypatch)
    runtime = {"event_state": {}}
    executor = SimpleNamespace()

    for content in ("这是", "一条", "完整回答。"):
        chat.NaturalTaskExecutor._handle_langgraph_event(
            executor,
            {"type": "content_delta", "content": content},
            runtime,
        )

    output = capsys.readouterr().out
    assert output == "这是一条完整回答。"
    assert "\r" not in output


def test_terminal_prompt_resolves_the_plan_instruction(tmp_path) -> None:
    executor = chat.NaturalTaskExecutor.__new__(chat.NaturalTaskExecutor)
    executor.max_steps = 20
    executor.max_web_searches = 3
    executor.skills_loader = SimpleNamespace(build_skills_summary=lambda: "")
    executor.preference_manager = SimpleNamespace(
        _load_preferences=lambda: None,
        generate_prompt_context=lambda: "",
    )
    executor.knowledge_base = SimpleNamespace(
        build_query_context=lambda **_kwargs: ""
    )

    prompt, _ = executor._build_langgraph_prompt(
        "实现功能",
        "还没有执行任何步骤。",
        memory_manager=MemoryManager(str(tmp_path / "memory")),
        accumulated_compression="",
    )

    assert "{plan_mode_instruction}" not in prompt
    assert "Plan Mode is off for this task." in prompt
    assert "{multi_agent_mode_instruction}" not in prompt
    assert "Multi-Agent Mode is off for this task." in prompt
    assert "{platform_instruction}" not in prompt
    assert "{runtime_mode_instruction}" not in prompt
    assert "running locally, not through a gateway" in prompt


def test_gateway_question_answer_keeps_free_text_supplement() -> None:
    payload = chat.NaturalTaskExecutor._parse_gateway_question_answer(
        [
            {
                "question": "填写项目名称",
                "multiple": False,
                "selection_required": False,
                "allow_free_text": True,
                "options": [{"label": "中文名称"}],
            }
        ],
        "星图",
    )

    assert payload is not None
    assert payload["answers"] == [[]]
    assert payload["supplements"] == ["星图"]
    assert "补充：星图" in payload["content"]


def test_terminal_text_only_question_can_submit(monkeypatch) -> None:
    answers = iter(["星图"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    executor = chat.NaturalTaskExecutor.__new__(chat.NaturalTaskExecutor)

    payload = executor._ask_graph_questions(
        [
            {
                "header": "项目名称",
                "question": "填写项目名称",
                "multiple": False,
                "selection_required": False,
                "allow_free_text": True,
                "free_text_required": True,
                "options": [],
            }
        ]
    )

    assert payload["answers"] == [[]]
    assert payload["supplements"] == ["星图"]


def test_terminal_completion_deletes_and_compacts_checkpoint() -> None:
    class Runner:
        def __init__(self) -> None:
            self.deleted = []
            self.vacuum_calls = 0

        def delete_thread(self, thread_id: str) -> None:
            self.deleted.append(thread_id)

        def vacuum_checkpoint_store(self) -> bool:
            self.vacuum_calls += 1
            return True

    class Memory:
        @staticmethod
        def strip_reasoning(content: str) -> str:
            return content

        @staticmethod
        def append_execution_step(_content: str) -> None:
            pass

    class Integrator:
        @staticmethod
        def end_task(_status: str) -> None:
            pass

    runner = Runner()
    executor = chat.NaturalTaskExecutor.__new__(chat.NaturalTaskExecutor)
    executor.langgraph_runner = runner
    executor._known_graph_threads = {"cli:finished"}
    executor._gateway_active = {}
    executor.memory_manager = Memory()
    executor.data_integrator = Integrator()
    executor.is_gateway_mode = False
    runtime_memory = Memory()

    executor._finish_langgraph_task(
        RunResult("complete", "cli:finished", "run", content="done"),
        {
            "memory_manager": runtime_memory,
            "data_integrator": executor.data_integrator,
        },
    )

    assert runner.deleted == ["cli:finished"]
    assert runner.vacuum_calls == 1
    assert "cli:finished" not in executor._known_graph_threads


def test_waiting_terminal_task_keeps_checkpoint_for_resume() -> None:
    class Runner:
        def __init__(self) -> None:
            self.deleted = []
            self.vacuum_calls = 0

        def delete_thread(self, thread_id: str) -> None:
            self.deleted.append(thread_id)

        def vacuum_checkpoint_store(self) -> bool:
            self.vacuum_calls += 1
            return True

    runner = Runner()
    executor = chat.NaturalTaskExecutor.__new__(chat.NaturalTaskExecutor)
    executor.langgraph_runner = runner
    executor._known_graph_threads = {"cli:waiting"}
    executor._gateway_active = {}
    discarded = []
    executor.tool_executor = SimpleNamespace(
        discard_plan_snapshot=lambda conversation_id, message_id: discarded.append(
            (conversation_id, message_id)
        )
    )
    executor.memory_manager = SimpleNamespace()
    executor.data_integrator = SimpleNamespace()

    executor._finish_langgraph_task(
        RunResult("waiting", "cli:waiting", "run"),
        {
            "memory_manager": executor.memory_manager,
            "data_integrator": executor.data_integrator,
        },
    )

    assert runner.deleted == []
    assert runner.vacuum_calls == 0
    assert "cli:waiting" in executor._known_graph_threads
    assert discarded == []


@pytest.mark.parametrize("status", ["complete", "cancelled", "error"])
def test_terminal_task_discards_its_plan_registry(status) -> None:
    class Runner:
        @staticmethod
        def delete_thread(_thread_id: str) -> None:
            pass

        @staticmethod
        def vacuum_checkpoint_store() -> bool:
            return True

    class Memory:
        @staticmethod
        def strip_reasoning(content: str) -> str:
            return content

        @staticmethod
        def append_execution_step(_content: str) -> None:
            pass

    class Integrator:
        @staticmethod
        def end_task(_status: str) -> None:
            pass

    class PlanRegistry:
        def __init__(self) -> None:
            self.discarded = []

        def discard_plan_snapshot(self, conversation_id, message_id) -> None:
            self.discarded.append((conversation_id, message_id))

    registry = PlanRegistry()
    executor = chat.NaturalTaskExecutor.__new__(chat.NaturalTaskExecutor)
    executor.langgraph_runner = Runner()
    executor.tool_executor = registry
    executor._known_graph_threads = {"gateway:task"}
    executor._gateway_active = {"gateway-session": {}}
    executor.memory_manager = Memory()
    executor.data_integrator = Integrator()
    executor.is_gateway_mode = False
    runtime = {
        "session_key": "gateway-session",
        "run_id": "runtime-run",
        "memory_manager": executor.memory_manager,
        "data_integrator": executor.data_integrator,
    }

    executor._finish_langgraph_task(
        RunResult(status, "gateway:task", "result-run", content="done"),
        runtime,
    )

    assert registry.discarded == [("gateway-session", "runtime-run")]


def test_clear_history_clears_all_plan_registries() -> None:
    class PlanRegistry:
        def __init__(self) -> None:
            self.clear_calls = 0

        def clear_plan_snapshots(self) -> None:
            self.clear_calls += 1

    registry = PlanRegistry()
    executor = chat.NaturalTaskExecutor.__new__(chat.NaturalTaskExecutor)
    executor._active_graph_runtime = None
    executor._known_graph_threads = set()
    executor._gateway_pending = {}
    executor.langgraph_runner = SimpleNamespace()
    executor.tool_executor = registry
    executor.ai_engine = SimpleNamespace(clear_history=lambda: None)
    executor.execution_history = ["old"]
    executor.step_count = 2
    executor.web_search_count = 1
    executor.allow_all_commands = True
    executor.accumulated_compression = "old"
    executor.task_compression_summary = "old"
    executor.memory_manager = SimpleNamespace(clear_all=lambda: None)

    executor._clear_history()

    assert registry.clear_calls == 1
