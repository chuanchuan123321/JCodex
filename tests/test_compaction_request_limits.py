"""Regression tests for the dedicated compaction request budget."""

import pytest

from agent.core.ai_engine import AIEngine
from agent.ui.desktop.main import DesktopTaskExecutor


def test_call_messages_forwards_request_limits() -> None:
    engine = object.__new__(AIEngine)
    captured = {}

    def post(messages, **kwargs):
        captured["messages"] = messages
        captured.update(kwargs)
        return {"content": "ok", "tool_calls": [], "finish_reason": "stop"}

    engine._post_chat_completion = post

    result = engine.call_messages(
        [{"role": "user", "content": "summarize"}],
        max_tokens=8_000,
        timeout=300,
        max_retries=1,
    )

    assert result["content"] == "ok"
    assert captured["max_tokens"] == 8_000
    assert captured["timeout"] == 300
    assert captured["max_retries"] == 1


def test_compaction_rejects_length_limited_summary(monkeypatch) -> None:
    class FakeEngine:
        def __init__(self) -> None:
            self.calls = []

        def call_messages(self, messages, **kwargs):
            self.calls.append((messages, kwargs))
            return {
                "content": "incomplete continuation summary",
                "finish_reason": "length",
            }

    monkeypatch.setenv("COMPACTION_TIMEOUT_SECONDS", "300")
    executor = object.__new__(DesktopTaskExecutor)
    executor.ai_engine = FakeEngine()

    with pytest.raises(RuntimeError, match="incomplete continuation summary"):
        executor._sample_compaction_prompt("compress this")

    _messages, request = executor.ai_engine.calls[0]
    assert "max_tokens" not in request
    assert request["timeout"] == 300
    assert request["max_retries"] == 1


def test_memory_flush_uses_its_own_smaller_budget(monkeypatch) -> None:
    class FakeEngine:
        def __init__(self) -> None:
            self.calls = []

        def call_messages(self, messages, **kwargs):
            self.calls.append((messages, kwargs))
            return {"content": "## Durable facts\n- retained", "finish_reason": "stop"}

    monkeypatch.setenv("MEMORY_FLUSH_TIMEOUT_SECONDS", "180")
    executor = object.__new__(DesktopTaskExecutor)
    executor.ai_engine = FakeEngine()

    assert executor._sample_memory_flush([{"role": "user", "content": "task"}])
    _messages, request = executor.ai_engine.calls[0]
    assert "max_tokens" not in request
    assert request["timeout"] == 180
    assert request["max_retries"] == 1
