"""Shell execution tool.

Model-facing contract:

- Each call runs in a fresh shell: no state (cwd, variables, functions)
  persists between calls.
- Non-zero exits are REPORTED as ``[exit code: N]`` markers, never presented
  as tool errors. Timeouts, cancellations, and signal kills get their own
  markers (``[timed out after Ns]``, ``[cancelled]``,
  ``[killed by signal: X]``). Only infrastructure failures use ``Error:``.
- Truncated output is spilled to a file and the path is reported in a
  ``[output truncated; full output: <path>]`` marker instead of being dropped
  silently.
- Output bytes are decoded with a UTF-8 -> GBK -> Latin-1 fallback chain so
  Windows cmd/PowerShell output (often cp936 on Chinese systems) survives.
"""

from __future__ import annotations

import os
import signal
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Tuple


def decode_stream(raw: bytes) -> str:
    """Decode command output bytes with a UTF-8 -> GBK -> Latin-1 fallback chain."""
    if not raw:
        return ""
    for encoding in ("utf-8", "gbk", "latin-1"):
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


@dataclass
class CommandResult:
    """Result of command execution.

    The first four fields are positional-compatible with historical callers;
    the outcome facts are defaulted keyword fields appended last.
    """

    returncode: int
    stdout: str
    stderr: str
    success: bool
    # Outcome facts (marker contract). `signal` is the terminating signal
    # name (e.g. "SIGTERM") when the process was signal-killed on POSIX.
    timed_out: bool = False
    cancelled: bool = False
    signal: Optional[str] = None
    truncated: bool = False
    spill_path: Optional[str] = None
    timeout_s: Optional[float] = None
    # True for infrastructure failures (spawn errors, missing tooling) that the
    # model must treat as harness errors, not as command reports. Rendered as a
    # plain `Error:` result with no exit/timeout markers.
    infrastructure: bool = False


