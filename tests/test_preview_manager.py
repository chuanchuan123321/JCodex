"""Regression tests for managed local Web previews."""

import json
import os as native_os
import socket
from types import SimpleNamespace

import pytest

import agent.tools.preview as preview_module
from agent.core.extended_tool_executor import ExtendedToolExecutor
from agent.tools.preview import PreviewManager


@pytest.fixture
def preview_manager(tmp_path):
    (tmp_path / "workspace" / "output").mkdir(parents=True)
    manager = PreviewManager(tmp_path, log_dir=tmp_path / "preview-logs")
    try:
        yield manager
    finally:
        manager.stop_all()


@pytest.mark.parametrize(
    "command",
    [
        'echo "Serving HTML file" && python3 -m http.server 8080',
        "python3 -m http.server $PORT",
        "python3 -m http.server $PORT --bind 127.0.0.1",
        'python3 -m http.server "$PORT" --bind "$HOST"',
        "python3 -m http.server '$PORT' --bind '$HOST'",
        "python3 -m http.server ${PORT}",
    ],
)
def test_python_http_server_commands_are_normalized(preview_manager, command):
    result = preview_manager.start(
        command=command,
        workdir="workspace/output",
        name="static-site",
        startup_timeout=5,
        conversation_id="test-conversation",
        message_id="1",
    )

    assert result["status"] == "ready"
    record = preview_manager._previews[result["preview_id"]]
    assert 'http.server "$PORT" --bind "$HOST"' in record.command


def test_http_server_option_values_are_not_treated_as_ports():
    normalized = PreviewManager._normalize_command(
        "python3 -m http.server --directory 8080"
    )

    assert normalized.endswith("--directory 8080")


def test_http_server_redirection_is_preserved():
    command = "python3 -m http.server 8080 > server.log"

    assert PreviewManager._normalize_command(command) == command


def test_discovers_one_loopback_listener_owned_by_preview(preview_manager):
    output_dir = preview_manager.project_root / "workspace" / "output"
    nested_page = output_dir / "nested" / "demo.html"
    nested_page.parent.mkdir()
    nested_page.write_text("<h1>Nested page</h1>", encoding="utf-8")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        actual_port = sock.getsockname()[1]
    command = (
        "python3 -c 'import http.server; "
        f"http.server.ThreadingHTTPServer((\"127.0.0.1\", {actual_port}), "
        "http.server.SimpleHTTPRequestHandler).serve_forever()'"
    )

    result = preview_manager.start(
        command=command,
        workdir="workspace/output",
        entry_path="/nested/demo.html",
        startup_timeout=5,
        conversation_id="test-conversation",
        message_id="2",
    )

    assert result["status"] == "ready"
    assert result["port"] == actual_port
    assert result["entry_path"] == "/nested/demo.html"
    assert result["url"].endswith("/nested/demo.html")


def test_clear_conversation_stops_and_forgets_preview(preview_manager):
    result = preview_manager.start(
        command="python3 -m http.server $PORT",
        workdir="workspace/output",
        startup_timeout=5,
        conversation_id="clear-preview-conversation",
        message_id="4",
    )
    preview_id = result["preview_id"]

    cleared = preview_manager.clear_conversation("clear-preview-conversation")
    remaining = preview_manager.status(
        conversation_id="clear-preview-conversation"
    )

    assert preview_id in cleared["cleared"]
    assert preview_id not in preview_manager._previews
    assert remaining["previews"] == []


def test_rejects_non_loopback_binding(preview_manager):
    result = preview_manager.start(
        command="python3 -m http.server 8080 --bind 0.0.0.0",
        workdir="workspace/output",
        startup_timeout=2,
        conversation_id="test-conversation",
        message_id="3",
    )

    assert result["status"] == "error"
    assert "127.0.0.1" in result["error"]


