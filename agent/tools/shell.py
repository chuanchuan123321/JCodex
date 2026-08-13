"""Shell execution tool"""

import os
import signal
import subprocess
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass


@dataclass
class CommandResult:
    """Result of command execution"""
    returncode: int
    stdout: str
    stderr: str
    success: bool


class ShellTool:
    """Tool for executing shell commands"""

    def __init__(self, max_output_length: int = 5000):
        self.max_output_length = max_output_length

    def execute(
        self,
        command: str,
        cwd: str | None = None,
        timeout: float | None = None,
        cancel_event: object | None = None,
        cancelled: Callable[[], bool] | None = None,
    ) -> CommandResult:
        """Execute a shell command and stop its process group on cancellation."""
        try:
            if self._is_cancelled(cancel_event, cancelled):
                return self._remember(CommandResult(
                    returncode=130,
                    stdout="",
                    stderr="Command cancelled",
                    success=False,
                ))

            popen_options = {}
            if os.name == "posix":
                popen_options["start_new_session"] = True
            elif os.name == "nt":
                popen_options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=cwd or os.getcwd(),
                **popen_options,
            )
            effective_timeout = float(timeout) if timeout else 30.0
            deadline = time.monotonic() + effective_timeout
            stdout = ""
            stderr = ""

            while True:
                if self._is_cancelled(cancel_event, cancelled):
                    self._terminate_process_group(process)
                    stdout, stderr = self._collect_output(process)
                    return self._remember(CommandResult(
                        returncode=130,
                        stdout=stdout[:self.max_output_length],
                        stderr=self._with_reason(stderr, "Command cancelled"),
                        success=False,
                    ))

                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._terminate_process_group(process)
                    stdout, stderr = self._collect_output(process)
                    return self._remember(CommandResult(
                        returncode=124,
                        stdout=stdout[:self.max_output_length],
                        stderr=self._with_reason(
                            stderr, f"Command timeout ({effective_timeout:g}s)"
                        ),
                        success=False,
                    ))

                try:
                    stdout, stderr = process.communicate(timeout=min(0.05, remaining))
                    break
                except subprocess.TimeoutExpired:
                    continue

            stdout = (stdout or "")[:self.max_output_length]
            stderr = (stderr or "")[:self.max_output_length]

            cmd_result = CommandResult(
                returncode=process.returncode,
                stdout=stdout,
                stderr=stderr,
                success=process.returncode == 0
            )

            return self._remember(cmd_result)
        except Exception as e:
            return self._remember(CommandResult(
                returncode=1,
                stdout="",
                stderr=str(e),
                success=False
            ))

    @staticmethod
    def _is_cancelled(
        cancel_event: object | None,
        cancelled: Callable[[], bool] | None,
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
                with suppress(OSError):
                    process.terminate()

        if process.poll() is None:
            with suppress(subprocess.TimeoutExpired):
                process.wait(timeout=0.25)

        try:
            # The shell can exit before its children. Signal the original
            # process group even after the group leader has been reaped.
            if os.name == "posix" and sent_group_signal:
                os.killpg(process.pid, signal.SIGKILL)
            elif process.poll() is None:
                process.kill()
        except (OSError, ProcessLookupError):
            pass

    @staticmethod
    def _collect_output(process: subprocess.Popen) -> tuple[str, str]:
        try:
            stdout, stderr = process.communicate(timeout=0.25)
        except subprocess.TimeoutExpired:
            with suppress(OSError):
                process.kill()
            stdout, stderr = process.communicate()
        return stdout or "", stderr or ""

    def _with_reason(self, stderr: str, reason: str) -> str:
        combined = "\n".join(part for part in ((stderr or "").strip(), reason) if part)
        return combined[:self.max_output_length]

    def _remember(self, result: CommandResult) -> CommandResult:
        return result

    def format_result(self, result: CommandResult) -> str:
        """Format command result for display"""
        output = []
        if result.stdout:
            output.append(f"Output:\n{result.stdout}")
        if result.stderr:
            output.append(f"Error:\n{result.stderr}")
        if not output:
            output.append("(No output)")

        status = "✓ Success" if result.success else f"✗ Failed (exit code: {result.returncode})"
        return f"{status}\n" + "\n".join(output)
