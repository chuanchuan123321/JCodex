"""Persistent, loopback-only development server previews."""

import atexit
import http.client
import ipaddress
import os
import re
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlsplit

try:
    import psutil
except ImportError:  # pragma: no cover - reported clearly on unsupported installs.
    psutil = None


EventCallback = Callable[[dict[str, Any]], None]

_ACTIVE_STATUSES = {"starting", "ready", "stopping"}
_SENSITIVE_ENV_MARKERS = (
    "ACCESS_KEY",
    "API_KEY",
    "AUTHORIZATION",
    "CLIENT_SECRET",
    "COOKIE",
    "CREDENTIAL",
    "PASSWORD",
    "PASSWD",
    "PRIVATE_KEY",
    "SESSION_TOKEN",
    "SECRET",
    "TOKEN",
)
_UNSAFE_BIND_PATTERN = re.compile(
    r"(?:^|[\s=:\"'])(?:0\.0\.0\.0|\[?::\]?)(?:$|[\s:\"'])"
)
_PYTHON_HTTP_SERVER_PATTERN = re.compile(
    r"(?P<prefix>\b(?:python(?:3(?:\.\d+)?)?|py)\s+-m\s+http\.server\b)"
    r"(?P<args>[^;&|]*)",
    re.IGNORECASE,
)
_PYTHON_HTTP_SERVER_PREFIX_PATTERN = re.compile(
    r"\b(?:python(?:3(?:\.\d+)?)?|py)\s+-m\s+http\.server\b",
    re.IGNORECASE,
)
_WINDOWS_PREVIEW_VARIABLE_PATTERN = re.compile(
    r"\$\{(?P<braced>HOST|PORT)\}|\$(?P<plain>HOST|PORT)\b"
)
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
ListenerEndpoint = tuple[str, int]


@dataclass
class _PreviewProcess:
    preview_id: str
    command: str
    workdir: Path
    name: str
    host: str
    port: int
    url: str
    entry_path: str
    health_path: str
    startup_timeout: float
    conversation_id: str
    message_id: str
    log_path: Path
    process: subprocess.Popen | None = None
    status: str = "starting"
    error: str = ""
    stop_reason: str = ""
    started_at: float = field(default_factory=time.time)
    ready_at: float | None = None
    stopped_at: float | None = None
    stop_requested: bool = False
    state_event: threading.Event = field(default_factory=threading.Event)
    log_tail: bytearray = field(default_factory=bytearray)
    managed_processes: dict[int, float] = field(default_factory=dict)


