"""Desktop workspace tree regressions."""

import base64
import subprocess
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent.core.config_manager import ConfigManager
from agent.ui.desktop import main as desktop


def _use_tmp_workspace(monkeypatch, tmp_path) -> None:
    """Isolate both runtime roots so tests never touch the real repo/data dir."""
    monkeypatch.setattr(desktop, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(desktop, "DATA_ROOT", tmp_path)


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

    _use_tmp_workspace(monkeypatch, tmp_path)

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


def test_chat_media_resolver_allows_output_media_and_rejects_escapes(
    monkeypatch, tmp_path: Path
) -> None:
    output_root = tmp_path / "workspace" / "output"
    temp_root = tmp_path / "workspace" / "temp"
    output_root.mkdir(parents=True)
    temp_root.mkdir(parents=True)
    image_path = output_root / "result image.png"
    video_path = temp_root / "preview.mp4"
    outside_path = tmp_path / "private.png"
    image_path.write_bytes(b"png")
    video_path.write_bytes(b"video")
    outside_path.write_bytes(b"private")
    _use_tmp_workspace(monkeypatch, tmp_path)

    assert desktop._resolve_chat_media_file(str(image_path)) == (
        image_path,
        "image/png",
    )
    assert desktop._resolve_chat_media_file("workspace/temp/preview.mp4") == (
        video_path,
        "video/mp4",
    )
    # 绝对路径允许指向工作区之外，相对路径逃逸仍被拒绝
    assert desktop._resolve_chat_media_file(str(outside_path)) == (
        outside_path,
        "image/png",
    )
    with pytest.raises(ValueError, match="outside the active task"):
        desktop._resolve_chat_media_file("../../private.png")
    with pytest.raises(ValueError, match="Only local media paths"):
        desktop._resolve_chat_media_file("data:image/png;base64,AAAA")


def test_large_base64_media_is_redacted_before_persistence() -> None:
    payload = "data:image/png;base64," + ("A" * 512)

    redacted = desktop._redact_embedded_media_data(f"before {payload} after")

    assert redacted == (
        "before [已省略 Base64 媒体数据，请改用文件路径或 HTTP(S) 地址] after"
    )
    assert "base64," not in redacted


def test_skill_folder_import_copies_nested_browser_selected_files(
    monkeypatch, tmp_path: Path
) -> None:
    _use_tmp_workspace(monkeypatch, tmp_path)

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
    _use_tmp_workspace(monkeypatch, tmp_path)
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


def test_desktop_skill_list_uses_explicit_builtin_names(
    monkeypatch, tmp_path: Path
) -> None:
    _use_tmp_workspace(monkeypatch, tmp_path)

    agent_skills = tmp_path / "agent" / "skills"
    workspace_skills = tmp_path / "workspace" / "skills"
    for name in ("python", "web"):
        skill_dir = agent_skills / name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: {name} description\n---\n",
            encoding="utf-8",
        )
    for name in (desktop.BUILTIN_SKILL_NAMES - {"python"}) | {"custom-skill"}:
        skill_dir = workspace_skills / name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: {name} description\n---\n",
            encoding="utf-8",
        )

    listed = {skill["name"]: skill for skill in desktop.list_skills()}

    assert {
        name for name, skill in listed.items() if skill["builtin"]
    } == desktop.BUILTIN_SKILL_NAMES
    assert listed["web"]["builtin"] is False
    assert listed["custom-skill"]["builtin"] is False
    store_names = {skill["name"] for skill in desktop.list_skill_store()}
    assert store_names == {"custom-skill", "web"}
    assert (tmp_path / "workspace" / "skill-store" / "web" / "SKILL.md").exists()
    assert desktop.delete_skill("python") == {
        "success": False,
        "error": "Cannot delete built-in skill",
    }
    assert desktop.delete_skill("web") == {"success": True}
    assert not (agent_skills / "web").exists()
    assert (tmp_path / "workspace" / "skill-store" / "web" / "SKILL.md").exists()


