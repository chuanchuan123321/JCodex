"""Tests for the frozen backend's ``-m http.server`` preview branch.

On Windows packaged builds there is no ``python3``, so PreviewManager spawns
the bundled executable as ``jcodex-server -m http.server <port> --bind <host>``.
These tests verify that branch serves plain static files without the desktop
security headers that would block the in-app preview iframe.
"""
import http.client
import importlib.util
import threading
from pathlib import Path

import pytest


def _load_backend_entry():
    backend_path = (
        Path(__file__).resolve().parents[1] / "electron" / "backend_entry.py"
    )
    spec = importlib.util.spec_from_file_location(
        "jcodex_backend_entry", str(backend_path)
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def backend_entry():
    return _load_backend_entry()


def test_parse_http_server_args_defaults(backend_entry):
    host, port, directory = backend_entry.parse_http_server_args(
        ["-m", "http.server"]
    )
    assert host == "127.0.0.1"
    assert port == 0
    assert directory is None


def test_parse_http_server_args_full(backend_entry):
    host, port, directory = backend_entry.parse_http_server_args(
        [
            "-m",
            "http.server",
            "8002",
            "--bind",
            "127.0.0.1",
            "--directory",
            r"C:\site",
        ]
    )
    assert host == "127.0.0.1"
    assert port == 8002
    assert directory == r"C:\site"


def test_parse_http_server_args_quoted_values(backend_entry):
    host, port, directory = backend_entry.parse_http_server_args(
        ["-m", "http.server", '"8002"', "--bind", '"127.0.0.1"',
         "--directory", r'"C:\site"']
    )
    assert host == "127.0.0.1"
    assert port == 8002
    assert directory == r"C:\site"


def test_http_server_serves_plain_files_without_security_headers(
    backend_entry, tmp_path
):
    (tmp_path / "index.html").write_text("<h1>preview-ok</h1>", encoding="utf-8")
    server = backend_entry.create_http_server("127.0.0.1", 0, tmp_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    try:
        connection = http.client.HTTPConnection(host, port, timeout=5)
        connection.request("GET", "/index.html")
        response = connection.getresponse()
        body = response.read().decode("utf-8")
        headers = {key.lower(): value for key, value in response.getheaders()}
        connection.close()
        assert response.status == 200
        assert body == "<h1>preview-ok</h1>"
        assert "x-frame-options" not in headers
        assert "content-security-policy" not in headers
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
