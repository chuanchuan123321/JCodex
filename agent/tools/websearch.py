"""WebSearch tool - Real-time web search using the Tavily API."""

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests

TAVILY_ENDPOINT = "https://api.tavily.com/search"
#: Transient network failures (reset/timeout) are retried once before giving up.
RETRY_ATTEMPTS = 2
RETRY_DELAY_S = 0.5


def _normalize_image_items(image_items: Any) -> list:
    """Normalize image entries (URL strings or {url, description} dicts) to (url, description) pairs."""
    normalized = []
    seen = set()
    for item in image_items or []:
        if isinstance(item, dict):
            url = str(item.get("url") or "").strip()
            description = str(item.get("description") or "").strip()
        elif isinstance(item, str):
            url = item.strip()
            description = ""
        else:
            continue
        if url and url not in seen:
            seen.add(url)
            normalized.append((url, description))
    return normalized


def _format_image_links(images: list, limit: int = 8) -> list:
    """Render image (url, description) pairs as Markdown image links, capped at limit."""
    lines = []
    for index, (url, description) in enumerate(images[:limit], 1):
        alt = (description or f"image {index}").replace("]", "\\]")
        lines.append(f"![{alt}]({url})")
    return lines


@dataclass
class WebSearchResult:
    success: bool
    results: str
    error: str = ""


class WebSearchTool:
    """Web search tool using the Tavily API."""

    def __init__(self):
        self.api_key = os.getenv("TAVILY_API_KEY")
        self.default_num_results = 8

    def execute(
        self,
        query: str,
        num_results: Optional[int] = None,
        include_images: Optional[bool] = None,
    ) -> WebSearchResult:
        """Execute a Tavily web search.

        Args:
            query: The search query.
            num_results: Number of results to return (default 8).
            include_images: Whether to request related images. Defaults to
                False; the caller opts in when visual context is relevant.
        """
        if not self.api_key:
            return WebSearchResult(
                success=False,
                results="",
                error="Please set TAVILY_API_KEY in environment variables",
            )

        if not query:
            return WebSearchResult(
                success=False, results="", error="query parameter required"
            )

        num_results = num_results or self.default_num_results
        return self._search_tavily(query, num_results, bool(include_images))

    def _search_tavily(
        self, query: str, num_results: int, include_images: bool = False
    ) -> WebSearchResult:
        """Search using the Tavily API."""
        headers = {"Content-Type": "application/json"}

        payload = {
            "api_key": self.api_key,
            "query": query,
            "include_answer": True,
            "include_images": include_images,
            "max_results": num_results,
        }

        response = None
        last_error = ""
        for attempt in range(RETRY_ATTEMPTS):
            try:
                response = requests.post(
                    TAVILY_ENDPOINT, headers=headers, json=payload, timeout=30
                )
                response.raise_for_status()
                break
            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response is not None else None
                if status in (401, 403):
                    return WebSearchResult(
                        success=False,
                        results="",
                        error="Tavily API key 无效或未授权，请检查 TAVILY_API_KEY",
                    )
                if status == 429:
                    return WebSearchResult(
                        success=False,
                        results="",
                        error="Tavily 请求过于频繁，请稍后重试",
                    )
                return WebSearchResult(
                    success=False,
                    results="",
                    error=f"Tavily API 错误 (HTTP {status})",
                )
            except requests.exceptions.ConnectionError:
                # TCP-level failure (e.g. "Connection reset by peer") — transient
                # network trouble, retried once before giving up.
                last_error = "网络连接失败（连接被重置），请检查网络或代理后重试"
                time.sleep(RETRY_DELAY_S)
            except requests.exceptions.Timeout:
                last_error = "网络请求超时，请检查网络或代理后重试"
                time.sleep(RETRY_DELAY_S)
        if response is None:
            return WebSearchResult(
                success=False, results="", error=last_error or "网络请求失败"
            )

        try:
            data = response.json()
        except ValueError:
            return WebSearchResult(
                success=False, results="", error="Tavily 返回了无法解析的响应"
            )

        results = []
        results.append(f"Search results for: {query}\n")

        # Add answer if available
        if data.get("answer"):
            results.append(f"Answer: {data['answer']}\n")

        # Add search results
        for i, item in enumerate(data.get("results", []), 1):
            title = item.get("title", "Untitled")
            url = item.get("url", "")
            content = item.get("content", "")[:300]

            results.append(f"{i}. {title}")
            results.append(f"   URL: {url}")
            if content:
                results.append(f"   {content}...")
            results.append("")

        # Include query-related images (top-level list plus per-result images),
        # only when the caller requested them.
        if include_images:
            image_items = list(data.get("images") or [])
            for item in data.get("results", []):
                image_items.extend(item.get("images") or [])

            images = _normalize_image_items(image_items)
            if images:
                results.append("相关图片：")
                results.extend(_format_image_links(images))
                results.append("")

        if len(results) == 1:
            return WebSearchResult(
                success=True, results=f"No results found for: {query}"
            )

        return WebSearchResult(success=True, results="\n".join(results))


# Tool definition for OpenAI function calling
def get_websearch_tool_definition() -> Dict[str, Any]:
    """Get tool definition in OpenAI function calling format"""
    return {
        "type": "function",
        "function": {
            "name": "websearch",
            "description": (
                "Search the public web for current or unknown information using the "
                "Tavily API. Returns an optional summary answer plus a list of source "
                "URLs with snippets. Set include_images to true only when the query is "
                "about visuals (images, logos, photos, products) — images are related "
                "links with little or no description, so they cost tokens without "
                "adding much to text-only questions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Websearch query"},
                    "numResults": {
                        "type": "integer",
                        "description": "Number of search results to return (default: 8)",
                    },
                    "include_images": {
                        "type": "boolean",
                        "description": "Whether to include related image links in the results (default: false)",
                    },
                },
                "required": ["query"],
            },
        },
    }


def execute_websearch(params: Dict[str, Any]) -> str:
    """Execute websearch tool"""
    tool = WebSearchTool()
    query = params.get("query", "")

    if not query:
        return "Error: query parameter required"

    num_results = params.get("numResults")
    include_images = params.get("include_images")

    result = tool.execute(query, num_results, include_images)

    if result.success:
        return result.results
    else:
        return f"Error: {result.error}"
