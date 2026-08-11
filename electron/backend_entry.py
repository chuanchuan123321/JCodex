"""PyInstaller entrypoint for the JCodex desktop server.

Runs the desktop backend in server mode (no browser window) so the Electron
shell can host the UI.
"""
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
        print(f"[backend] bundled .env NOT found (looked in {bundle_root})", flush=True)
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