def test_preview_accepts_an_absolute_workdir_outside_the_task_root(
    preview_manager, tmp_path
):
    external_site = tmp_path.parent / f"{tmp_path.name}-external-site"
    external_site.mkdir()
    (external_site / "index.html").write_text(
        "<h1>External preview</h1>", encoding="utf-8"
    )
    try:
        result = preview_manager.start(
            command="python3 -m http.server $PORT",
            workdir=str(external_site),
            startup_timeout=5,
            conversation_id="external-preview",
            message_id="outside-root",
        )

        assert result["status"] == "ready"
        assert result["workdir"] == str(external_site.resolve())
        assert result["url"].startswith("http://127.0.0.1:")
    finally:
        preview_manager.stop_all()
        (external_site / "index.html").unlink()
        external_site.rmdir()


def test_static_preview_auto_selects_a_single_root_html_file(preview_manager):
    output_dir = preview_manager.project_root / "workspace" / "output"
    (output_dir / "kylin-agent.html").write_text(
        "<h1>Kylin Agent</h1>", encoding="utf-8"
    )

    result = preview_manager.start(
        command="python3 -m http.server $PORT",
        workdir="workspace/output",
        startup_timeout=5,
        conversation_id="entry-conversation",
        message_id="single-file",
    )

    assert result["status"] == "ready"
    assert result["entry_path"] == "/kylin-agent.html"
    assert result["url"].endswith("/kylin-agent.html")


def test_static_preview_accepts_an_explicit_nested_entry_path(preview_manager):
    output_dir = preview_manager.project_root / "workspace" / "output"
    nested_page = output_dir / "pages" / "demo.html"
    nested_page.parent.mkdir()
    nested_page.write_text("<h1>Demo</h1>", encoding="utf-8")

    result = preview_manager.start(
        command="python3 -m http.server $PORT",
        workdir="workspace/output",
        entry_path="pages/demo.html",
        startup_timeout=5,
        conversation_id="entry-conversation",
        message_id="nested-file",
    )

    assert result["status"] == "ready"
    assert result["entry_path"] == "/pages/demo.html"
    assert result["url"].endswith("/pages/demo.html")


@pytest.mark.parametrize(
    "entry_path",
    [
        "../outside.html",
        "/%2e%2e/outside.html",
        "/%252e%252e/outside.html",
        "/%5coutside.html",
        "https://example.com/page",
    ],
)
def test_preview_rejects_invalid_entry_paths(preview_manager, entry_path):
    result = preview_manager.start(
        command="python3 -m http.server $PORT",
        workdir="workspace/output",
        entry_path=entry_path,
        conversation_id="entry-conversation",
        message_id="invalid-path",
    )

    assert result["status"] == "error"
    assert "entry_path" in result["error"]


def test_reused_preview_updates_its_entry_url(preview_manager):
    output_dir = preview_manager.project_root / "workspace" / "output"
    (output_dir / "first.html").write_text("<h1>First</h1>", encoding="utf-8")
    (output_dir / "second.html").write_text("<h1>Second</h1>", encoding="utf-8")
    first = preview_manager.start(
        command="python3 -m http.server $PORT",
        workdir="workspace/output",
        entry_path="/first.html",
        startup_timeout=5,
        conversation_id="reuse-conversation",
        message_id="first-message",
    )
    second = preview_manager.start(
        command="python3 -m http.server $PORT",
        workdir="workspace/output",
        entry_path="/second.html",
        startup_timeout=5,
        conversation_id="reuse-conversation",
        message_id="second-message",
    )

    assert first["status"] == "ready"
    assert second["reused"] is True
    assert second["preview_id"] == first["preview_id"]
    assert second["entry_path"] == "/second.html"
    assert second["url"].endswith("/second.html")


def test_entry_path_encodes_literal_percent_characters():
    assert PreviewManager._validate_entry_path("100%real.html") == "/100%25real.html"


