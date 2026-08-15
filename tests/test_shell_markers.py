"""Marker contract tests for the shell tool.

Covers the model-facing result contract: non-zero exits are reported as
`[exit code: N]` (never `✗ Failed`), timeouts/cancellations/signal kills get
their own markers, output truncation spills to a file, and Windows cmd/pwsh
output decodes through the UTF-8 -> GBK -> Latin-1 fallback chain.

These tests import only the standard library, so they run without the
project's LangChain dependencies (and on Python 3.9 for local verification).
"""
from __future__ import annotations

import os
import tempfile

from agent.tools.shell import CommandResult, ShellTool, decode_stream


def test_decode_stream_utf8():
    assert decode_stream("你好".encode("utf-8")) == "你好"
    assert decode_stream(b"") == ""


def test_decode_stream_gbk_fallback():
    # 你好 in GBK is not valid UTF-8, so the chain falls back to GBK.
    assert decode_stream(b"\xc4\xe3\xba\xc3") == "你好"


def test_command_result_positional_compatibility():
    # Historical callers construct CommandResult(returncode, stdout, stderr, success).
    result = CommandResult(0, "out", "err", True)
    assert result.timed_out is False
    assert result.cancelled is False
    assert result.signal is None
    assert result.truncated is False
    assert result.spill_path is None
    assert result.success is True


def test_format_result_clean_exit_has_no_markers():
    result = CommandResult(0, "hello\n", "", True)
    rendered = ShellTool().format_result(result)
    assert rendered == "hello\n"
    assert "[exit code:" not in rendered


def test_format_result_nonzero_exit_marker():
    result = CommandResult(3, "output\n", "", False)
    rendered = ShellTool().format_result(result)
    assert rendered.endswith("[exit code: 3]")
    assert "✗" not in rendered


def test_format_result_stderr_section():
    result = CommandResult(0, "out", "oops", True)
    rendered = ShellTool().format_result(result)
    assert rendered == "out\n[stderr]\noops"


def test_format_result_cancelled_marker():
    result = CommandResult(130, "", "Command cancelled", False, cancelled=True)
    rendered = ShellTool().format_result(result)
    assert rendered.endswith("[cancelled]")


def test_format_result_timeout_marker():
    result = CommandResult(
        124, "", "Command timeout (30s)", False, timed_out=True, timeout_s=30.0
    )
    rendered = ShellTool().format_result(result)
    assert rendered.endswith("[timed out after 30s]")


def test_format_result_signal_marker():
    result = CommandResult(-15, "", "", False, signal="SIGTERM")
    rendered = ShellTool().format_result(result)
    assert rendered.endswith("[killed by signal: SIGTERM]")


def test_format_result_truncation_reports_spill_path():
    result = CommandResult(
        0,
        "x" * 6000,
        "",
        True,
        truncated=True,
        spill_path="/tmp/shell-abc.log",
    )
    rendered = ShellTool().format_result(result)
    assert "[output truncated; full output: /tmp/shell-abc.log]" in rendered


def test_execute_echo_success():
    result = ShellTool().execute("echo hello")
    assert result.success is True
    assert result.stdout == "hello\n"
    assert "[exit code:" not in ShellTool().format_result(result)


def test_execute_nonzero_exit_is_a_report():
    result = ShellTool().execute("exit 3")
    assert result.success is False
    assert result.returncode == 3
    assert ShellTool().format_result(result).endswith("[exit code: 3]")


def test_execute_signal_kill_reports_signal_name():
    if os.name != "posix":
        return
    result = ShellTool().execute("kill -TERM $$")
    assert result.success is False
    assert result.signal == "SIGTERM"
    assert ShellTool().format_result(result).endswith("[killed by signal: SIGTERM]")


def test_execute_timeout_reports_marker():
    result = ShellTool().execute("sleep 5", timeout=0.3)
    assert result.timed_out is True
    assert result.success is False
    assert ShellTool().format_result(result).endswith("[timed out after 0.3s]")


def test_execute_truncation_spills_full_output():
    with tempfile.TemporaryDirectory() as tmp:
        tool = ShellTool(max_output_length=10, spill_dir=tmp)
        result = tool.execute("printf '1234567890ABCDEFGHIJ'")
        assert result.truncated is True
        assert result.spill_path
        assert os.path.exists(result.spill_path)
        rendered = tool.format_result(result)
        assert f"[output truncated; full output: {result.spill_path}]" in rendered
        with open(result.spill_path, encoding="utf-8") as fh:
            assert "ABCDEFGHIJ" in fh.read()


def test_execute_pwsh_unavailable_is_an_error():
    if ShellTool._resolve_pwsh() is not None:
        return  # PowerShell installed: dialect runs for real elsewhere
    result = ShellTool().execute("Get-Date", dialect="pwsh")
    assert result.success is False
    assert result.infrastructure is True
    assert "PowerShell" in result.stderr
    assert result.stderr.startswith("Error:")
    # Infrastructure failures render as a plain Error: with no exit markers.
    rendered = ShellTool().format_result(result)
    assert rendered.startswith("Error:")
    assert "[exit code:" not in rendered
    assert "[stderr]" not in rendered


def test_format_result_infrastructure_failure_is_plain_error():
    result = CommandResult(
        1,
        "",
        "Error: failed to start command: boom",
        False,
        infrastructure=True,
    )
    rendered = ShellTool().format_result(result)
    assert rendered == "Error: failed to start command: boom"
    assert "[exit code:" not in rendered
    assert "[stderr]" not in rendered
    assert "(no output)" not in rendered


def test_pwsh_dialect_runs_when_available():
    if ShellTool._resolve_pwsh() is None:
        return
    result = ShellTool().execute("Write-Output hi", dialect="pwsh")
    assert result.success is True


if __name__ == "__main__":
    # Minimal runner so the pure-stdlib suite can be verified without pytest.
    import sys
    import traceback

    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except Exception:
                failures += 1
                print(f"FAIL {name}")
                traceback.print_exc()
    sys.exit(1 if failures else 0)