def test_skill_store_install_delete_and_reinstall_preserves_catalog(
    monkeypatch, tmp_path: Path
) -> None:
    _use_tmp_workspace(monkeypatch, tmp_path)
    monkeypatch.delenv("SKILL_STORE_PATH", raising=False)
    store_skill = tmp_path / "workspace" / "skill-store" / "demo-store-skill"
    store_skill.mkdir(parents=True)
    (store_skill / "SKILL.md").write_text(
        "---\nname: demo-store-skill\ndescription: Store demo\n---\n# Demo\n",
        encoding="utf-8",
    )
    (store_skill / "scripts").mkdir()
    (store_skill / "scripts" / "run.py").write_text(
        "print('store copy')\n", encoding="utf-8"
    )

    assert desktop.list_skill_store() == [
        {
            "name": "demo-store-skill",
            "description": "Store demo",
            "installed": False,
            "builtin": False,
        }
    ]
    assert desktop.install_store_skill("demo-store-skill") == {
        "success": True,
        "name": "demo-store-skill",
    }
    installed = tmp_path / "workspace" / "skills" / "demo-store-skill"
    assert (installed / "scripts" / "run.py").read_text(encoding="utf-8") == (
        "print('store copy')\n"
    )
    assert desktop.list_skill_store()[0]["installed"] is True

    duplicate = desktop.install_store_skill("demo-store-skill")
    assert duplicate == {
        "success": False,
        "error": "Skill 'demo-store-skill' is already installed",
    }
    assert desktop.delete_skill("demo-store-skill") == {"success": True}
    assert not installed.exists()
    assert (store_skill / "SKILL.md").exists()
    assert desktop.list_skill_store()[0]["installed"] is False
    assert desktop.install_store_skill("demo-store-skill")["success"] is True
    assert desktop.install_store_skill("../demo")["success"] is False


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


def test_saving_local_api_config_allows_empty_api_key(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    manager = ConfigManager()

    result = desktop.save_api_config(
        "本地8080", "http://127.0.0.1:8080", "", "qwen"
    )

    assert result == {"success": True, "active": "本地8080"}
    reloaded = ConfigManager()
    assert reloaded.get_active_config() == {
        "api_base_url": "http://127.0.0.1:8080",
        "api_key": "",
        "api_model": "qwen",
    }


def test_set_active_config_applies_runtime_and_persists(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    manager = ConfigManager()
    assert manager.add_config("first", "https://first.test", "key-1", "model-1")
    assert manager.add_config("second", "https://second.test", "key-2", "model-2")

    written = []
    monkeypatch.setattr(
        desktop,
        "_write_env_file",
        lambda env_file, settings: written.append(settings),
    )
    monkeypatch.setattr(desktop, "load_dotenv", lambda *args, **kwargs: None)

    rebuilt = []

    class _FakeExecutor:
        def __init__(self, engine):
            self.ai_engine = engine

        def rebuild_langgraph_runner(self):
            rebuilt.append(self._name)

    os_agent_engine = SimpleNamespace()
    os_agent = _FakeExecutor(os_agent_engine)
    os_agent._name = "os_agent"
    monkeypatch.setattr(desktop, "os_agent", os_agent)

    conversation_engine = SimpleNamespace()
    conversation_executor = _FakeExecutor(conversation_engine)
    conversation_executor._name = "conversation"
    desktop.conversation_executors["switch-test"] = conversation_executor
    try:
        result = desktop.set_active_config("second")
    finally:
        desktop.conversation_executors.pop("switch-test", None)

    assert result["success"] is True
    assert result["active"] == "second"
    assert os_agent_engine.api_key == "key-2"
    assert os_agent_engine.api_base_url == "https://second.test"
    assert os_agent_engine.api_path == "/v1/chat/completions"
    assert os_agent_engine.model == "model-2"
    assert conversation_engine.model == "model-2"
    assert written == [
        {
            "api_base_url": "https://second.test",
            "api_key": "key-2",
            "api_model": "model-2",
        }
    ]
    assert "os_agent" in rebuilt
    assert "conversation" in rebuilt
    assert ConfigManager().list_configs()["active"] == "second"


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
