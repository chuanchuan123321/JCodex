"""Tests for web search image result handling."""

import agent.tools.websearch as websearch
from agent.tools.websearch import (
    WebSearchTool,
    _format_image_links,
    _normalize_image_items,
)


def test_normalize_image_items_accepts_strings_and_dicts() -> None:
    items = [
        "https://example.com/a.png",
        {"url": "https://example.com/b.png", "description": "A red car"},
        {"url": "https://example.com/a.png"},  # duplicate URL
        "",
        None,
        123,
    ]

    normalized = _normalize_image_items(items)

    assert normalized == [
        ("https://example.com/a.png", ""),
        ("https://example.com/b.png", "A red car"),
    ]


def test_format_image_links_uses_description_and_caps_limit() -> None:
    images = [
        ("https://example.com/a.png", "First"),
        ("https://example.com/b.png", "Second"),
        ("https://example.com/c.png", "Third"),
    ]

    lines = _format_image_links(images, limit=2)

    assert lines == [
        "![First](https://example.com/a.png)",
        "![Second](https://example.com/b.png)",
    ]
    assert _format_image_links([("https://example.com/a.png", "")]) == [
        "![image 1](https://example.com/a.png)"
    ]


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._payload


def test_search_tavily_includes_images_in_payload_and_result(monkeypatch) -> None:
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["payload"] = json
        return _FakeResponse(
            {
                "query": "red car",
                "answer": "Cars come in many colors.",
                "images": ["https://example.com/top-1.png"],
                "results": [
                    {
                        "title": "Car Gallery",
                        "url": "https://example.com/cars",
                        "content": "A gallery of red cars.",
                        "images": [
                            {"url": "https://example.com/result-1.png", "description": "Red car front"}
                        ],
                    },
                    {
                        "title": "Another Car",
                        "url": "https://example.com/more",
                        "content": "More cars.",
                        "images": ["https://example.com/result-2.png"],
                    },
                ],
            }
        )

    monkeypatch.setattr(websearch.requests, "post", fake_post)
    tool = WebSearchTool()
    tool.api_key = "tvly-test"

    result = tool._search_tavily("red car", 5, include_images=True)

    assert captured["url"] == "https://api.tavily.com/search"
    assert captured["payload"]["include_images"] is True
    assert captured["payload"]["query"] == "red car"
    assert "相关图片：" in result.results
    assert "![image 1](https://example.com/top-1.png)" in result.results
    assert "![Red car front](https://example.com/result-1.png)" in result.results
    assert "![image 3](https://example.com/result-2.png)" in result.results


def test_search_tavily_without_images_by_default(monkeypatch) -> None:
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["payload"] = json
        return _FakeResponse(
            {
                "query": "red car",
                "images": ["https://example.com/top-1.png"],
                "results": [
                    {
                        "title": "Car Gallery",
                        "url": "https://example.com/cars",
                        "content": "A gallery of red cars.",
                    }
                ],
            }
        )

    monkeypatch.setattr(websearch.requests, "post", fake_post)
    tool = WebSearchTool()
    tool.api_key = "tvly-test"

    result = tool._search_tavily("red car", 5)

    assert captured["payload"]["include_images"] is False
    assert "相关图片：" not in result.results


def test_execute_goes_directly_to_tavily_without_exa(monkeypatch) -> None:
    # Tavily is the only search provider: execute() must call the Tavily
    # endpoint exactly once and never attempt an Exa request first.
    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append(url)
        return _FakeResponse({"query": "q", "images": [], "results": []})

    monkeypatch.setattr(websearch.requests, "post", fake_post)
    tool = WebSearchTool()
    tool.api_key = "tvly-test"

    result = tool.execute("hello")

    assert calls == ["https://api.tavily.com/search"]
    assert result.success is True


def test_search_tavily_connection_error_is_classified(monkeypatch) -> None:
    # A TCP reset (the reported ConnectionResetError symptom) must surface as a
    # clear network message after one retry, never as a raw exception.
    import requests as requests_module

    def failing_post(url, headers=None, json=None, timeout=None):
        raise requests_module.exceptions.ConnectionError(
            "Connection aborted.", ConnectionResetError(54, "Connection reset by peer")
        )

    monkeypatch.setattr(websearch.requests, "post", failing_post)
    monkeypatch.setattr(websearch.time, "sleep", lambda _s: None)
    tool = WebSearchTool()
    tool.api_key = "tvly-test"

    result = tool._search_tavily("q", 5)

    assert result.success is False
    assert "网络连接失败" in result.error
    assert "连接被重置" in result.error


def test_search_tavily_invalid_key_is_classified(monkeypatch) -> None:
    import requests as requests_module

    def unauthorized_post(url, headers=None, json=None, timeout=None):
        response = requests_module.Response()
        response.status_code = 401
        error = requests_module.exceptions.HTTPError("401 Client Error")
        error.response = response
        raise error

    monkeypatch.setattr(websearch.requests, "post", unauthorized_post)
    tool = WebSearchTool()
    tool.api_key = "tvly-bad"

    result = tool._search_tavily("q", 5)

    assert result.success is False
    assert "API key 无效" in result.error


def test_search_tavily_payload_uses_api_key_from_env(monkeypatch) -> None:
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["payload"] = json
        return _FakeResponse({"query": "q", "images": [], "results": []})

    monkeypatch.setattr(websearch.requests, "post", fake_post)
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-env-test")

    tool = WebSearchTool()

    result = tool._search_tavily("q", 5)

    assert captured["payload"]["api_key"] == "tvly-env-test"
    assert result.success is True
    assert "No results found" in result.results
