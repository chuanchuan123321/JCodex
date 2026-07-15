"""Edit tool - Smart file editing with multiple matching strategies"""

import os
from pathlib import Path
from typing import Dict, Any, Optional, List, Generator
from dataclasses import dataclass


@dataclass
class EditResult:
    success: bool
    message: str
    diff: str = ""


def normalize_line_endings(text: str) -> str:
    """Normalize line endings to LF"""
    return text.replace("\r\n", "\n")


class EditTool:
    """Smart file editing tool with multiple matching strategies"""

    def __init__(self):
        self.base_dir = Path.cwd()

    def execute(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> EditResult:
        """Execute edit operation

        Args:
            file_path: Path to the file to modify
            old_string: The text to replace
            new_string: The text to replace it with
            replace_all: Replace all occurrences (default: False)

        Returns:
            EditResult with success status and message
        """
        try:
            # Resolve path
            filepath = Path(file_path)
            if not filepath.is_absolute():
                filepath = self.base_dir / filepath
            filepath = filepath.resolve()

            if not filepath.exists():
                return EditResult(success=False, message=f"File not found: {file_path}")

            if filepath.is_dir():
                return EditResult(
                    success=False,
                    message=f"Path is a directory, not a file: {file_path}",
                )

            # Read current content
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            content = normalize_line_endings(content)

            if old_string == new_string:
                return EditResult(
                    success=False,
                    message="No changes to apply: oldString and newString are identical.",
                )

            # Try multiple replacement strategies
            new_content = self._replace(content, old_string, new_string, replace_all)

            if new_content is None:
                # No match found
                return EditResult(
                    success=False,
                    message="Could not find oldString in the file. It must match exactly, including whitespace, indentation, and line endings.",
                )

            if new_content == content:
                return EditResult(
                    success=False,
                    message="No changes made - oldString not found or identical to newString",
                )

            # Generate diff
            diff = self._generate_diff(content, new_content, str(filepath))

            # Write new content
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(new_content)

            return EditResult(
                success=True, message="Edit applied successfully.", diff=diff
            )

        except Exception as e:
            return EditResult(success=False, message=f"Error: {str(e)}")

    def _replace(
        self, content: str, old_string: str, new_string: str, replace_all: bool
    ) -> Optional[str]:
        """Try multiple replacement strategies"""

        # Strategy 1: Simple exact match
        if old_string in content:
            if replace_all:
                return content.replace(old_string, new_string)
            # Replace only the last occurrence
            idx = content.rfind(old_string)
            if idx != -1:
                return content[:idx] + new_string + content[idx + len(old_string) :]

        # Strategy 2: Line-trimmed match
        result = self._line_trimmed_replace(
            content, old_string, new_string, replace_all
        )
        if result:
            return result

        # Strategy 3: Whitespace normalized
        result = self._whitespace_normalized_replace(
            content, old_string, new_string, replace_all
        )
        if result:
            return result

        return None

    def _line_trimmed_replace(
        self, content: str, old_string: str, new_string: str, replace_all: bool
    ) -> Optional[str]:
        """Try matching with trimmed lines"""
        old_lines = old_string.split("\n")
        content_lines = content.split("\n")

        for i in range(len(content_lines) - len(old_lines) + 1):
            matches = True
            for j in range(len(old_lines)):
                if content_lines[i + j].strip() != old_lines[j].strip():
                    matches = False
                    break

            if matches:
                # Build new content
                new_lines = (
                    content_lines[:i]
                    + new_string.split("\n")
                    + content_lines[i + len(old_lines) :]
                )
                return "\n".join(new_lines)

        return None

    def _whitespace_normalized_replace(
        self, content: str, old_string: str, new_string: str, replace_all: bool
    ) -> Optional[str]:
        """Try matching with normalized whitespace"""
        normalize = lambda t: " ".join(t.split())

        normalized_old = normalize(old_string)

        if normalize(content).find(normalized_old) == -1:
            return None

        # Find and replace with normalized matching
        lines = content.split("\n")
        result_lines = []
        i = 0
        replaced = False

        while i < len(lines):
            if normalize(lines[i]).find(normalized_old) != -1:
                result_lines.append(new_string)
                replaced = True
                if not replace_all:
                    result_lines.extend(lines[i + 1 :])
                    break
            else:
                result_lines.append(lines[i])
            i += 1

        return "\n".join(result_lines) if replaced else None

    def _generate_diff(self, old: str, new: str, filepath: str) -> str:
        """Generate a simple unified diff"""
        old_lines = old.split("\n")
        new_lines = new.split("\n")

        diff_lines = [f"--- {filepath}", f"+++ {filepath}"]

        # Simple diff - show changed lines
        max_len = max(len(old_lines), len(new_lines))

        for i in range(max_len):
            old_line = old_lines[i] if i < len(old_lines) else None
            new_line = new_lines[i] if i < len(new_lines) else None

            if old_line != new_line:
                if old_line is not None:
                    diff_lines.append(f"-{i + 1}: {old_line[:80]}")
                if new_line is not None:
                    diff_lines.append(f"+{i + 1}: {new_line[:80]}")

        return "\n".join(diff_lines[:20])  # Limit diff size


# Tool definition for OpenAI function calling
def get_edit_tool_definition() -> Dict[str, Any]:
    """Get tool definition in OpenAI function calling format"""
    return {
        "type": "function",
        "function": {
            "name": "edit",
            "description": "Performs exact string replacements in files. You MUST use the Read tool at least once in the conversation before editing. When editing text from Read tool output, ensure you preserve the exact indentation (tabs/spaces) as it appears AFTER the line number prefix. The line number prefix format is: line number + colon + space (e.g., `1: `). Everything after that space is the actual file content. ALWAYS prefer editing existing files in the codebase. NEVER write new files unless explicitly required.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filePath": {
                        "type": "string",
                        "description": "The absolute path to the file to modify",
                    },
                    "oldString": {
                        "type": "string",
                        "description": "The text to replace. Must match exactly including whitespace, indentation, and line endings.",
                    },
                    "newString": {
                        "type": "string",
                        "description": "The text to replace it with (must be different from oldString)",
                    },
                    "replaceAll": {
                        "type": "boolean",
                        "description": "Replace all occurrences of oldString (default false)",
                    },
                },
                "required": ["filePath", "oldString", "newString"],
            },
        },
    }


def execute_edit(params: Dict[str, Any]) -> str:
    """Execute edit tool"""
    tool = EditTool()
    file_path = params.get("filePath", "")
    old_string = params.get("oldString", "")
    new_string = params.get("newString", "")
    replace_all = params.get("replaceAll", False)

    if not file_path:
        return "Error: filePath parameter required"
    if not old_string:
        return "Error: oldString parameter required"
    if new_string == old_string:
        return "Error: newString must be different from oldString"

    result = tool.execute(file_path, old_string, new_string, replace_all)

    if result.success:
        output = result.message
        if result.diff:
            output += f"\n\nDiff:\n{result.diff}"
        return output
    else:
        return f"Error: {result.message}"