class ShellTool:
    """Tool for executing shell commands"""

    def __init__(
        self,
        max_output_length: int = 5000,
        spill_dir: Optional[str] = None,
    ):
        self.max_output_length = max_output_length
        # Where truncated full output is spilled so the model can read the tail
        # that was cut. Defaults to the system temp directory.
        self.spill_dir = spill_dir
        self.last_result: Optional[CommandResult] = None

    def execute(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: Optional[float] = None,
        cancel_event: Optional[object] = None,
        cancelled: Optional[Callable[[], bool]] = None,
        dialect: str = "system",
    ) -> CommandResult:
        """Execute a shell command and stop its process group on cancellation.

        Args:
            command: Command text to execute.
            cwd: Working directory (defaults to the current directory).
            timeout: Timeout in seconds (defaults to 30.0).
            cancel_event / cancelled: Cancellation signal sources.
            dialect: ``"system"`` runs through the platform shell
                (``cmd.exe`` on Windows, ``sh`` on POSIX); ``"pwsh"`` runs the
                command through ``pwsh -NoProfile -NonInteractive -Command``
                (falling back to ``powershell``) with no intermediate shell.
        """
        if self._is_cancelled(cancel_event, cancelled):
            return self._remember(CommandResult(
                returncode=130,
                stdout="",
                stderr="Command cancelled",
                success=False,
                cancelled=True,
            ))

        popen_options: dict = {}
        if os.name == "posix":
            popen_options["start_new_session"] = True
        elif os.name == "nt":
            # 独立进程组便于整体终止；CREATE_NO_WINDOW 阻止 GUI 宿主（桌面应用）
            # 启动 pwsh/cmd 时弹出新的控制台窗口。
            popen_options["creationflags"] = (
                subprocess.CREATE_NEW_PROCESS_GROUP
                | getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )
        args: object = command
        if dialect == "pwsh":
            pwsh = self._resolve_pwsh()
            if pwsh is None:
                return self._remember(CommandResult(
                    returncode=1,
                    stdout="",
                    stderr=(
                        "Error: PowerShell (pwsh or powershell) was not found on "
                        "PATH; the pwsh tool requires it. Install PowerShell or "
                        "use the legacy bash tool with cmd.exe commands."
                    ),
                    success=False,
                    infrastructure=True,
                ))
            args = [pwsh, "-NoProfile", "-NonInteractive", "-Command", command]

        try:
            process = subprocess.Popen(
                args,
                shell=(dialect != "pwsh"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=cwd or os.getcwd(),
                **popen_options,
            )
        except Exception as e:
            return self._remember(CommandResult(
                returncode=1,
                stdout="",
                stderr=f"Error: failed to start command: {e}",
                success=False,
                infrastructure=True,
            ))

        effective_timeout = float(timeout) if timeout else 30.0
        deadline = time.monotonic() + effective_timeout
        raw_stdout = b""
        raw_stderr = b""
        cancelled_flag = False
        timed_out_flag = False

        while True:
            if self._is_cancelled(cancel_event, cancelled):
                cancelled_flag = True
                self._terminate_process_group(process)
                raw_stdout, raw_stderr = self._collect_output(process)
                break

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out_flag = True
                self._terminate_process_group(process)
                raw_stdout, raw_stderr = self._collect_output(process)
                break

            try:
                raw_stdout, raw_stderr = process.communicate(timeout=min(0.05, remaining))
                break
            except subprocess.TimeoutExpired:
                continue

        stdout = decode_stream(raw_stdout)
        stderr = decode_stream(raw_stderr)
        returncode = process.returncode if process.returncode is not None else 1

        if cancelled_flag:
            result = CommandResult(
                returncode=130,
                stdout=stdout,
                stderr=self._with_reason(stderr, "Command cancelled"),
                success=False,
                cancelled=True,
                timeout_s=effective_timeout,
            )
        elif timed_out_flag:
            result = CommandResult(
                returncode=124,
                stdout=stdout,
                stderr=self._with_reason(
                    stderr, f"Command timeout ({effective_timeout:g}s)"
                ),
                success=False,
                timed_out=True,
                timeout_s=effective_timeout,
            )
        else:
            sig_name: Optional[str] = None
            if os.name == "posix" and returncode < 0:
                sig_name = self._signal_name(-returncode)
            result = CommandResult(
                returncode=returncode,
                stdout=stdout,
                stderr=stderr,
                success=returncode == 0,
                signal=sig_name,
                timeout_s=effective_timeout,
            )

        return self._remember(self._finalize(result))

    @staticmethod
    def _resolve_pwsh() -> Optional[str]:
        """Resolve the PowerShell executable (pwsh preferred, powershell fallback)."""
        import shutil

        for name in ("pwsh", "powershell"):
            path = shutil.which(name)
            if path:
                return path
        return None

    @staticmethod
    def _signal_name(signum: int) -> str:
        """Map a POSIX signal number to its name (e.g. 15 -> 'SIGTERM')."""
        try:
            return signal.Signals(signum).name
        except (ValueError, AttributeError):
            return f"signal {signum}"

    def _finalize(self, result: CommandResult) -> CommandResult:
        """Apply output truncation, spilling the full text when cut."""
        if len(result.stdout) <= self.max_output_length and len(result.stderr) <= self.max_output_length:
            return result
        full = "=== stdout ===\n" + result.stdout + "\n=== stderr ===\n" + result.stderr
        spill_path = self._write_spill(full)
        result.stdout = result.stdout[: self.max_output_length]
        result.stderr = result.stderr[: self.max_output_length]
        result.truncated = True
        result.spill_path = spill_path or None
        return result

    def _write_spill(self, text: str) -> str:
        """Persist full output next to the truncated result; '' when unwritable."""
        directory = Path(self.spill_dir) if self.spill_dir else Path(tempfile.gettempdir())
        try:
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / f"shell-{uuid.uuid4().hex[:12]}.log"
            path.write_text(text, encoding="utf-8", errors="replace")
            return str(path)
        except OSError:
            return ""

    @staticmethod
    def _is_cancelled(
        cancel_event: Optional[object],
        cancelled: Optional[Callable[[], bool]],
    ) -> bool:
        try:
            if callable(cancelled) and cancelled():
                return True
        except Exception:
            pass
        try:
            return bool(
                hasattr(cancel_event, "is_set") and cancel_event.is_set()
            )
        except Exception:
            return False

    @staticmethod
    def _terminate_process_group(process: subprocess.Popen) -> None:
        sent_group_signal = False
        try:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGTERM)
                sent_group_signal = True
            elif os.name == "nt":
                if process.poll() is not None:
                    return
                process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                if process.poll() is not None:
                    return
                process.terminate()
        except (OSError, ProcessLookupError):
            if process.poll() is None:
                try:
                    process.terminate()
                except OSError:
                    pass

        if process.poll() is None:
            try:
                process.wait(timeout=0.25)
            except subprocess.TimeoutExpired:
                pass

        try:
            # The shell can exit before its children. Signal the original
            # process group even after the group leader has been reaped.
            if os.name == "posix" and sent_group_signal:
                os.killpg(process.pid, signal.SIGKILL)
            elif os.name == "nt":
                # cmd.exe/PowerShell leave child processes behind; taskkill /T
                # removes the whole tree that CTRL_BREAK alone may miss.
                if process.poll() is None:
                    try:
                        subprocess.run(
                            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                            capture_output=True,
                            timeout=5,
                            creationflags=getattr(
                                subprocess, "CREATE_NO_WINDOW", 0
                            ),
                        )
                    except Exception:
                        pass
                    if process.poll() is None:
                        process.kill()
            elif process.poll() is None:
                process.kill()
        except (OSError, ProcessLookupError):
            pass

    @staticmethod
    def _collect_output(process: subprocess.Popen) -> Tuple[bytes, bytes]:
        try:
            stdout, stderr = process.communicate(timeout=0.25)
        except subprocess.TimeoutExpired:
            try:
                process.kill()
            except OSError:
                pass
            stdout, stderr = process.communicate()
        return stdout or b"", stderr or b""

    def _with_reason(self, stderr: str, reason: str) -> str:
        combined = "\n".join(part for part in ((stderr or "").strip(), reason) if part)
        return combined[: self.max_output_length]

    def _remember(self, result: CommandResult) -> CommandResult:
        self.last_result = result
        return result

    def get_current_dir(self) -> str:
        """Get current working directory"""
        return os.getcwd()

    def change_dir(self, path: str) -> Tuple[bool, str]:
        """Change working directory"""
        try:
            os.chdir(path)
            return True, f"Changed to {os.getcwd()}"
        except Exception as e:
            return False, str(e)

    def format_result(self, result: CommandResult) -> str:
        """Render a command result for the model (body-first contract).

        Output body first, then a marked ``[stderr]`` section, then at most one
        status marker on its own final line. Non-zero exits are reported, not
        errored — the model decides how to react. Infrastructure failures
        (spawn errors, missing tooling) render as a plain ``Error:`` result
        with no markers, so downstream error classification sees them at the
        top of the text.
        """
        if result.infrastructure:
            return result.stderr.strip() or "Error: command failed to start"

        body = result.stdout
        if result.stderr:
            if body and not body.endswith("\n"):
                body += "\n"
            body += f"[stderr]\n{result.stderr}"
        if not body:
            body = "(no output)"

        markers: list[str] = []
        if result.truncated and result.spill_path:
            markers.append(f"[output truncated; full output: {result.spill_path}]")
        if result.cancelled:
            markers.append("[cancelled]")
        elif result.timed_out:
            markers.append(
                f"[timed out after {result.timeout_s:g}s]"
                if result.timeout_s is not None
                else "[timed out]"
            )
        elif result.signal:
            markers.append(f"[killed by signal: {result.signal}]")
        elif result.returncode not in (0, None):
            markers.append(f"[exit code: {result.returncode}]")

        if not markers:
            return body
        if not body.endswith("\n"):
            body += "\n"
        return body + "\n".join(markers)
