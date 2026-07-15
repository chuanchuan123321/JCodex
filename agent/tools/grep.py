"""Grep tool - Fast content search using regular expressions"""

import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class GrepMatch:
    file_path: str
    line_number: int
    line_content: str


@dataclass
class GrepResult:
    success: bool
    matches: List[GrepMatch]
    total_files: int
    error: str = ""


class GrepTool:
    """Fast content search tool using regular expressions"""

    DEFAULT_LIMIT = 50

    def __init__(self, max_matches: int = 50):
        self.max_matches = max_matches

    def execute(
        self,
        pattern: str,
        path: str = ".",
        include: Optional[str] = None,
    ) -> GrepResult:
        """Execute grep pattern search

        Args:
            pattern: Regular expression pattern to search for
            path: Directory to search in (default: current directory)
            include: File pattern to include (e.g., "*.py", "*.{ts,tsx}")

        Returns:
            GrepResult with list of matches
        """
        try:
            search_path = Path(path).resolve()

            if not search_path.exists():
                return GrepResult(
                    success=False,
                    matches=[],
                    total_files=0,
                    error=f"Path does not exist: {path}",
                )

            # Compile regex
            try:
                regex = re.compile(pattern)
            except re.error as e:
                return GrepResult(
                    success=False,
                    matches=[],
                    total_files=0,
                    error=f"Invalid regex pattern: {e}",
                )

            matches: List[GrepMatch] = []
            files_with_matches: set = set()

            # Walk through directory
            for root, dirs, files in os.walk(search_path):
                # Skip hidden directories and common ignore patterns
                dirs[:] = [
                    d
                    for d in dirs
                    if not d.startswith(".")
                    and d
                    not in ("node_modules", "__pycache__", ".git", "venv", ".venv")
                ]

                for filename in files:
                    # Skip hidden files
                    if filename.startswith("."):
                        continue

                    # Filter by include pattern if specified
                    if include and not self._matches_glob(filename, include):
                        continue

                    # Skip binary files
                    if self._is_binary(filename):
                        continue

                    filepath = os.path.join(root, filename)
                    rel_path = os.path.relpath(filepath, search_path)

                    # Search in file
                    try:
                        with open(
                            filepath, "r", encoding="utf-8", errors="ignore"
                        ) as f:
                            for line_num, line in enumerate(f, 1):
                                if regex.search(line):
                                    matches.append(
                                        GrepMatch(
                                            file_path=rel_path,
                                            line_number=line_num,
                                            line_content=line.rstrip(),
                                        )
                                    )
                                    files_with_matches.add(rel_path)

                                    if len(matches) >= self.max_matches:
                                        return GrepResult(
                                            success=True,
                                            matches=matches,
                                            total_files=len(files_with_matches),
                                        )
                    except Exception:
                        continue

            return GrepResult(
                success=True, matches=matches, total_files=len(files_with_matches)
            )

        except Exception as e:
            return GrepResult(success=False, matches=[], total_files=0, error=str(e))

    def _matches_glob(self, filename: str, pattern: str) -> bool:
        """Check if filename matches glob pattern"""
        import fnmatch

        # Handle multiple patterns like "*.{py,js}"
        patterns = pattern.replace("{", ",").replace("}", ",").split(",")
        return any(fnmatch.fnmatch(filename, p.strip()) for p in patterns if p.strip())

    def _is_binary(self, filename: str) -> bool:
        """Check if file is likely binary"""
        binary_exts = {
            ".pyc",
            ".pyo",
            ".so",
            ".dll",
            ".dylib",
            ".exe",
            ".bin",
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".bmp",
            ".ico",
            ".svg",
            ".pdf",
            ".doc",
            ".docx",
            ".xls",
            ".xlsx",
            ".ppt",
            ".pptx",
            ".zip",
            ".tar",
            ".gz",
            ".rar",
            ".7z",
            ".mp3",
            ".mp4",
            ".wav",
            ".avi",
            ".mov",
            ".ttf",
            ".otf",
            ".woff",
            ".woff2",
        }
        return Path(filename).suffix.lower() in binary_exts

    def format_result(self, result: GrepResult) -> str:
        """Format result for display"""
        if not result.success:
            return f"Error: {result.error}"

        if not result.matches:
            return f"No matches found"

        # Group by file
        by_file: Dict[str, List[GrepMatch]] = {}
        for match in result.matches:
            if match.file_path not in by_file:
                by_file[match.file_path] = []
            by_file[match.file_path].append(match)

        lines = [
            f"Found {result.total_files} files with {len(result.matches)} matches:"
        ]

        for filepath, matches in by_file.items():
            lines.append(f"\n{filepath}:")
            for match in matches[:5]:  # Show first 5 matches per file
                # Truncate long lines
                content = match.line_content[:100]
                if len(match.line_content) > 100:
                    content += "..."
                lines.append(f"  {match.line_number}: {content}")
            if len(matches) > 5:
                lines.append(f"  ... and {len(matches) - 5} more matches")

        return "\n".join(lines)


# Tool definition for OpenAI function calling
def get_grep_tool_definition() -> Dict[str, Any]:
    """Get tool definition in OpenAI function calling format"""
    return {
        "type": "function",
        "function": {
            "name": "grep",
            "description": "Fast content search tool that works with any codebase size. Searches file contents using regular expressions. Supports full regex syntax. Returns file paths and line numbers with at least one match sorted by modification time. Use grep to find specific code patterns, function definitions, or any text within files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "The regex pattern to search for in file contents",
                    },
                    "path": {
                        "type": "string",
                        "description": "The directory to search in (defaults to current directory)",
                    },
                    "include": {
                        "type": "string",
                        "description": "File pattern to include (e.g., '*.py', '*.{ts,tsx}')",
                    },
                },
                "required": ["pattern"],
            },
        },
    }


def execute_grep(params: Dict[str, Any]) -> str:
    """Execute grep tool"""
    tool = GrepTool()
    pattern = params.get("pattern", "")
    path = params.get("path", ".")
    include = params.get("include")

    if not pattern:
        return "Error: pattern parameter required"

    result = tool.execute(pattern, path, include)
    return tool.format_result(result)
