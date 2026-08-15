"""Tests for ToolLoopGuard result-success judgement."""
from agent.core.tool_loop_guard import ToolLoopGuard


def test_succeeded_success_status_is_authoritative():
    # 删除后的验证输出：正文含 "No such file or directory" 是预期结果，
    # 状态行是 ✓ Success，因此必须判定为成功。
    result = (
        "✓ Success\n"
        "Output:\n"
        "=== 删除后验证 ===\n"
        "ls: /Users/a/Library/Application Support/JCodex/workspace/output/study-room: "
        "No such file or directory\n"
        "grep_exit=1"
    )
    assert ToolLoopGuard._succeeded(result) is True


def test_succeeded_shell_failure_status():
    result = (
        "✗ Failed (exit code: 127)\n"
        "Error:\n"
        "/bin/sh: tial: command not found"
    )
    assert ToolLoopGuard._succeeded(result) is False


def test_succeeded_windows_cmd_failure():
    result = (
        "✗ Failed (exit code: 1)\n"
        "Error:\n"
        "'python3' 不是内部或外部命令，也不是可运行的程序\n"
        "或批处理文件。"
    )
    assert ToolLoopGuard._succeeded(result) is False


def test_succeeded_plain_success():
    assert ToolLoopGuard._succeeded("✓ Success\nOutput:\nhello") is True
    assert ToolLoopGuard._succeeded("Output: hello") is True


def test_succeeded_json_failure():
    assert ToolLoopGuard._succeeded('{"success": false, "error": "boom"}') is False


def test_embedded_failure_text_without_status_is_not_judged():
    # 内嵌失败文本不再参与判定：没有 ✗ 状态行/失败前缀时视为成功。
    assert ToolLoopGuard._succeeded("Error reading file: no such file or directory") is True
    assert ToolLoopGuard._succeeded("bash: rm: command not found") is True


def test_tool_error_prefix_still_failure():
    # 工具直接返回的 Error:/failed: 前缀错误仍然判失败。
    assert ToolLoopGuard._succeeded("Error: filePath parameter required") is False
    assert ToolLoopGuard._succeeded("failed: cannot write file") is False


# ── marker contract ─────────────────────────────────────────────────────────
# The shell tool now renders non-zero exits as `[exit code: N]` markers and
# reports timeouts/cancellations/signal kills with their own markers. Only
# Error:-style prefixes are infrastructure failures; markers are reports.


def test_marker_exit_code_nonzero_is_not_success():
    assert ToolLoopGuard._succeeded("hello\n[exit code: 1]") is False
    assert ToolLoopGuard._succeeded("Output:\n[exit code: 127]") is False


def test_marker_exit_code_zero_stays_success():
    # The renderer never emits [exit code: 0], but the parser is defensive.
    assert ToolLoopGuard._succeeded("hello\n[exit code: 0]") is True


def test_marker_timeout_is_not_success():
    assert ToolLoopGuard._succeeded("started\n[timed out after 30s]") is False


def test_marker_cancelled_is_not_success():
    assert ToolLoopGuard._succeeded("[cancelled]") is False


def test_marker_signal_kill_is_not_success():
    assert ToolLoopGuard._succeeded("output\n[killed by signal: SIGTERM]") is False


def test_marker_truncation_is_success():
    # Truncation is a report, not a failure: the full output is available at
    # the reported path.
    result = "data\n[output truncated; full output: /tmp/shell-abc.log]"
    assert ToolLoopGuard._succeeded(result) is True


def test_marker_embedded_failure_text_without_marker_stays_success():
    # The delete-verification guarantee under the new contract: body text like
    # "No such file or directory" never participates, only exact markers do.
    result = (
        "=== 删除后验证 ===\n"
        "ls: /Users/a/Library/Application Support/JCodex/workspace/output/study-room: "
        "No such file or directory\n"
        "grep_exit=1"
    )
    assert ToolLoopGuard._succeeded(result) is True


def test_marker_stderr_section_with_clean_exit_is_success():
    assert ToolLoopGuard._succeeded("warn\n[stderr]\nwarning: something") is True
