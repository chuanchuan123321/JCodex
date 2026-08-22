"""AIEngine local-model support: empty API key on loopback servers."""

from __future__ import annotations

import os

import pytest

from agent.core import ai_engine


def _clear_model_env(monkeypatch):
    for name in ("API_BASE_URL", "API_KEY", "API_MODEL", "MAX_TOKENS", "TEMPERATURE"):
        monkeypatch.delenv(name, raising=False)


def test_local_base_url_allows_empty_api_key(monkeypatch) -> None:
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("API_BASE_URL", "http://127.0.0.1:8080")
    monkeypatch.setenv("API_MODEL", "qwen")
    monkeypatch.setenv("API_KEY", "")

    engine = ai_engine.AIEngine()
    assert engine.api_key == ""
    assert engine.api_base_url == "http://127.0.0.1:8080"


def test_localhost_allows_empty_api_key(monkeypatch) -> None:
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("API_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("API_MODEL", "llama3:8b")
    monkeypatch.delenv("API_KEY", raising=False)

    engine = ai_engine.AIEngine()
    assert engine.api_key is None


@pytest.mark.parametrize(
    "url",
    [
        "https://api.deepseek.com",
        "https://api.openai.com/v1",
        "http://192.168.1.10:8080",
    ],
)
def test_remote_base_url_without_key_constructs_but_fails_on_request(
    monkeypatch, url
) -> None:
    # 新用户首次启动未配置 key 时，初始化不能失败：构造成功，
    # 真正请求时才返回“请先配置”的友好错误。
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("API_BASE_URL", url)
    monkeypatch.delenv("API_KEY", raising=False)

    engine = ai_engine.AIEngine()
    assert engine.api_key is None

    result = engine._post_chat_completion([{"role": "user", "content": "hi"}])
    assert result["finish_reason"] == "error"
    assert "API Key" in result["content"]

    stream_result = engine._post_chat_completion_stream(
        [{"role": "user", "content": "hi"}]
    )
    assert stream_result["finish_reason"] == "error"


class _FakePostResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_request_without_api_key_sends_no_authorization_header(monkeypatch) -> None:
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("API_BASE_URL", "http://127.0.0.1:8080")
    monkeypatch.setenv("API_MODEL", "qwen")
    monkeypatch.delenv("API_KEY", raising=False)

    captured: dict = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["headers"] = headers
        return _FakePostResponse(
            {
                "choices": [
                    {
                        "message": {"content": "ok", "tool_calls": None},
                        "finish_reason": "stop",
                    }
                ]
            }
        )

    monkeypatch.setattr(ai_engine.requests, "post", fake_post)

    engine = ai_engine.AIEngine()
    result = engine._post_chat_completion([{"role": "user", "content": "hi"}])
    assert result["content"] == "ok"
    assert "Authorization" not in captured["headers"]
    assert captured["headers"]["Content-Type"] == "application/json"


def test_request_with_api_key_sends_authorization_header(monkeypatch) -> None:
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("API_BASE_URL", "http://127.0.0.1:8080")
    monkeypatch.setenv("API_MODEL", "qwen")
    monkeypatch.setenv("API_KEY", "sk-local")

    captured: dict = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["headers"] = headers
        return _FakePostResponse(
            {
                "choices": [
                    {
                        "message": {"content": "ok", "tool_calls": None},
                        "finish_reason": "stop",
                    }
                ]
            }
        )

    monkeypatch.setattr(ai_engine.requests, "post", fake_post)

    engine = ai_engine.AIEngine()
    result = engine._post_chat_completion([{"role": "user", "content": "hi"}])
    assert result["content"] == "ok"
    assert captured["headers"]["Authorization"] == "Bearer sk-local"
