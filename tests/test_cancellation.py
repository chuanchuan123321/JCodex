"""Cancellation regressions for model streaming and command execution."""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
import threading
import time

import pytest
from langchain_core.messages import HumanMessage

from agent.core.extended_tool_executor import ExtendedToolExecutor
from agent.core.langchain_model import AIEngineChatModel
from agent.tools.shell import CommandResult, ShellTool


def test_silent_model_stream_stops_without_waiting_for_transport() -> None:
    transport_started = threading.Event()
    release_transport = threading.Event()
    cancel_event = threading.Event()

    class SilentEngine:
        model = "fake"
        max_tokens = 100
        temperature = 0.0
        api_base_url = "http://fake"

        def _post_chat_completion_stream(self, *args, **kwargs):
            transport_started.set()
            release_transport.wait(timeout=3)
            return {"content": "late", "tool_calls": [], "finish_reason": "stop"}

        def call_messages(self, *args, **kwargs):
            return {"content": "late", "tool_calls": [], "finish_reason": "stop"}

    model = AIEngineChatModel(engine=SilentEngine())
    consumed: list[object] = []

    def consume() -> None:
        with model.cancellation_scope(cancel_event.is_set):
            consumed.extend(model._stream([HumanMessage(content="hello")]))

    consumer = threading.Thread(target=consume)
    consumer.start()
    assert transport_started.wait(timeout=1)

    started = time.monotonic()
    cancel_event.set()
    consumer.join(timeout=0.4)
    elapsed = time.monotonic() - started
    release_transport.set()

    assert not consumer.is_alive()
    assert elapsed < 0.3
    assert consumed == []


@pytest.mark.skipif(os.name != "posix", reason="process-group assertion is POSIX-only")
def test_shell_cancellation_terminates_command_process_group(tmp_path) -> None:
    child_pid_path = tmp_path / "child.pid"
    script = (
        "import pathlib, subprocess, sys, time; "
        "child = subprocess.Popen([sys.executable, '-c', "
        "'import time; time.sleep(30)']); "
        "pathlib.Path(sys.argv[1]).write_text(str(child.pid)); "
        "print('started', flush=True); time.sleep(30)"
    )
    command = " ".join(
        (
            shlex.quote(sys.executable),
            "-c",
            shlex.quote(script),
            shlex.quote(str(child_pid_path)),
        )
    )
    cancel_event = threading.Event()
    results: list[CommandResult] = []

    worker = threading.Thread(
        target=lambda: results.append(
            ShellTool().execute(command, timeout=10, cancel_event=cancel_event)
        )
    )
    worker.start()
    deadline = time.monotonic() + 2
    while not child_pid_path.exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert child_pid_path.exists()
    child_pid = int(child_pid_path.read_text())

    started = time.monotonic()
    cancel_event.set()
    worker.join(timeout=1)

    assert not worker.is_alive()
    assert time.monotonic() - started < 0.8
    assert results[0].returncode == 130
    assert results[0].success is False
    assert "Command cancelled" in results[0].stderr

    deadline = time.monotonic() + 1
    while _process_is_running(child_pid) and time.monotonic() < deadline:
        time.sleep(0.02)
    assert not _process_is_running(child_pid)


def test_extended_executor_passes_runtime_cancellation_to_shell() -> None:
    captured: dict[str, object] = {}

    class RecordingShell:
        def execute(self, command: str, **kwargs) -> CommandResult:
            captured.update(kwargs)
            return CommandResult(0, command, "", True)

        @staticmethod
        def format_result(result: CommandResult) -> str:
            return result.stdout

    executor = object.__new__(ExtendedToolExecutor)
    executor.shell_tool = RecordingShell()
    executor.tools = {"bash": executor.execute_shell}
    cancel_event = threading.Event()
    checker = cancel_event.is_set

    result = executor.execute(
        {"tool": "bash", "params": {"command": "echo ok"}},
        runtime={"cancel_event": cancel_event, "cancelled": checker},
    )

    assert result == "echo ok"
    assert captured["cancel_event"] is cancel_event
    assert captured["cancelled"] is checker


@pytest.mark.skipif(os.name == "nt", reason="rm behavior is POSIX-only")
def test_shell_does_not_block_an_approved_rm_command(tmp_path) -> None:
    target = tmp_path / "removable"
    target.mkdir()
    (target / "file.txt").write_text("remove me")

    result = ShellTool().execute(f"rm -rf {shlex.quote(str(target))}")

    assert result.success is True
    assert not target.exists()


def _process_is_running(pid: int) -> bool:
    result = subprocess.run(
        ["ps", "-o", "stat=", "-p", str(pid)],
        capture_output=True,
        text=True,
        check=False,
    )
    status = result.stdout.strip()
    return bool(status and not status.startswith("Z"))
