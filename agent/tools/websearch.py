"""WebSearch tool - Real-time web search using Exa API"""

import os
import requests
from typing import Dict, Any, Optional
from dataclasses import dataclass


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
        num_results: Optional[int] = None,
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
        except Exception as e:
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
            "description": "Search the web using Exa AI - performs real-time web searches and can scrape content from specific URLs. Provides up-to-date information for current events and recent data. Supports configurable result counts and returns the content from the most relevant websites.",
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


def execute_websearch(params: Dict[str, Any]) -> str:
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
    else:
        return f"Error: {result.error}"
