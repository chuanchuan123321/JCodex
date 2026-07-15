"""CodeSearch tool - Search and get relevant context for programming tasks using Exa Code API"""

import os
import requests
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class CodeSearchResult:
    success: bool
    results: str
    error: str = ""


class CodeSearchTool:
    """Code search tool using Exa Code API for programming-related queries"""

    def __init__(self):
        self.api_key = os.getenv("EXA_API_KEY")
        self.default_tokens = 5000

    def execute(self, query: str, tokens_num: Optional[int] = None) -> CodeSearchResult:
        """Execute code search

        Args:
            query: Search query to find relevant context for APIs, Libraries, and SDKs
            tokens_num: Number of tokens to return (1000-50000). Default: 5000

        Returns:
            CodeSearchResult with code examples and documentation
        """
        if not self.api_key:
            return CodeSearchResult(
                success=False,
                results="",
                error="EXA_API_KEY not found in environment variables",
            )

        if not query:
            return CodeSearchResult(
                success=False, results="", error="query parameter required"
            )

        tokens_num = tokens_num or self.default_tokens
        tokens_num = max(1000, min(50000, tokens_num))  # Clamp to valid range

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            payload = {"query": query, "type": "code", "num_tokens": tokens_num}

            response = requests.post(
                "https://api.exa.ai/search", headers=headers, json=payload, timeout=30
            )
            response.raise_for_status()

            data = response.json()

            results = []
            results.append(f"Code search results for: {query}\n")

            for i, item in enumerate(data.get("results", []), 1):
                title = item.get("title", "Untitled")
                url = item.get("url", "")
                content = item.get("content", "")

                results.append(f"--- Result {i} ---")
                results.append(f"Title: {title}")
                results.append(f"URL: {url}")
                results.append(f"\n{content}")
                results.append("")

            if len(results) == 1:
                return CodeSearchResult(
                    success=True, results=f"No code examples found for: {query}"
                )

            return CodeSearchResult(success=True, results="\n".join(results))

        except requests.exceptions.RequestException as e:
            return CodeSearchResult(
                success=False, results="", error=f"API request failed: {str(e)}"
            )
        except Exception as e:
            return CodeSearchResult(success=False, results="", error=f"Error: {str(e)}")


# Tool definition for OpenAI function calling
def get_codesearch_tool_definition() -> Dict[str, Any]:
    """Get tool definition in OpenAI function calling format"""
    return {
        "type": "function",
        "function": {
            "name": "codesearch",
            "description": "Search and get relevant context for any programming task using Exa Code API. Provides the highest quality and freshest context for libraries, SDKs, and APIs. Returns comprehensive code examples, documentation, and API references. Optimized for finding specific programming patterns and solutions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query to find relevant context for APIs, Libraries, and SDKs. For example: 'React useState hook examples', 'Python pandas dataframe filtering', 'Express.js middleware', 'Next js partial prerendering configuration'",
                    },
                    "tokensNum": {
                        "type": "integer",
                        "description": "Number of tokens to return (1000-50000). Default 5000 tokens provides balanced context for most queries. Adjust this value based on how much context you need - use lower values for focused queries and higher values for comprehensive documentation.",
                    },
                },
                "required": ["query"],
            },
        },
    }


def execute_codesearch(params: Dict[str, Any]) -> str:
    """Execute codesearch tool"""
    tool = CodeSearchTool()
    query = params.get("query", "")

    if not query:
        return "Error: query parameter required"

    tokens_num = params.get("tokensNum")

    result = tool.execute(query, tokens_num)

    if result.success:
        return result.results
    else:
        return f"Error: {result.error}"
