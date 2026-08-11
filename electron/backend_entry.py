"""PyInstaller entrypoint for the JCodex desktop server.

Runs the desktop backend in server mode (no browser window) so the Electron
shell can host the UI. When the preview manager spawns this executable as
``jcodex-server -m http.server <port> --bind <host>`` (Windows packaged builds
have no ``python3``), it instead serves a plain loopback static file server
without the desktop security headers so the in-app preview iframe can load it.
"""
import functools
import os
import sys
from pathlib import Path


class _NullWriter:
    """Sink for windowed (--noconsole) builds where stdout/stderr are None."""

    def write(self, *args):
        return 0

    def flush(self):
        pass

    def isatty(self):
        return False

    def writelines(self, lines):
        for line in lines:
            self.write(line)


if sys.stdout is None:
    sys.stdout = _NullWriter()
if sys.stderr is None:
    sys.stderr = _NullWriter()


_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _unquote(value):
    value = str(value or "").strip()
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1]
    return value


def parse_http_server_args(argv):
    """Parse ``-m http.server [port] [--bind host] [--directory dir]``.

    ``PreviewManager`` launches the frozen executable with exactly this shape
    on Windows. Returns ``(host, port, directory)``.
    """
    host = "127.0.0.1"
    port = 0
    directory = None
    tokens = list(argv or [])
    index = 2  # skip "-m" and "http.server"
    while index < len(tokens):
        token = tokens[index]
        if token in {"--bind", "-b"} and index + 1 < len(tokens):
            host = _unquote(tokens[index + 1])
            index += 2
        elif token.startswith("--bind="):
            host = _unquote(token.split("=", 1)[1])
            index += 1
        elif token in {"--directory", "-d"} and index + 1 < len(tokens):
            directory = _unquote(tokens[index + 1])
            index += 2
        elif token.startswith("--directory="):
            directory = _unquote(token.split("=", 1)[1])
            index += 1
        else:
            unquoted = _unquote(token)
            if unquoted.isdigit():
                port = int(unquoted)
                index += 1
            else:
                index += 1
    return host, port, directory


def create_http_server(host, port, directory):
    """Create a plain loopback static file server with no security headers."""
    import http.server

    class _QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

    handler = functools.partial(_QuietHandler, directory=str(directory))
    return http.server.ThreadingHTTPServer((host, port), handler)


def run_http_server(argv):
    """Serve ``directory`` (or the working directory) over plain HTTP."""
    host, port, directory = parse_http_server_args(argv)
    if host not in _LOOPBACK_HOSTS:
        print(f"[preview] refused non-loopback bind host: {host}", flush=True)
        return 2
    if not (0 <= port <= 65535):
        port = 0
    serve_root = Path(directory).expanduser() if directory else Path.cwd()
    if not serve_root.is_dir():
        print(f"[preview] directory does not exist: {serve_root}", flush=True)
        return 1
    try:
        server = create_http_server(host, port, serve_root)
    except OSError as exc:
        print(f"[preview] failed to bind {host}:{port}: {exc}", flush=True)
        return 1
    bound_host, bound_port = server.server_address[:2]
    print(
        f"[preview] serving {serve_root} on http://{bound_host}:{bound_port}/",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "-m" and sys.argv[2] == "http.server":
        sys.exit(run_http_server(sys.argv[1:]))

    # 将打包时内置的 .env 作为默认配置注入环境。只在变量缺失时写入
    # （override=False），因此真实环境变量和用户数据目录下的
    # ~/Library/Application Support/JCodex/.env 仍然优先。
    try:
        from dotenv import load_dotenv

        bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        bundled_env = bundle_root / ".env"
        if bundled_env.exists():
            load_dotenv(bundled_env, override=False)
            print(f"[backend] bundled .env loaded from {bundled_env}", flush=True)
        else:
            print(
                f"[backend] bundled .env NOT found (looked in {bundle_root})",
                flush=True,
            )
    except Exception as exc:
        print(f"[backend] bundled .env load failed: {exc}", flush=True)

    print(
        "[backend] MEMORY_EMBEDDING_MODEL =",
        os.getenv("MEMORY_EMBEDDING_MODEL", "<unset>"),
        flush=True,
    )

    os.environ["MINIBOT_DESKTOP_MODE"] = "server"
    sys.argv = ["chat.py", "desktop"]

    import chat  # noqa: F401  (executes chat.py top-level init)

    from agent.ui.desktop import main as desktop_main

    desktop_main.main()


if __name__ == "__main__":
    main()
