"""Glob tool - Fast file pattern matching"""

import os
import fnmatch
from pathlib import Path
from typing import Dict, Any, List
from dataclasses import dataclass


@dataclass
class GlobResult:
    success: bool
    files: List[str]
    error: str = ""


class GlobTool:
    """Fast file pattern matching tool"""

    DEFAULT_LIMIT = 100

    def __init__(self, max_results: int = 100):
        self.max_results = max_results

    def execute(self, pattern: str, path: str = ".") -> GlobResult:
        """Execute glob pattern matching

        Args:
            pattern: Glob pattern (e.g., "**/*.py", "src/**/*.ts")
            path: Directory to search in (default: current directory)

        Returns:
            GlobResult with list of matching files
        """
        try:
            search_path = Path(path).resolve()

            if not search_path.exists():
                return GlobResult(
                    success=False, files=[], error=f"Path does not exist: {path}"
                )

            if not search_path.is_dir():
                return GlobResult(
                    success=False, files=[], error=f"Path is not a directory: {path}"
                )

            # Use recursive glob for ** patterns
            if "**" in pattern:
                all_files = []
                for root, dirs, files in os.walk(search_path):
                    # Skip hidden directories
                    dirs[:] = [d for d in dirs if not d.startswith(".")]

                    for filename in files:
                        if not filename.startswith("."):
                            rel_path = os.path.join(root, filename)
                            rel_pattern = os.path.relpath(rel_path, search_path)

                            # Convert path to pattern format for matching
                            pattern_for_match = pattern.replace("**/", "").replace(
                                "**", ""
                            )
                            if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(
                                rel_pattern, pattern
                            ):
                                all_files.append(rel_path)

                files = all_files[: self.max_results]
            else:
                # Simple glob
                files = [
                    str(p.relative_to(search_path)) for p in search_path.glob(pattern)
                ]
                files = sorted(files)[: self.max_results]

            return GlobResult(success=True, files=files)

        except Exception as e:
            return GlobResult(success=False, files=[], error=str(e))

    def format_result(self, result: GlobResult) -> str:
        """Format result for display"""
        if not result.success:
            return f"Error: {result.error}"

        if not result.files:
            return f"No files found matching pattern"

        files_list = "\n".join(result.files)
        count = len(result.files)
        return f"Found {count} files:\n{files_list}"


# Tool definition for OpenAI function calling
def get_glob_tool_definition() -> Dict[str, Any]:
    """Get tool definition in OpenAI function calling format"""
    return {
        "type": "function",
        "function": {
            "name": "glob",
            "description": 'Fast file pattern matching tool that works with any codebase size. Supports glob patterns like "**/*.js" or "src/**/*.ts". Returns matching file paths sorted by modification time. Use this tool when you need to find files by name patterns.',
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "The glob pattern to match files against (e.g., '**/*.py', 'src/**/*.ts')",
                    },
                    "path": {
                        "type": "string",
                        "description": "The directory to search in (defaults to current directory)",
                    },
                },
                "required": ["pattern"],
            },
        },
    }


def execute_glob(params: Dict[str, Any]) -> str:
    """Execute glob tool"""
    tool = GlobTool()
    pattern = params.get("pattern", "")
    path = params.get("path", ".")

    if not pattern:
        return "Error: pattern parameter required"

    result = tool.execute(pattern, path)
    return tool.format_result(result)