def test_project_preview_schema_and_executor_forward_entry_path(tmp_path):
    class PreviewSpy:
        def __init__(self):
            self.start_params = None

        def start(self, **params):
            self.start_params = params
            return {"success": True, "status": "ready", "url": "http://127.0.0.1/"}

    preview_manager_spy = PreviewSpy()
    executor = ExtendedToolExecutor(
        project_root=str(tmp_path), preview_manager=preview_manager_spy
    )
    schema = next(
        tool["function"]
        for tool in executor.get_available_tools()
        if tool.get("function", {}).get("name") == "project_preview"
    )
    result = executor.execute(
        {
            "tool": "project_preview",
            "params": {
                "action": "start",
                "command": "python3 -m http.server $PORT",
                "entry_path": "/nested/demo.html",
            },
        }
    )

    assert "entry_path" in schema["parameters"]["properties"]
    assert "proactively call action=start" in schema["description"]
    assert json.loads(result)["status"] == "ready"
    assert preview_manager_spy.start_params["entry_path"] == "/nested/demo.html"


class _WindowsOS:
    """Expose the host OS except for the platform branch under test."""

    name = "nt"

    def __getattr__(self, attribute):
        return getattr(native_os, attribute)


def test_windows_preview_launch_uses_cmd_variables_and_process_group(
    preview_manager, monkeypatch
):
    class FakeProcess:
        pid = 12345
        stdout = None
        returncode = None

        def poll(self):
            return None

        def terminate(self):
            self.returncode = 0

        def kill(self):
            self.returncode = 0

        def wait(self, timeout=None):
            self.returncode = 0
            return 0

    launched = {}

    def fake_popen(command, **kwargs):
        launched["command"] = command
        launched["kwargs"] = kwargs
        return FakeProcess()

    def mark_ready(record):
        record.status = "ready"
        record.state_event.set()

    class ImmediateThread:
        def __init__(self, target, args, **kwargs):
            self.target = target
            self.args = args

        def start(self):
            self.target(*self.args)

    monkeypatch.setattr(preview_module, "os", _WindowsOS())
    monkeypatch.setattr(preview_module.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(
        preview_module.subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200, raising=False
    )
    monkeypatch.setattr(preview_manager, "_capture_output", lambda record: None)
    monkeypatch.setattr(preview_manager, "_monitor", mark_ready)
    monkeypatch.setattr(preview_module.threading, "Thread", ImmediateThread)

    result = preview_manager.start(
        command="npx vite --host $HOST --port ${PORT}",
        workdir="workspace/output",
        startup_timeout=1,
    )

    assert result["status"] == "ready"
    assert launched["command"] == "npx vite --host %HOST% --port %PORT%"
    assert launched["kwargs"]["shell"] is True
    assert launched["kwargs"]["creationflags"] & 0x200
    assert "start_new_session" not in launched["kwargs"]
    assert launched["kwargs"]["env"]["HOST"] == "127.0.0.1"
    assert launched["kwargs"]["env"]["PORT"] == str(result["port"])
    record = preview_manager._previews[result["preview_id"]]
    record.status = "stopped"


def test_windows_static_preview_uses_embedded_python_runtime(monkeypatch):
    monkeypatch.setattr(PreviewManager, "_is_windows", classmethod(lambda cls: True))
    monkeypatch.setattr(
        preview_module.sys,
        "executable",
        r"C:\Program Files\Minibot\python.exe",
    )

    normalized = PreviewManager._normalize_command("python3 -m http.server $PORT")
    command = PreviewManager._prepare_launch_command(normalized)

    assert "python3" not in command.lower()
    assert "python.exe" in command.lower()
    assert "%PORT%" in command
    assert "%HOST%" in command


@pytest.mark.parametrize(
    "command",
    [
        'python3 -m http.server "$PORT" --bind "$HOST"',
        "python3 -m http.server '$PORT' --bind '$HOST'",
        "python3 -m http.server %PORT% --bind %HOST%",
    ],
)
def test_windows_static_preview_normalizes_variable_quote_styles(monkeypatch, command):
    monkeypatch.setattr(PreviewManager, "_is_windows", classmethod(lambda cls: True))

    normalized = PreviewManager._normalize_command(command)

    assert normalized == 'python3 -m http.server "%PORT%" --bind "%HOST%"'


def test_windows_listener_inspection_detects_loopback_and_external_bindings(
    preview_manager, monkeypatch
):
    class Process:
        pid = 99

        @staticmethod
        def poll():
            return None

    record = SimpleNamespace(process=Process(), managed_processes={})

    class OwnedProcess:
        pid = 99

        @staticmethod
        def children(recursive):
            return []

        @staticmethod
        def net_connections(kind):
            return [
                SimpleNamespace(
                    status="LISTEN",
                    laddr=SimpleNamespace(ip="127.0.0.1", port=5173),
                )
            ]

    fake_psutil = SimpleNamespace(
        Error=Exception,
        CONN_LISTEN="LISTEN",
        Process=lambda pid: OwnedProcess(),
    )
    monkeypatch.setattr(preview_module, "psutil", fake_psutil)
    monkeypatch.setattr(PreviewManager, "_is_windows", classmethod(lambda cls: True))

    endpoints, unsafe = preview_manager._process_group_listener_endpoints(record)

    assert endpoints == {("127.0.0.1", 5173)}
    assert unsafe is False

    OwnedProcess.net_connections = staticmethod(
        lambda kind: [
            SimpleNamespace(
                status="LISTEN",
                laddr=SimpleNamespace(ip="0.0.0.0", port=5173),
            )
        ]
    )
    endpoints, unsafe = preview_manager._process_group_listener_endpoints(record)

    assert endpoints == set()
    assert unsafe is True


def test_windows_listener_inspection_fails_closed_when_process_cannot_be_read(
    preview_manager, monkeypatch
):
    class Process:
        pid = 99

        @staticmethod
        def poll():
            return None

    record = SimpleNamespace(process=Process(), managed_processes={})
    fake_psutil = SimpleNamespace(
        Error=RuntimeError,
        CONN_LISTEN="LISTEN",
        Process=lambda pid: (_ for _ in ()).throw(RuntimeError("access denied")),
    )
    monkeypatch.setattr(preview_module, "psutil", fake_psutil)
    monkeypatch.setattr(PreviewManager, "_is_windows", classmethod(lambda cls: True))

    endpoints, unsafe = preview_manager._process_group_listener_endpoints(record)

    assert endpoints is None
    assert unsafe is True


def test_monitor_uses_the_owned_port_when_the_requested_port_is_taken(
    preview_manager, monkeypatch
):
    class Process:
        pid = 100

        @staticmethod
        def poll():
            return None

        @staticmethod
        def wait():
            return 0

        @staticmethod
        def terminate():
            return None

        @staticmethod
        def kill():
            return None

    result = preview_manager.start(
        command="python3 -m http.server $PORT",
        workdir="workspace/output",
        startup_timeout=1,
    )
    record = preview_manager._previews[result["preview_id"]]
    preview_manager.stop(result["preview_id"])
    record.process = Process()
    record.status = "starting"
    record.state_event.clear()
    record.port = 5173
    record.url = preview_manager._format_url(record.host, record.port)

    monkeypatch.setattr(preview_manager, "_http_reachable", lambda value: True)
    monkeypatch.setattr(
        preview_manager,
        "_process_group_listener_endpoints",
        lambda value: ({("127.0.0.1", 5180)}, False),
    )
    monkeypatch.setattr(
        preview_manager,
        "_watch_running_process",
        lambda value: None,
    )

    preview_manager._monitor(record)

    assert record.status == "ready"
    assert record.port == 5180
    assert record.url.endswith(":5180/")
    record.status = "stopped"


def test_windows_stop_kills_observed_processes_without_posix_signals(
    preview_manager, monkeypatch
):
    class Process:
        pid = 100
        returncode = None

        @staticmethod
        def poll():
            return None

        def wait(self, timeout):
            self.returncode = 0
            return 0

        @staticmethod
        def kill():
            raise AssertionError("taskkill should be used")

    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0)

    record = SimpleNamespace(
        process=Process(),
        managed_processes={100: 0.0, 101: 0.0},
    )
    monkeypatch.setattr(preview_module.subprocess, "run", fake_run)

    preview_manager._terminate_windows_process_tree(record)

    assert ["taskkill", "/PID", "100", "/T", "/F"] in calls
    assert ["taskkill", "/PID", "101", "/T", "/F"] in calls
