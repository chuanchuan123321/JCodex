"""WebSearch tool - Real-time web search using Exa API"""

import os
from dataclasses import dataclass
from typing import Any

import requests


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
    """Web search tool using Exa AI API"""

    def __init__(self):
        self.api_key = os.getenv("EXA_API_KEY") or os.getenv("TAVILY_API_KEY")
        self.default_num_results = 8

    def execute(
        self,
        query: str,
        num_results: int | None = None,
        livecrawl: str = "fallback",
        search_type: str = "auto",
    ) -> WebSearchResult:
        """Execute web search

        Args:
            query: Search query
            num_results: Number of results to return (default: 8)
            livecrawl: 'fallback' or 'preferred' for live crawling
            search_type: 'auto', 'fast', or 'deep'

        Returns:
            WebSearchResult with search results
        """
        if not self.api_key:
            return WebSearchResult(
                success=False,
                results="",
                error="Please set EXA_API_KEY or TAVILY_API_KEY in environment variables",
            )

        if not query:
            return WebSearchResult(
                success=False, results="", error="query parameter required"
            )

        num_results = num_results or self.default_num_results

        try:
            # Try Exa API first
            return self._search_exa(query, num_results, livecrawl, search_type)
        except Exception:
            # Fallback to Tavily
            return self._search_tavily(query, num_results)

    def _search_exa(
        self, query: str, num_results: int, livecrawl: str, search_type: str
    ) -> WebSearchResult:
        """Search using Exa API"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "query": query,
            "num_results": num_results,
            "livecrawl": livecrawl,
            "type": search_type,
        }

        response = requests.post(
            "https://api.exa.ai/search", headers=headers, json=payload, timeout=30
        )
        response.raise_for_status()

        data = response.json()

        results = []
        results.append(f"Search results for: {query}\n")

        for i, item in enumerate(data.get("results", []), 1):
            title = item.get("title", "Untitled")
            url = item.get("url", "")
            content = item.get("content", "")[:300]

            results.append(f"{i}. {title}")
            results.append(f"   URL: {url}")
            image = item.get("image") or ""
            if image:
                results.append(f"   图片: ![image]({image})")
            if content:
                results.append(f"   {content}...")
            results.append("")

        if not results:
            return WebSearchResult(
                success=True, results=f"No results found for: {query}"
            )

        return WebSearchResult(success=True, results="\n".join(results))

    def _search_tavily(self, query: str, num_results: int) -> WebSearchResult:
        """Search using Tavily API as fallback"""
        headers = {"Content-Type": "application/json"}

        payload = {
            "api_key": self.api_key,
            "query": query,
            "include_answer": True,
            "include_images": True,
            "max_results": num_results,
        }

        response = requests.post(
            "https://api.tavily.com/search", headers=headers, json=payload, timeout=30
        )
        response.raise_for_status()

        data = response.json()

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

        # Include query-related images (top-level list plus per-result images)
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
def get_websearch_tool_definition() -> dict[str, Any]:
    """Get tool definition in OpenAI function calling format"""
    return {
        "type": "function",
        "function": {
            "name": "websearch",
            "description": "Search the web using Exa AI - performs real-time web searches and can scrape content from specific URLs. Provides up-to-date information for current events and recent data. Supports configurable result counts, returns the content from the most relevant websites, and includes related image links when available.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Websearch query"},
                    "numResults": {
                        "type": "integer",
                        "description": "Number of search results to return (default: 8)",
                    },
                    "livecrawl": {
                        "type": "string",
                        "enum": ["fallback", "preferred"],
                        "description": "Live crawl mode - 'fallback': use live crawling as backup if cached unavailable, 'preferred': prioritize live crawling (default: 'fallback')",
                    },
                    "type": {
                        "type": "string",
                        "enum": ["auto", "fast", "deep"],
                        "description": "Search type - 'auto': balanced search (default), 'fast': quick results, 'deep': comprehensive search",
                    },
                },
                "required": ["query"],
            },
        },
    }


def execute_websearch(params: dict[str, Any]) -> str:
    """Execute websearch tool"""
    tool = WebSearchTool()
    query = params.get("query", "")

    if not query:
        return "Error: query parameter required"

    num_results = params.get("numResults")
    livecrawl = params.get("livecrawl", "fallback")
    search_type = params.get("type", "auto")

    result = tool.execute(query, num_results, livecrawl, search_type)

    if result.success:
        return result.results
    return f"Error: {result.error}"
