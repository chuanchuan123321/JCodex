"""Tests for the bounded URL fetcher — no external network required.

A local http.server thread serves the fixtures; every request stays on
127.0.0.1. Covers URL hygiene, redirect policy, byte/char caps, content-type
classification, and charset decoding.
"""
from __future__ import annotations

import http.server
import threading

from agent.tools.url_fetch import (
    classify_content_type,
    decode_body,
    fetch_url,
    validate_fetch_url,
)


class _FixtureHandler(http.server.BaseHTTPRequestHandler):
    """Serve routes from a class-level dict; logs nothing."""

    routes: dict = {}

    def do_GET(self):  # noqa: N802 (stdlib casing)
        route = type(self).routes.get(self.path)
        if route is None:
            self.send_response(404)
            self.end_headers()
            return
        status, headers, body = route
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
        if "Content-Length" not in headers:
            self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def log_message(self, *args):  # noqa: A002 (stdlib override)
        pass


class _Server:
    def __init__(self):
        self._httpd = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), _FixtureHandler
        )
        self.port = self._httpd.server_address[1]
        self.thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self._httpd.shutdown()
        self._httpd.server_close()


def _setup_routes(server: _Server) -> None:
    base = f"http://127.0.0.1:{server.port}"
    _FixtureHandler.routes = {
        "/html": (
            200,
            {"Content-Type": "text/html; charset=utf-8"},
            b"<html><body><h1>Hello</h1><p>world <b>bold</b></p></body></html>",
        ),
        "/text": (200, {"Content-Type": "text/plain"}, b"plain text body"),
        "/gbk": (
            200,
            {"Content-Type": "text/html; charset=gbk"},
            "你好，世界".encode("gbk"),
        ),
        "/json": (200, {"Content-Type": "application/json"}, b'{"ok": true}'),
        "/binary": (200, {"Content-Type": "application/octet-stream"}, b"\x89PNG"),
        "/too-large": (
            200,
            {"Content-Type": "text/plain", "Content-Length": "6000000"},
            b"x",
        ),
        "/redirect-same": (
            302,
            {"Location": f"{base}/html"},
            b"",
        ),
        "/redirect-cross": (
            302,
            {"Location": "http://example.com/other"},
            b"",
        ),
        "/redirect-loop": (
            302,
            {"Location": f"{base}/redirect-loop"},
            b"",
        ),
        "/redirect-missing-location": (302, {}, b""),
    }


def test_validate_fetch_url_rejects_bad_urls():
    ok, _ = validate_fetch_url("ftp://example.com/file")
    assert ok is False
    ok, _ = validate_fetch_url("http://user:pass@example.com/")
    assert ok is False
    ok, _ = validate_fetch_url("http://example.com:8080/path")
    assert ok is True
    ok, _ = validate_fetch_url("https://example.com")
    assert ok is True
    ok, _ = validate_fetch_url("http://example.com/" + "a" * 3000)
    assert ok is False


def test_classify_content_type():
    assert classify_content_type("text/html; charset=utf-8") == "html"
    assert classify_content_type("application/xhtml+xml") == "html"
    assert classify_content_type("text/plain") == "text"
    assert classify_content_type("application/json") == "text"
    assert classify_content_type("application/xml") == "text"
    assert classify_content_type("image/png") is None
    assert classify_content_type("application/pdf") is None
    assert classify_content_type(None) is None


def test_decode_body_respects_declared_charset():
    text, truncated = decode_body("你好".encode("gbk"), "gbk", 1000)
    assert text == "你好"
    assert truncated is False


def test_decode_body_detects_without_charset():
    # No declared charset: the GBK bytes must still decode via detection.
    text, _ = decode_body("你好".encode("gbk"), None, 1000)
    assert text == "你好"


def test_decode_body_truncates_at_char_cap():
    text, truncated = decode_body(b"a" * 500, "utf-8", 100)
    assert truncated is True
    assert len(text) == 100


def test_fetch_html():
    with _Server() as server:
        _setup_routes(server)
        base = f"http://127.0.0.1:{server.port}"
        outcome = fetch_url(f"{base}/html")
    assert outcome.ok is True
    assert outcome.kind == "html"
    assert "<h1>Hello</h1>" in outcome.text
    assert outcome.status_code == 200


def test_fetch_text_and_json_kinds():
    with _Server() as server:
        _setup_routes(server)
        base = f"http://127.0.0.1:{server.port}"
        text_outcome = fetch_url(f"{base}/text")
        json_outcome = fetch_url(f"{base}/json")
    assert text_outcome.ok and text_outcome.kind == "text"
    assert text_outcome.text == "plain text body"
    assert json_outcome.ok and json_outcome.kind == "text"
    assert '"ok": true' in json_outcome.text


def test_fetch_gbk_charset():
    with _Server() as server:
        _setup_routes(server)
        base = f"http://127.0.0.1:{server.port}"
        outcome = fetch_url(f"{base}/gbk")
    assert outcome.ok is True
    assert "你好，世界" in outcome.text


def test_fetch_rejects_binary_content_type():
    with _Server() as server:
        _setup_routes(server)
        base = f"http://127.0.0.1:{server.port}"
        outcome = fetch_url(f"{base}/binary")
    assert outcome.ok is False
    assert "不支持的内容类型" in outcome.error


def test_fetch_rejects_declared_oversized_body():
    with _Server() as server:
        _setup_routes(server)
        base = f"http://127.0.0.1:{server.port}"
        outcome = fetch_url(f"{base}/too-large")
    assert outcome.ok is False
    assert "超过最大限制" in outcome.error


def test_fetch_follows_same_host_redirect():
    with _Server() as server:
        _setup_routes(server)
        base = f"http://127.0.0.1:{server.port}"
        outcome = fetch_url(f"{base}/redirect-same")
    assert outcome.ok is True
    assert outcome.final_url.endswith("/html")
    assert "Hello" in outcome.text


def test_fetch_refuses_cross_host_redirect():
    with _Server() as server:
        _setup_routes(server)
        base = f"http://127.0.0.1:{server.port}"
        outcome = fetch_url(f"{base}/redirect-cross")
    assert outcome.ok is False
    assert "跨主机重定向被拒绝" in outcome.error


def test_fetch_stops_at_redirect_cap():
    with _Server() as server:
        _setup_routes(server)
        base = f"http://127.0.0.1:{server.port}"
        outcome = fetch_url(f"{base}/redirect-loop")
    assert outcome.ok is False
    assert "重定向次数超过上限" in outcome.error


def test_fetch_rejects_missing_redirect_location():
    with _Server() as server:
        _setup_routes(server)
        base = f"http://127.0.0.1:{server.port}"
        outcome = fetch_url(f"{base}/redirect-missing-location")
    assert outcome.ok is False
    assert "缺少 Location" in outcome.error


def test_fetch_invalid_scheme_is_an_error():
    outcome = fetch_url("file:///etc/passwd")
    assert outcome.ok is False
    assert "不支持的协议" in outcome.error


if __name__ == "__main__":
    # Minimal runner for dependency-light local verification.
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
