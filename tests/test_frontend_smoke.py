"""Behavioral smoke test for the desktop frontend (jsdom, no browser).

Loads the real index.html + app.js with a stubbed eel bridge and asserts the
app boots, renders messages safely, and wires core UI. Skips when Node.js or
the jsdom dependency is unavailable (e.g. fresh clone without `npm ci`).
"""

import shutil
import subprocess
from pathlib import Path

import pytest

FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"
SMOKE_SCRIPT = FRONTEND_DIR / "smoke.mjs"


def _node_available() -> bool:
    if shutil.which("node") is None:
        return False
    # jsdom must be resolvable from the repo root (npm ci / npm install).
    root = FRONTEND_DIR.parents[1]
    probe = "import('jsdom').then(() => process.exit(0)).catch(() => process.exit(1))"
    try:
        result = subprocess.run(
            ["node", "--input-type=module", "-e", probe],
            cwd=root,
            capture_output=True,
            timeout=30,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


@pytest.mark.skipif(not _node_available(), reason="node/jsdom not installed (run: npm ci)")
def test_frontend_smoke() -> None:
    root = FRONTEND_DIR.parents[1]
    result = subprocess.run(
        ["node", str(SMOKE_SCRIPT)],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"frontend smoke failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    assert "frontend smoke OK" in result.stdout
