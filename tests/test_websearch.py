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

    result = tool._search_tavily("red car", 5)

    assert captured["url"] == "https://api.tavily.com/search"
    assert captured["payload"]["include_images"] is True
    assert captured["payload"]["query"] == "red car"
    assert "相关图片：" in result.results
    assert "![image 1](https://example.com/top-1.png)" in result.results
    assert "![Red car front](https://example.com/result-1.png)" in result.results
    assert "![image 3](https://example.com/result-2.png)" in result.results


def test_search_exa_includes_result_image(monkeypatch) -> None:
    def fake_post(url, headers=None, json=None, timeout=None):
        return _FakeResponse(
            {
                "results": [
                    {
                        "title": "Exa Page",
                        "url": "https://example.com/exa",
                        "content": "Page content.",
                        "image": "https://example.com/exa-image.png",
                    }
                ]
            }
        )

    monkeypatch.setattr(websearch.requests, "post", fake_post)
    tool = WebSearchTool()
    tool.api_key = "exa-test"

    result = tool._search_exa("query", 5, "fallback", "auto")

    assert "图片: ![image](https://example.com/exa-image.png)" in result.results


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
