"""Regression coverage for the consolidated local tool inventory."""

import json
from pathlib import Path

from agent.core.extended_tool_executor import ExtendedToolExecutor
from agent.core.multi_agent import MULTI_AGENT_TOOL_NAMES


def test_glob_uses_langchain_scoped_file_search(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    outside_root = tmp_path / "outside"
    (project_root / "src").mkdir(parents=True)
    outside_root.mkdir()
    (project_root / "src" / "app.py").write_text("print('ok')\n")
    (project_root / "src" / "nested").mkdir()
    (project_root / "src" / "nested" / "worker.py").write_text("pass\n")
    (project_root / "README.md").write_text("project\n")
    (outside_root / "external.py").write_text("outside\n")
    executor = ExtendedToolExecutor(
        project_root=project_root,
        preview_manager=object(),
        restrict_reads_to_project=True,
    )

    result = executor.execute_glob({"pattern": "*.py", "path": "src"})

    assert result == "app.py"
    assert executor.execute_glob({"pattern": "**/*.py", "path": "src"}) == (
        "app.py\nnested/worker.py"
    )
    assert executor.execute_glob(
        {"pattern": "*.py", "path": "../outside"}
    ) == "external.py"


def test_tool_inventory_keeps_unique_local_capabilities() -> None:
    executor = ExtendedToolExecutor(preview_manager=object())
    names = [tool["function"]["name"] for tool in executor.get_available_tools()]

    assert names.count("glob") == 1
    assert {"grep", "codesearch", "edit", "glob"}.issubset(names)
    assert "search_files" not in names
    assert "search_files" not in executor.tools
    redundant_terminal_tools = {
        "file_list",
        "file_delete",
        "dir_create",
        "copy_file",
        "move_file",
    }
    assert not redundant_terminal_tools.intersection(names)
    assert "read_pdf" not in names
    assert "send_file" not in names
    assert "update_plan" not in names
    assert "update_plan" in executor.tools
    gateway_names = [
        tool["function"]["name"]
        for tool in executor.get_available_tools(include_gateway_tools=True)
    ]
    assert gateway_names.count("send_file") == 1
    # Keep old checkpointed calls runnable without offering them to new tasks.
    assert (redundant_terminal_tools | {"read_pdf"}).issubset(executor.tools)


def test_tool_inventory_exposes_bounded_multi_agent_control_surface() -> None:
    executor = ExtendedToolExecutor(preview_manager=object())
    definitions = {
        tool["function"]["name"]: tool["function"]
        for tool in executor.get_available_tools()
    }

    assert MULTI_AGENT_TOOL_NAMES.issubset(definitions)
    assert all(
        sum(
            tool["function"]["name"] == name
            for tool in executor.get_available_tools()
        )
        == 1
        for name in MULTI_AGENT_TOOL_NAMES
    )
    assert definitions["spawn_agent"]["parameters"]["required"] == [
        "name",
        "role",
        "task",
    ]
    assert definitions["spawn_agent"]["parameters"]["additionalProperties"] is False
    assert "workdir" in definitions["spawn_agent"]["parameters"]["properties"]
    assert "creates this directory" in definitions["spawn_agent"]["parameters"]["properties"]["workdir"]["description"]
    assert definitions["send_agent_message"]["parameters"]["required"] == [
        "agent_id",
        "message",
    ]
    assert definitions["wait_agents"]["parameters"]["properties"]["timeout_ms"][
        "maximum"
    ] == 600000
    assert definitions["cancel_agent"]["parameters"]["required"] == ["agent_id"]


def test_scoped_child_writes_cannot_escape_assigned_paths(tmp_path: Path) -> None:
    project = tmp_path / "project"
    allowed = project / "allowed"
    outside = project / "outside"
    allowed.mkdir(parents=True)
    outside.mkdir()
    executor = ExtendedToolExecutor(
        project_root=project,
        workspace_root=tmp_path / "workspace",
        protected_root=tmp_path / "protected",
        preview_manager=object(),
    )
    executor.mutation_scope_roots = (allowed,)

    inside_result = executor.execute(
        {"tool": "write", "params": {"path": "allowed/inside.txt", "content": "ok"}}
    )
    outside_result = executor.execute(
        {"tool": "write", "params": {"path": "outside/escape.txt", "content": "no"}}
    )
    nested_result = executor.execute(
        {
            "tool": "use_tool",
            "params": {
                "tool_name": "write",
                "tool_input": {"path": "outside/nested.txt", "content": "no"},
            },
        }
    )

    assert "Error:" not in inside_result
    assert (allowed / "inside.txt").read_text() == "ok"
    assert "outside this agent's allowed write paths" in outside_result
    assert "outside this agent's allowed write paths" in nested_result
    assert not (outside / "escape.txt").exists()
    assert not (outside / "nested.txt").exists()


def test_scoped_child_treats_trailing_recursive_glob_as_directory(tmp_path: Path) -> None:
    project = tmp_path / "project"
    allowed = project / "src" / "world"
    allowed.mkdir(parents=True)
    executor = ExtendedToolExecutor(
        project_root=project,
        workspace_root=tmp_path / "workspace",
        protected_root=tmp_path / "protected",
        preview_manager=object(),
    )
    executor.mutation_scope_roots = (project / "src" / "world" / "**",)

    result = executor.execute(
        {
            "tool": "write",
            "params": {"path": "src/world/World.js", "content": "export {};\n"},
        }
    )

    assert "Error:" not in result
    assert (allowed / "World.js").is_file()


def test_scoped_child_write_rejects_symlink_escape(tmp_path: Path) -> None:
    project = tmp_path / "project"
    allowed = project / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir(parents=True)
    outside.mkdir()
    (allowed / "escape").symlink_to(outside, target_is_directory=True)
    executor = ExtendedToolExecutor(
        project_root=project,
        workspace_root=tmp_path / "workspace",
        protected_root=tmp_path / "protected",
        preview_manager=object(),
    )
    executor.mutation_scope_roots = (allowed,)

    result = executor.execute(
        {
            "tool": "write",
            "params": {"path": "allowed/escape/leak.txt", "content": "blocked"},
        }
    )

    assert "outside this agent's allowed write paths" in result
    assert not (outside / "leak.txt").exists()


def test_tool_inventory_exposes_executable_grok_compatible_surface(tmp_path: Path) -> None:
    executor = ExtendedToolExecutor(
        project_root=tmp_path,
        workspace_root=tmp_path / "workspace",
        preview_manager=object(),
    )
    names = {
        tool["function"]["name"] for tool in executor.get_available_tools()
    }

    assert {
        "list_dir",
        "web_search",
        "web_fetch",
        "todo_write",
        "memory_search",
        "memory_get",
        "get_task_output",
        "kill_task",
        "monitor",
        "search_tool",
        "use_tool",
        "wait_tasks",
        "scheduler_create",
        "scheduler_delete",
        "scheduler_list",
        "update_goal",
    }.issubset(names)
    assert "ask_user_question" not in names
    assert "ask_user_question" in executor.tools
    assert {"run_terminal_cmd", "read_file", "search_replace"}.isdisjoint(names)
    assert {"run_terminal_cmd", "read_file", "search_replace"}.issubset(
        executor.tools
    )

    started = json.loads(
        executor.execute(
            {
                "tool": "bash",
                "params": {"command": "printf ready", "is_background": True},
            }
        )
    )
    completed = json.loads(
        executor.execute(
            {
                "tool": "get_task_output",
                "params": {"task_ids": [started["task_id"]], "timeout_ms": 2000},
            }
        )
    )
    assert completed["results"][0]["status"] == "completed"
    assert completed["results"][0]["output"] == "ready"
