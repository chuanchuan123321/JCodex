"""Regression tests for managed local Web previews."""

import socket
from pathlib import Path

import pytest

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
        startup_timeout=5,
        conversation_id="test-conversation",
        message_id="2",
    )

    assert result["status"] == "ready"
    assert result["port"] == actual_port


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
