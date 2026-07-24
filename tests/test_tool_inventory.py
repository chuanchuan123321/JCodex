"""Regression coverage for the consolidated local tool inventory."""

import json
from pathlib import Path

from agent.core.extended_tool_executor import ExtendedToolExecutor


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
        "ask_user_question",
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