class PreviewManager:
    """Manage long-running local web previews independently from shell tools."""

    HOST = "127.0.0.1"
    MAX_LOG_BYTES = 256 * 1024
    MAX_TAIL_BYTES = 64 * 1024
    MAX_RETAINED_LOGS = 24

    def __init__(
        self,
        project_root: str | Path,
        event_callback: EventCallback | None = None,
        log_dir: str | Path | None = None,
    ) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        if not self.project_root.is_dir():
            raise ValueError(f"Project root does not exist: {self.project_root}")

        default_log_dir = self.project_root / "workspace" / "temp" / "previews"
        raw_log_dir = Path(log_dir or default_log_dir).expanduser()
        if not raw_log_dir.is_absolute():
            raw_log_dir = self.project_root / raw_log_dir
        # The desktop app may keep managed logs in its own workspace while the
        # previewed code lives in a separately bound user project.
        self.log_dir = raw_log_dir.resolve()
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.event_callback = event_callback
        self._previews: dict[str, _PreviewProcess] = {}
        self._lock = threading.RLock()
        self._prune_logs()
        atexit.register(self.stop_all)

    def start(
        self,
        command: str,
        workdir: str | Path = ".",
        name: str | None = None,
        port: int = 0,
        health_path: str = "/",
        startup_timeout: float = 20,
        conversation_id: str | None = None,
        message_id: str | None = None,
        entry_path: str | None = None,
    ) -> dict[str, Any]:
        """Start a server, wait until it accepts HTTP connections, and retain it."""
        preview_id = uuid.uuid4().hex
        conversation_id = str(conversation_id or "")
        message_id = str(message_id or "")
        requested_name = str(name or "").strip()[:120]
        try:
            command = self._validate_command(command)
            resolved_workdir = self._resolve_workdir(workdir)
            entry_path = self._resolve_entry_path(resolved_workdir, entry_path)
            health_path = self._validate_health_path(health_path)
            startup_timeout = min(max(float(startup_timeout), 1.0), 120.0)
            requested_port = int(port or 0)
            if requested_port < 0 or requested_port > 65535:
                raise ValueError("port must be 0 or between 1 and 65535")
        except (TypeError, ValueError) as exc:
            result = {
                "success": False,
                "preview_id": preview_id,
                "status": "error",
                "error": str(exc),
            }
            self._emit_error_payload(
                preview_id=preview_id,
                error=str(exc),
                conversation_id=conversation_id,
                message_id=message_id,
                name=requested_name or "Project preview",
                workdir=str(workdir or "."),
            )
            return result

        display_name = requested_name or resolved_workdir.name or "Project preview"
        display_name = display_name[:120] or "Project preview"
        if self._is_windows() and psutil is None:
            error = (
                "Windows preview requires the psutil dependency "
                "to verify loopback binding"
            )
            result = {
                "success": False,
                "preview_id": preview_id,
                "status": "error",
                "error": error,
            }
            self._emit_error_payload(
                preview_id=preview_id,
                error=error,
                conversation_id=conversation_id,
                message_id=message_id,
                name=display_name,
                workdir=str(resolved_workdir),
            )
            return result
        command = self._normalize_command(command)

        reusable = self._find_reusable(
            command, resolved_workdir, conversation_id, requested_port
        )
        if reusable is not None:
            with self._lock:
                reusable.message_id = message_id or reusable.message_id
                reusable.name = display_name or reusable.name
                reusable.entry_path = entry_path
                reusable.health_path = health_path
                reusable.url = self._format_url(
                    reusable.host, reusable.port, entry_path
                )
            result = self._snapshot(reusable)
            result["reused"] = True
            self._emit(
                "preview_ready" if reusable.status == "ready" else "preview_starting",
                reusable,
                reused=True,
            )
            return result

        try:
            selected_port = self._select_port(requested_port)
        except ValueError as exc:
            result = {
                "success": False,
                "preview_id": preview_id,
                "status": "error",
                "error": str(exc),
            }
            self._emit_error_payload(
                preview_id=preview_id,
                error=str(exc),
                conversation_id=conversation_id,
                message_id=message_id,
                name=display_name,
                workdir=str(resolved_workdir),
                port=requested_port,
            )
            return result

        url = self._format_url(self.HOST, selected_port, entry_path)
        record = _PreviewProcess(
            preview_id=preview_id,
            command=command,
            workdir=resolved_workdir,
            name=display_name,
            host=self.HOST,
            port=selected_port,
            url=url,
            entry_path=entry_path,
            health_path=health_path,
            startup_timeout=startup_timeout,
            conversation_id=conversation_id,
            message_id=message_id,
            log_path=self.log_dir / f"preview-{preview_id}.log",
        )
        with self._lock:
            self._previews[preview_id] = record

        self._emit("preview_starting", record)
        try:
            record.process = subprocess.Popen(
                self._prepare_launch_command(command),
                shell=True,
                cwd=str(resolved_workdir),
                env=self._build_environment(
                    selected_port, self._format_url(self.HOST, selected_port)
                ),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                close_fds=True,
                **self._build_popen_options(),
            )
            if self._is_windows():
                self._remember_windows_process(record, record.process.pid)
        except Exception as exc:
            self._mark_error(record, f"无法启动预览进程：{exc}")
            return self._snapshot(record)

        threading.Thread(
            target=self._capture_output,
            args=(record,),
            name=f"preview-log-{preview_id[:8]}",
            daemon=True,
        ).start()
        threading.Thread(
            target=self._monitor,
            args=(record,),
            name=f"preview-monitor-{preview_id[:8]}",
            daemon=True,
        ).start()

        # The starting callback is immediate; waiting here gives the model a usable URL.
        record.state_event.wait(startup_timeout + 2.0)
        if not record.state_event.is_set():
            self._mark_error(record, "预览启动监控未能正常完成")
        return self._snapshot(record)

    def status(
        self,
        preview_id: str | None = None,
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        """Return one preview or all previews belonging to a conversation."""
        if preview_id:
            with self._lock:
                record = self._previews.get(str(preview_id))
            if record is None:
                return {
                    "success": False,
                    "preview_id": str(preview_id),
                    "status": "error",
                    "error": "Preview not found",
                }
            self._sync_process_state(record)
            return self._snapshot(record, include_log=True)

        conversation_filter = None
        if conversation_id is not None:
            conversation_filter = str(conversation_id)
        with self._lock:
            records = list(self._previews.values())
        if conversation_filter is not None:
            records = [
                record
                for record in records
                if record.conversation_id == conversation_filter
            ]
        records.sort(key=lambda item: item.started_at, reverse=True)
        for record in records:
            self._sync_process_state(record)
        return {
            "success": True,
            "previews": [self._snapshot(record) for record in records],
        }

    def stop(self, preview_id: str, reason: str = "user") -> dict[str, Any]:
        """Stop one preview and its complete process group."""
        if not preview_id:
            return {
                "success": False,
                "status": "error",
                "error": "preview_id is required",
            }
        with self._lock:
            record = self._previews.get(str(preview_id))
            if record is None:
                return {
                    "success": False,
                    "preview_id": str(preview_id),
                    "status": "error",
                    "error": "Preview not found",
                }
            if record.status in {"stopped", "error"}:
                return self._snapshot(record)
            record.stop_requested = True
            record.stop_reason = str(reason or "user")[:120]
            record.status = "stopping"

        self._terminate_process(record)
        self._mark_stopped(record)
        return self._snapshot(record)

    def stop_conversation(self, conversation_id: str) -> dict[str, Any]:
        """Stop every active preview owned by a conversation."""
        conversation_id = str(conversation_id or "")
        with self._lock:
            preview_ids = [
                record.preview_id
                for record in self._previews.values()
                if record.conversation_id == conversation_id
                and record.status in _ACTIVE_STATUSES
            ]
        results = [
            self.stop(preview_id, reason="conversation_closed")
            for preview_id in preview_ids
        ]
        return {
            "success": True,
            "conversation_id": conversation_id,
            "stopped": results,
        }

    def clear_conversation(self, conversation_id: str) -> dict[str, Any]:
        """Stop and forget every preview owned by a cleared conversation."""
        conversation_id = str(conversation_id or "")
        stopped = self.stop_conversation(conversation_id)
        with self._lock:
            records = [
                record
                for record in self._previews.values()
                if record.conversation_id == conversation_id
            ]
            for record in records:
                self._previews.pop(record.preview_id, None)
        for record in records:
            with suppress(OSError):
                record.log_path.unlink(missing_ok=True)
        return {
            **stopped,
            "cleared": [record.preview_id for record in records],
        }

    def stop_all(self) -> dict[str, Any]:
        """Stop all processes. Safe to call repeatedly during application exit."""
        with self._lock:
            preview_ids = [
                record.preview_id
                for record in self._previews.values()
                if record.status in _ACTIVE_STATUSES
            ]
        results = [
            self.stop(preview_id, reason="application_exit")
            for preview_id in preview_ids
        ]
        return {"success": True, "stopped": results}

    def _resolve_path(self, path: str | Path) -> Path:
        """Resolve relative paths from the task root and accept absolute folders."""
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            candidate = self.project_root / candidate
        return candidate.resolve()

    def _resolve_workdir(self, workdir: str | Path) -> Path:
        path = self._resolve_path(workdir or ".")
        if not path.is_dir():
            raise ValueError(f"Preview workdir does not exist: {path}")
        return path

    @classmethod
    def _resolve_entry_path(
        cls, workdir: Path, entry_path: str | None
    ) -> str:
        """Resolve an explicit page target or a useful static-site default."""
        raw_path = str(entry_path or "").strip()
        if raw_path:
            return cls._validate_entry_path(raw_path)

        root_indexes = sorted(
            (
                child
                for child in workdir.iterdir()
                if child.is_file()
                and child.name.lower() in {"index.html", "index.htm"}
            ),
            key=lambda child: (
                child.name.lower() != "index.html",
                child.name.lower(),
                child.name,
            ),
        )
        if root_indexes:
            root_index = root_indexes[0]
            if root_index.name in {"index.html", "index.htm"}:
                return "/"
            return cls._validate_entry_path(root_index.name)

        root_html_files = sorted(
            (
                child
                for child in workdir.iterdir()
                if child.is_file() and child.suffix.lower() in {".html", ".htm"}
            ),
            key=lambda child: child.name.lower(),
        )
        if len(root_html_files) == 1:
            return cls._validate_entry_path(root_html_files[0].name)
        return "/"

    @staticmethod
    def _validate_entry_path(entry_path: str) -> str:
        """Accept a same-origin path while rejecting URL and traversal forms."""
        raw_path = str(entry_path or "").strip()
        if not raw_path:
            return "/"
        if "\\" in raw_path or any(ord(character) < 32 for character in raw_path):
            raise ValueError("entry_path contains invalid characters")
        parts = urlsplit(raw_path)
        if parts.scheme or parts.netloc or parts.query or parts.fragment:
            raise ValueError("entry_path must be a local path such as /page.html")

        path = parts.path
        while True:
            decoded_path = unquote(path)
            if decoded_path == path:
                break
            path = decoded_path
        if "\\" in path or any(ord(character) < 32 for character in path):
            raise ValueError("entry_path contains invalid characters")
        if not path.startswith("/"):
            path = f"/{path}"
        if any(segment in {".", ".."} for segment in path.split("/")):
            raise ValueError("entry_path may not contain dot traversal")
        return quote(path, safe="/:@!$&'()*+,;=-._~")

    @staticmethod
    def _validate_command(command: str) -> str:
        command = str(command or "").strip()
        if not command:
            raise ValueError("command is required for start")
        if "\x00" in command or "\n" in command or "\r" in command:
            raise ValueError("command must be a single shell command line")
        try:
            shlex.split(command, posix=True)
        except ValueError as exc:
            raise ValueError(f"Preview command has incomplete quoting: {exc}") from exc
        if _UNSAFE_BIND_PATTERN.search(command):
            raise ValueError("Preview commands may only bind to 127.0.0.1")
        for host_argument in re.findall(
            r"(?:--host(?:=|\s+)|--bind(?:=|\s+))([^\s;&|]+)", command
        ):
            host = host_argument.strip("\"'")
            if host not in {
                "$HOST",
                "${HOST}",
                "%HOST%",
                "127.0.0.1",
                "localhost",
            }:
                raise ValueError(
                    "Preview host arguments must use $HOST, localhost, or 127.0.0.1"
                )
        return command

    @staticmethod
    def _is_windows() -> bool:
        """Keep platform branches easy to exercise without changing global os state."""
        return os.name == "nt"

    @classmethod
    def _prepare_launch_command(cls, command: str) -> str:
        """Adapt the portable preview command to the shell of the current OS."""
        if not cls._is_windows():
            return command

        # The desktop application's interpreter is always available, unlike a
        # separately installed ``python3`` command on many Windows machines.
        executable = subprocess.list2cmdline([sys.executable])
        command = _PYTHON_HTTP_SERVER_PREFIX_PATTERN.sub(
            lambda _match: f"{executable} -m http.server", command
        )

        # Tool prompts use POSIX-style variables on every platform. cmd.exe
        # expands percent-delimited variables instead, so translate only the
        # two variables injected by the preview manager.
        def windows_variable(match: re.Match) -> str:
            name = match.group("braced") or match.group("plain")
            return f"%{name}%"

        return _WINDOWS_PREVIEW_VARIABLE_PATTERN.sub(windows_variable, command)

    @classmethod
    def _build_popen_options(cls) -> dict[str, Any]:
        """Create an isolated process group using each platform's mechanism."""
        if not cls._is_windows():
            return {"start_new_session": True}

        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        # Do not flash a console window while the desktop application starts a preview.
        creationflags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
        return {"creationflags": creationflags} if creationflags else {}

    @classmethod
    def _normalize_command(cls, command: str) -> str:
        """Make common preview servers honor the managed loopback endpoint."""

        def normalize_python_http_server(match: re.Match) -> str:
            if "<" in match.group("args") or ">" in match.group("args"):
                # Preserve shell redirection syntax; runtime endpoint discovery
                # still verifies the actual listener belongs to this process group.
                return match.group(0)
            try:
                tokens = shlex.split(match.group("args"), posix=True)
            except ValueError:
                return match.group(0)

            def unquote_token(token: str) -> str:
                if (
                    len(token) >= 2
                    and token[0] == token[-1]
                    and token[0] in {"\"", "'"}
                ):
                    return token[1:-1]
                return token

            remaining = []
            positional_port_removed = False
            index = 0
            while index < len(tokens):
                token = tokens[index]
                value = unquote_token(token)
                lower_token = value.lower()
                if lower_token in {"--bind", "-b"}:
                    index += 2
                    continue
                if lower_token.startswith("--bind="):
                    index += 1
                    continue
                if lower_token in {
                    "--directory",
                    "-d",
                    "--protocol",
                    "-p",
                }:
                    remaining.append(token)
                    if index + 1 < len(tokens):
                        remaining.append(tokens[index + 1])
                    index += 2
                    continue
                if lower_token.startswith(("--directory=", "--protocol=")):
                    remaining.append(token)
                    index += 1
                    continue
                if (
                    not positional_port_removed
                    and not token.startswith("-")
                    and (
                        value in {"$PORT", "${PORT}", "%PORT%"}
                        or value.isdigit()
                    )
                ):
                    positional_port_removed = True
                    index += 1
                    continue
                remaining.append(value if cls._is_windows() else token)
                index += 1

            if cls._is_windows():
                suffix = (
                    f" {subprocess.list2cmdline(remaining)}" if remaining else ""
                )
                return f'{match.group("prefix")} "%PORT%" --bind "%HOST%"{suffix}'

            suffix = "".join(f" {shlex.quote(token)}" for token in remaining)
            return f'{match.group("prefix")} "$PORT" --bind "$HOST"{suffix}'

        return _PYTHON_HTTP_SERVER_PATTERN.sub(
            normalize_python_http_server, command
        )

    @staticmethod
    def _validate_health_path(health_path: str) -> str:
        health_path = str(health_path or "/").strip()
        parts = urlsplit(health_path)
        if parts.scheme or parts.netloc or not health_path.startswith("/"):
            raise ValueError("health_path must be a local absolute path such as /")
        if parts.fragment or any(ord(character) < 32 for character in health_path):
            raise ValueError("health_path contains invalid characters")
        return health_path

    def _find_reusable(
        self,
        command: str,
        workdir: Path,
        conversation_id: str,
        requested_port: int,
    ) -> _PreviewProcess | None:
        with self._lock:
            records = list(self._previews.values())
        for record in records:
            if (
                record.command == command
                and record.workdir == workdir
                and record.conversation_id == conversation_id
                and record.status in {"starting", "ready"}
                and (requested_port == 0 or record.port == requested_port)
                and record.process is not None
                and record.process.poll() is None
            ):
                return record
        return None

    def _select_port(self, requested_port: int) -> int:
        if requested_port:
            if not self._port_available(requested_port):
                raise ValueError(f"Loopback port {requested_port} is already in use")
            return requested_port
        for _ in range(10):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind((self.HOST, 0))
                port = int(sock.getsockname()[1])
            if self._port_available(port):
                return port
        raise ValueError("Unable to allocate a loopback preview port")

    def _port_available(self, port: int) -> bool:
        with self._lock:
            if any(
                record.port == port and record.status in _ACTIVE_STATUSES
                for record in self._previews.values()
            ):
                return False
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                if self._is_windows() and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                sock.bind((self.HOST, port))
            return True
        except OSError:
            return False

    @staticmethod
    def _is_sensitive_environment_key(key: str) -> bool:
        upper_key = key.upper()
        return upper_key.endswith("_KEY") or any(
            marker in upper_key for marker in _SENSITIVE_ENV_MARKERS
        )

    def _build_environment(self, port: int, url: str) -> dict[str, str]:
        environment = {
            key: value
            for key, value in os.environ.items()
            if not self._is_sensitive_environment_key(key)
        }
        environment.update(
            {
                "HOST": self.HOST,
                "PORT": str(port),
                "BROWSER": "none",
                "NO_OPEN": "1",
                "MINIBOT_PREVIEW_HOST": self.HOST,
                "MINIBOT_PREVIEW_PORT": str(port),
                "MINIBOT_PREVIEW_URL": url,
            }
        )
        return environment

    def _monitor(self, record: _PreviewProcess) -> None:
        deadline = time.monotonic() + record.startup_timeout
        while time.monotonic() < deadline:
            with self._lock:
                if record.status != "starting":
                    return
                process = record.process
            if process is None:
                time.sleep(0.05)
                continue
            return_code = process.poll()
            if return_code is not None:
                self._mark_error(
                    record,
                    f"预览服务在就绪前退出（退出码 {return_code}）",
                )
                return
            if self._http_reachable(record):
                endpoints, unsafe_listener = self._process_group_listener_endpoints(
                    record
                )
                if unsafe_listener:
                    error = (
                        "预览服务监听了外部网络接口，"
                        "已为安全起见停止"
                        if endpoints is not None
                        else (
                            "无法验证 Windows 预览进程的本地监听状态，"
                            "已停止"
                        )
                    )
                    self._mark_error(
                        record,
                        error,
                    )
                    return
                owned_ports = (
                    {port for _, port in endpoints} if endpoints is not None else None
                )
                if owned_ports is not None and record.port not in owned_ports:
                    discovered = self._discover_process_group_http_endpoint(
                        record, endpoints=endpoints
                    )
                    if discovered:
                        discovered_host, discovered_port = discovered
                        with self._lock:
                            if record.status != "starting":
                                return
                            record.host = discovered_host
                            record.port = discovered_port
                            record.url = self._format_url(
                                discovered_host, discovered_port, record.entry_path
                            )
                            record.status = "ready"
                            record.ready_at = time.time()
                            record.state_event.set()
                        self._emit(
                            "preview_ready", record, port_discovered=True
                        )
                        self._watch_running_process(record)
                        return
                    time.sleep(0.05)
                    continue
                with self._lock:
                    if record.status != "starting":
                        return
                    record.status = "ready"
                    record.ready_at = time.time()
                    record.state_event.set()
                self._emit("preview_ready", record)
                self._watch_running_process(record)
                return
            endpoints, unsafe_listener = self._process_group_listener_endpoints(record)
            if unsafe_listener:
                error = (
                    "预览服务监听了外部网络接口，"
                    "已为安全起见停止"
                    if endpoints is not None
                    else (
                        "无法验证 Windows 预览进程的本地监听状态，"
                        "已停止"
                    )
                )
                self._mark_error(
                    record,
                    error,
                )
                return
            discovered = self._discover_process_group_http_endpoint(
                record, endpoints=endpoints
            )
            if discovered and discovered != (record.host, record.port):
                discovered_host, discovered_port = discovered
                with self._lock:
                    if record.status != "starting":
                        return
                    record.host = discovered_host
                    record.port = discovered_port
                    record.url = self._format_url(
                        discovered_host, discovered_port, record.entry_path
                    )
                self._emit("preview_starting", record, port_discovered=True)
                if self._http_reachable(record):
                    with self._lock:
                        if record.status != "starting":
                            return
                        record.status = "ready"
                        record.ready_at = time.time()
                        record.state_event.set()
                    self._emit("preview_ready", record, port_discovered=True)
                    self._watch_running_process(record)
                    return
            time.sleep(0.2)

        self._mark_error(
            record,
            (
                f"预览服务在 {record.startup_timeout:g} 秒内未就绪。"
                "请确认启动命令使用系统分配的端口，并监听 127.0.0.1"
            ),
        )

    def _watch_running_process(self, record: _PreviewProcess) -> None:
        process = record.process
        if process is None:
            return
        return_code = process.wait()
        with self._lock:
            stop_requested = record.stop_requested
            current_status = record.status
        if current_status in {"stopped", "error"}:
            return
        if stop_requested or current_status == "stopping":
            self._mark_stopped(record)
        else:
            self._mark_error(
                record, f"预览进程意外退出（退出码 {return_code}）"
            )

    @staticmethod
    def _http_reachable(record: _PreviewProcess) -> bool:
        connection = http.client.HTTPConnection(record.host, record.port, timeout=0.6)
        try:
            connection.request(
                "GET",
                record.health_path,
                headers={"User-Agent": "Minibot-Preview/1.0", "Connection": "close"},
            )
            response = connection.getresponse()
            response.read(1)
            return True
        except (OSError, http.client.HTTPException):
            return False
        finally:
            connection.close()

    def _discover_process_group_http_endpoint(
        self,
        record: _PreviewProcess,
        endpoints: set[ListenerEndpoint] | None = None,
    ) -> ListenerEndpoint | None:
        """Find one loopback HTTP endpoint owned by this preview process group."""
        if endpoints is None:
            endpoints, unsafe_listener = self._process_group_listener_endpoints(record)
            if unsafe_listener:
                return None
        if not endpoints:
            return None
        ports = {port for _, port in endpoints}
        if len(ports) != 1:
            return None
        port = next(iter(ports))
        candidate_hosts = [
            host for host, candidate_port in endpoints if candidate_port == port
        ]
        candidate_hosts.sort(key=lambda host: host != self.HOST)
        host = candidate_hosts[0]
        probe = _PreviewProcess(
            preview_id=record.preview_id,
            command=record.command,
            workdir=record.workdir,
            name=record.name,
            host=host,
            port=port,
            url=self._format_url(host, port, record.entry_path),
            entry_path=record.entry_path,
            health_path=record.health_path,
            startup_timeout=record.startup_timeout,
            conversation_id=record.conversation_id,
            message_id=record.message_id,
            log_path=record.log_path,
        )
        return (host, port) if self._http_reachable(probe) else None

    def _process_group_listener_endpoints(
        self, record: _PreviewProcess
    ) -> tuple[set[ListenerEndpoint] | None, bool]:
        """Return this process group's loopback endpoints and unsafe bind state."""
        process = record.process
        if process is None or process.poll() is not None:
            if self._is_windows():
                return self._windows_listener_endpoints(record)
            return set(), False
        # Windows does not support the POSIX lsof process-group query. Use the
        # managed process tree so readiness cannot be claimed by another local
        # server or by a listener on an externally reachable interface.
        if self._is_windows():
            return self._windows_listener_endpoints(record)
        lsof = shutil.which("lsof")
        if not lsof and Path("/usr/sbin/lsof").is_file():
            lsof = "/usr/sbin/lsof"
        if not lsof:
            return None, False
        try:
            result = subprocess.run(
                [
                    lsof,
                    "-nP",
                    "-a",
                    "-g",
                    str(process.pid),
                    "-iTCP",
                    "-sTCP:LISTEN",
                    "-F",
                    "n",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=1,
            )
        except (OSError, subprocess.SubprocessError):
            return None, False

        endpoints: set[ListenerEndpoint] = set()
        for line in result.stdout.splitlines():
            if not line.startswith("n"):
                continue
            endpoint = line[1:].strip()
            try:
                host, raw_port = endpoint.rsplit(":", 1)
                port = int(raw_port)
            except (ValueError, TypeError):
                return set(), True
            host = host.strip("[]").lower()
            if host not in _LOOPBACK_HOSTS and not host.startswith("127."):
                return set(), True
            endpoints.add((host, port))
        return endpoints, False

    def _windows_listener_endpoints(
        self, record: _PreviewProcess
    ) -> tuple[set[ListenerEndpoint] | None, bool]:
        """Inspect Windows launcher descendants for TCP listeners via psutil."""
        if psutil is None:
            return None, True

        root_pid = record.process.pid if record.process is not None else None
        candidate_pids = set(record.managed_processes)
        if root_pid:
            candidate_pids.add(root_pid)
        if not candidate_pids:
            return None, True

        processes = []
        for pid in candidate_pids:
            try:
                process = psutil.Process(pid)
                processes.append(process)
                processes.extend(process.children(recursive=True))
            except (psutil.Error, OSError):
                continue

        if not processes:
            return None, True

        endpoints: set[ListenerEndpoint] = set()
        for owned_process in processes:
            try:
                pid = int(owned_process.pid)
                record.managed_processes.setdefault(pid, time.monotonic())
                connections = owned_process.net_connections(kind="tcp")
            except (psutil.Error, OSError):
                continue
            for connection in connections:
                if connection.status != psutil.CONN_LISTEN or not connection.laddr:
                    continue
                host = str(connection.laddr.ip).strip("[]").lower()
                port = int(connection.laddr.port)
                if not self._is_loopback_host(host):
                    return set(), True
                endpoints.add((host, port))
        return endpoints, False

    @staticmethod
    def _remember_windows_process(record: _PreviewProcess, pid: int) -> None:
        """Retain the launcher PID so cleanup still reaches orphaned children."""
        record.managed_processes.setdefault(int(pid), time.monotonic())

    @staticmethod
    def _is_loopback_host(host: str) -> bool:
        """Return whether a listener address is limited to the local machine."""
        if host.lower() in _LOOPBACK_HOSTS:
            return True
        try:
            return ipaddress.ip_address(host).is_loopback
        except ValueError:
            return False

    @staticmethod
    def _format_url(host: str, port: int, entry_path: str = "/") -> str:
        display_host = f"[{host}]" if ":" in host else host
        path = str(entry_path or "/")
        if not path.startswith("/"):
            path = f"/{path}"
        return f"http://{display_host}:{port}{path}"

    def _capture_output(self, record: _PreviewProcess) -> None:
        process = record.process
        if process is None or process.stdout is None:
            return
        try:
            with record.log_path.open("w+b") as log_file:
                while True:
                    read_chunk = getattr(process.stdout, "read1", None)
                    chunk = (
                        read_chunk(4096)
                        if callable(read_chunk)
                        else process.stdout.read(4096)
                    )
                    if not chunk:
                        break
                    with self._lock:
                        record.log_tail.extend(chunk)
                        if len(record.log_tail) > self.MAX_TAIL_BYTES:
                            del record.log_tail[: -self.MAX_TAIL_BYTES]
                    log_file.write(chunk)
                    log_file.flush()
                    if log_file.tell() > self.MAX_LOG_BYTES:
                        log_file.seek(-self.MAX_TAIL_BYTES, os.SEEK_END)
                        tail = log_file.read(self.MAX_TAIL_BYTES)
                        log_file.seek(0)
                        log_file.write(tail)
                        log_file.truncate()
                        log_file.seek(0, os.SEEK_END)
        except (OSError, ValueError):
            return
        finally:
            with suppress(OSError, ValueError):
                process.stdout.close()

    def _terminate_process(self, record: _PreviewProcess) -> None:
        process = record.process
        if process is None:
            return
        if self._is_windows():
            self._terminate_windows_process_tree(record)
            return

        process_group = process.pid
        try:
            os.killpg(process_group, signal.SIGTERM)
        except (OSError, ProcessLookupError):
            with suppress(OSError):
                process.terminate()

        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline and self._process_group_exists(process_group):
            with suppress(subprocess.TimeoutExpired):
                process.wait(timeout=0.05)
            time.sleep(0.05)
        if not self._process_group_exists(process_group):
            with suppress(subprocess.TimeoutExpired):
                process.wait(timeout=0.1)
            return

        try:
            os.killpg(process_group, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            with suppress(OSError):
                process.kill()
        with suppress(subprocess.TimeoutExpired):
            process.wait(timeout=1)

    def _terminate_windows_process_tree(self, record: _PreviewProcess) -> None:
        """Stop the cmd.exe launcher and every preview child on Windows."""
        process = record.process
        if process is None:
            return

        with self._lock:
            process_ids = list(record.managed_processes)
        if process.pid not in process_ids:
            process_ids.insert(0, process.pid)
        else:
            process_ids.remove(process.pid)
            process_ids.insert(0, process.pid)

        # ``cmd.exe`` can exit before npm/npx/node descendants. taskkill /T
        # must run for each previously observed process even after the launcher
        # itself has exited.
        taskkill_available = True
        for process_id in process_ids:
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(process_id), "/T", "/F"],
                    check=False,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=3,
                )
            except (OSError, subprocess.SubprocessError):
                taskkill_available = False
                break
        if not taskkill_available and process.poll() is None:
            with suppress(OSError):
                process.kill()
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            with suppress(OSError):
                process.kill()

    @staticmethod
    def _process_group_exists(process_group: int) -> bool:
        """Return whether a POSIX process group is still alive."""
        try:
            os.killpg(process_group, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True

    def _sync_process_state(self, record: _PreviewProcess) -> None:
        process = record.process
        if (
            process is not None
            and process.poll() is not None
            and record.status in {"starting", "ready"}
        ):
            self._mark_error(
                record,
                f"预览进程意外退出（退出码 {process.returncode}）",
            )

    def _mark_stopped(self, record: _PreviewProcess) -> None:
        with self._lock:
            if record.status in {"stopped", "error"}:
                record.state_event.set()
                return
            record.status = "stopped"
            record.stopped_at = time.time()
            record.state_event.set()
        self._emit("preview_stopped", record)

    def _mark_error(self, record: _PreviewProcess, error: str) -> None:
        with self._lock:
            if record.status in {"stopped", "error"}:
                record.state_event.set()
                return
            record.status = "stopping"
        self._terminate_process(record)
        with self._lock:
            record.status = "error"
            record.error = str(error)
            record.stopped_at = time.time()
            record.state_event.set()
        self._emit("preview_error", record, error=record.error)

    def _snapshot(
        self, record: _PreviewProcess, include_log: bool = False
    ) -> dict[str, Any]:
        with self._lock:
            process = record.process
            result: dict[str, Any] = {
                "success": record.status != "error",
                "preview_id": record.preview_id,
                "status": record.status,
                "name": record.name,
                "url": record.url,
                "entry_path": record.entry_path,
                "host": record.host,
                "port": record.port,
                "workdir": str(record.workdir),
                "health_path": record.health_path,
                "conversation_id": record.conversation_id,
                "message_id": record.message_id,
                "pid": process.pid if process is not None else None,
                "started_at_ms": int(record.started_at * 1000),
                "ready_at_ms": (
                    int(record.ready_at * 1000) if record.ready_at is not None else None
                ),
                "stopped_at_ms": (
                    int(record.stopped_at * 1000)
                    if record.stopped_at is not None
                    else None
                ),
                "error": record.error,
                "stop_reason": record.stop_reason,
                "log_path": str(record.log_path),
            }
            if include_log or record.status == "error":
                result["log_tail"] = bytes(record.log_tail).decode(
                    "utf-8", errors="replace"
                )[-8000:]
        return result

    def _emit(self, event_type: str, record: _PreviewProcess, **extra: Any) -> None:
        callback = self.event_callback
        if callback is None:
            return
        payload = self._snapshot(record)
        payload.update(extra)
        payload["type"] = event_type
        payload["event_at_ms"] = int(time.time() * 1000)
        if event_type == "preview_error":
            payload["log_tail"] = bytes(record.log_tail).decode(
                "utf-8", errors="replace"
            )
        # A UI callback failure must never orphan the managed process.
        with suppress(Exception):
            callback(payload)

    def _emit_error_payload(
        self,
        preview_id: str,
        error: str,
        conversation_id: str,
        message_id: str,
        name: str,
        workdir: str,
        port: int = 0,
    ) -> None:
        callback = self.event_callback
        if callback is None:
            return
        payload = {
            "type": "preview_error",
            "success": False,
            "preview_id": preview_id,
            "status": "error",
            "name": name,
            "url": "",
            "host": self.HOST,
            "port": port,
            "workdir": workdir,
            "conversation_id": conversation_id,
            "message_id": message_id,
            "error": error,
            "log_tail": "",
            "event_at_ms": int(time.time() * 1000),
        }
        with suppress(Exception):
            callback(payload)

    def _prune_logs(self) -> None:
        try:
            logs = sorted(
                self.log_dir.glob("preview-*.log"),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
            for path in logs[self.MAX_RETAINED_LOGS :]:
                path.unlink(missing_ok=True)
        except OSError:
            pass
