"""Desktop workspace tree regressions."""

import base64
import subprocess
import threading
from pathlib import Path

from agent.core.config_manager import ConfigManager
from agent.ui.desktop import main as desktop


def _data_url(content: bytes, mime_type: str = "text/plain") -> str:
    return (
        f"data:{mime_type};base64,"
        + base64.b64encode(content).decode("ascii")
    )


def test_workspace_listing_supports_nested_relative_paths(monkeypatch, tmp_path: Path) -> None:
    output_root = tmp_path / "workspace" / "output"
    nested_file = output_root / "reports" / "2026" / "result.csv"
    nested_file.parent.mkdir(parents=True)
    nested_file.write_text("value\n1\n", encoding="utf-8")
    (tmp_path / "workspace" / "temp").mkdir(parents=True)

    monkeypatch.setattr(desktop, "PROJECT_ROOT", tmp_path)

    root_items = desktop.list_workspace_files("output")
    assert any(
        item["name"] == "reports"
        and item["path"] == "reports"
        and item["type"] == "folder"
        for item in root_items
    )

    nested_items = desktop.list_workspace_files("output", "reports/2026")
    assert nested_items == [
        {
            "name": "result.csv",
            "path": "reports/2026/result.csv",
            "type": "file",
            "size": len("value\n1\n".encode("utf-8")),
            "modified": nested_file.stat().st_mtime,
        }
    ]
    assert desktop.list_workspace_files("output", "../temp") == []


def test_skill_folder_import_copies_nested_browser_selected_files(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(desktop, "PROJECT_ROOT", tmp_path)

    result = desktop.import_skill_folder(
        [
            {
                "path": "demo-skill/SKILL.md",
                "data": _data_url(b"---\nname: demo-skill\n---\n# Demo\n"),
            },
            {
                "path": "demo-skill/scripts/run.py",
                "data": _data_url(b"print('hello')\n", "text/x-python"),
            },
            {
                "path": "demo-skill/assets/icon.bin",
                "data": _data_url(b"\x00\xff", "application/octet-stream"),
            },
        ]
    )

    destination = tmp_path / "workspace" / "skills" / "demo-skill"
    assert result == {"success": True, "name": "demo-skill"}
    assert (destination / "SKILL.md").read_text(encoding="utf-8") == (
        "---\nname: demo-skill\n---\n# Demo\n"
    )
    assert (destination / "scripts" / "run.py").read_text(encoding="utf-8") == (
        "print('hello')\n"
    )
    assert (destination / "assets" / "icon.bin").read_bytes() == b"\x00\xff"


def test_skill_folder_import_rejects_traversal_and_existing_destination(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(desktop, "PROJECT_ROOT", tmp_path)
    files = [{"path": "demo/SKILL.md", "data": _data_url(b"# Demo")}]

    assert desktop.import_skill_folder(files)["success"] is True
    duplicate = desktop.import_skill_folder(files)
    assert duplicate == {
        "success": False,
        "error": "Skill 'demo' already exists",
    }

    rejected = desktop.import_skill_folder(
        [{"path": "demo/../outside/SKILL.md", "data": _data_url(b"# Nope")}]
    )
    assert rejected["success"] is False
    assert "Invalid skill folder path" in rejected["error"]
    assert not (tmp_path / "workspace" / "outside").exists()


def test_macos_project_folder_picker_uses_osascript(monkeypatch) -> None:
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, "/Users/test/My Project/\n", "")

    monkeypatch.setattr(desktop.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(desktop.subprocess, "run", fake_run)

    assert desktop._run_native_project_folder_picker() == "/Users/test/My Project/"
    assert captured["command"][0:2] == ["osascript", "-e"]
    assert "choose folder" in captured["command"][2]
    assert captured["kwargs"]["timeout"] == 10 * 60


def test_macos_project_folder_picker_treats_cancel_as_a_normal_result(
    monkeypatch,
) -> None:
    command = ["osascript", "-e", "choose folder"]

    monkeypatch.setattr(desktop.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(
        desktop.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            command,
            1,
            "",
            "execution error: User canceled. (-128)\n",
        ),
    )

    assert desktop.select_project_folder() == {
        "success": False,
        "path": "",
        "cancelled": True,
    }


def test_project_folder_picker_rejects_duplicate_requests(monkeypatch) -> None:
    monkeypatch.setattr(
        desktop,
        "_run_native_project_folder_picker",
        lambda: "/Users/test/project",
    )
    assert desktop._project_folder_picker_lock.acquire(blocking=False)
    try:
        assert desktop.select_project_folder() == {
            "success": False,
            "error": "目录选择器已经打开",
            "path": "",
        }
    finally:
        desktop._project_folder_picker_lock.release()


def test_project_folder_picker_runs_modal_dialog_outside_eel_thread(
    monkeypatch,
) -> None:
    caller_thread = threading.get_ident()
    picker_threads = []
    sleep_calls = []

    def fake_picker() -> str:
        picker_threads.append(threading.get_ident())
        return "/Users/test/project"

    monkeypatch.setattr(desktop, "_run_native_project_folder_picker", fake_picker)
    monkeypatch.setattr(desktop.eel, "sleep", lambda seconds: sleep_calls.append(seconds))

    assert desktop.select_project_folder() == {
        "success": True,
        "path": "/Users/test/project",
        "cancelled": False,
    }
    assert picker_threads and picker_threads[0] != caller_thread
    assert all(seconds == 0.05 for seconds in sleep_calls)


def test_reference_folder_picker_reuses_the_native_directory_picker(
    monkeypatch,
) -> None:
    expected = {
        "success": True,
        "path": "/Users/test/reference",
        "cancelled": False,
    }
    monkeypatch.setattr(desktop, "select_project_folder", lambda: expected)

    assert desktop.select_reference_folder() == expected


def test_loading_api_config_persists_selected_config_as_active(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    manager = ConfigManager()
    assert manager.add_config("first", "https://first.test", "key-1", "model-1")
    assert manager.add_config("second", "https://second.test", "key-2", "model-2")

    result = desktop.load_api_config("second")

    assert result["success"] is True
    assert result["active"] == "second"
    assert ConfigManager().list_configs()["active"] == "second"


def test_saving_api_config_makes_saved_config_active(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    manager = ConfigManager()
    assert manager.add_config("first", "https://first.test", "key-1", "model-1")

    result = desktop.save_api_config(
        "second", "https://second.test", "key-2", "model-2"
    )

    assert result == {"success": True, "active": "second"}
    reloaded = ConfigManager()
    assert reloaded.list_configs()["active"] == "second"
    assert reloaded.get_active_config()["api_model"] == "model-2"


def test_macos_dragged_folder_paths_are_filtered_by_directory_name(
    monkeypatch, tmp_path: Path
) -> None:
    requested = tmp_path / "requested-project"
    stale = tmp_path / "stale-project"
    requested.mkdir()
    stale.mkdir()

    monkeypatch.setattr(desktop.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(
        desktop.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            ["osascript"],
            0,
            f"{stale}\n{requested}\n",
            "",
        ),
    )

    assert desktop.get_dragged_folder_paths([requested.name]) == {
        "success": True,
        "paths": [str(requested)],
    }
