"""File operations tool - optimized for token efficiency (OpenCode aligned)"""

import os
import shutil
from typing import List, Tuple, Optional
from pathlib import Path
import subprocess


class FileTool:
    """Tool for file operations - aligned with OpenCode patterns"""

    DEFAULT_READ_LIMIT = 1000
    MAX_READ_TOKENS = 25_000

    IMAGE_EXTENSIONS = {
        ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff",
        ".heic", ".heif", ".avif", ".ico", ".jfif", ".apng", ".psd",
        ".dng", ".cr2", ".nef", ".arw", ".raw", ".exr",
    }

    @staticmethod
    def expand_path(path: str) -> str:
        """Expand path with support for ~, Desktop, Documents, etc."""
        path = path.replace("桌面", "Desktop")
        path = path.replace("文档", "Documents")
        path = path.replace("下载", "Downloads")
        path = os.path.expanduser(path)

        if not os.path.isabs(path):
            path = os.path.join(os.path.expanduser("~"), path)

        return path

    @staticmethod
    def read_file(
        path: str, offset: Optional[int] = None, limit: Optional[int] = None
    ) -> Tuple[bool, str]:
        """Read file contents with Grok Build-compatible pagination.

        Non-skill reads are capped at 1000 lines. The complete selected window
        must also fit Grok Build's 25,000-token estimate; otherwise the model
        receives a range/search instruction instead of a partial file body.

        Args:
            path: File path to read
            offset: Line number to start from (1-indexed, default: 1)
            limit: Maximum number of lines to read (default and maximum: 1000)

        Returns:
            Tuple of (success, content)
            Content uses Grok Build-style sparse line-number anchors.
        """
        try:
            file_path = Path(FileTool.expand_path(path)).resolve()

            if not file_path.exists():
                return False, f"File not found: {path}"

            if file_path.is_dir():
                return FileTool.list_directory(path)

            if file_path.suffix.lower() in FileTool.IMAGE_EXTENSIONS:
                return False, (
                    f"Cannot read image file with the read tool: {file_path.name}. "
                    "The read tool can only read document files."
                )

            # Defaults
            offset = offset if offset is not None else 1
            limit = limit if limit is not None else FileTool.DEFAULT_READ_LIMIT
            try:
                offset = int(offset)
                limit = max(1, min(int(limit), FileTool.DEFAULT_READ_LIMIT))
            except (TypeError, ValueError):
                return False, "offset and limit must be positive integers"

            if offset < 1:
                offset = 1

            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

            total_lines = len(lines)

            if offset > total_lines:
                return (
                    False,
                    f"Offset {offset} is out of range (file has {total_lines} lines)",
                )

            # Calculate slice
            start_idx = offset - 1  # Convert to 0-indexed
            end_idx = min(start_idx + limit, total_lines)

            selected_lines = lines[start_idx:end_idx]

            # Grok Build anchors the first line and every tenth line. It does
            # not clip individual lines because that corrupts minified files.
            output_parts = []
            for i, line in enumerate(selected_lines, start=offset):
                content = line.rstrip("\r\n")
                output_parts.append(
                    f"{i}\u2192{content}" if i == offset or i % 10 == 0 else content
                )

            output = "\n".join(output_parts)
            estimated_tokens = len(output.encode("utf-8")) // 4
            if estimated_tokens > FileTool.MAX_READ_TOKENS:
                range_specified = offset != 1 or limit != FileTool.DEFAULT_READ_LIMIT
                if range_specified:
                    message = (
                        f"The requested line range (offset={offset}, limit={limit}) "
                        f"contains {estimated_tokens} tokens, which exceeds the "
                        f"maximum allowed tokens ({FileTool.MAX_READ_TOKENS} tokens). "
                        "Try a smaller limit, a different starting offset, or use "
                        "grep to search for specific content."
                    )
                else:
                    message = (
                        f"File content ({estimated_tokens} tokens) exceeds maximum "
                        f"allowed tokens ({FileTool.MAX_READ_TOKENS} tokens). Please "
                        "use offset and limit parameters to read a shorter range, or "
                        "use grep to search for specific content."
                    )
                return False, message

            return True, output

        except FileNotFoundError:
            return False, f"File not found: {path}"
        except Exception as e:
            return False, f"Error reading file: {str(e)}"

    @staticmethod
    def list_directory(path: str) -> Tuple[bool, str]:
        """List directory contents"""
        try:
            dir_path = Path(FileTool.expand_path(path)).resolve()

            if not dir_path.exists():
                return False, f"Directory not found: {path}"

            if not dir_path.is_dir():
                return False, f"Not a directory: {path}"

            entries = []
            for item in dir_path.iterdir():
                if item.is_dir():
                    entries.append(item.name + "/")
                else:
                    entries.append(item.name)

            entries.sort()

            output_parts = [
                f"<path>{dir_path}</path>",
                f"<type>directory</type>",
                "<entries>",
                "\n".join(entries),
                f"\n({len(entries)} entries)",
                "</entries>",
            ]

            return True, "\n".join(output_parts)

        except Exception as e:
            return False, f"Error listing directory: {str(e)}"

    @staticmethod
    def write_file(path: str, content: str, append: bool = False) -> Tuple[bool, str]:
        """Write content to file"""
        try:
            file_path = Path(FileTool.expand_path(path)).resolve()

            # Create parent directories if needed
            file_path.parent.mkdir(parents=True, exist_ok=True)

            mode = "a" if append else "w"
            with open(file_path, mode, encoding="utf-8") as f:
                f.write(content)

            return True, f"File {'appended' if append else 'written'}: {path}"

        except Exception as e:
            return False, f"Error writing file: {str(e)}"

    @staticmethod
    def list_files(path: str = ".", recursive: bool = False) -> Tuple[bool, List[str]]:
        """List files in directory"""
        try:
            dir_path = Path(FileTool.expand_path(path)).resolve()

            if not dir_path.is_dir():
                return False, [f"Not a directory: {path}"]

            if recursive:
                files = [str(p.relative_to(dir_path)) for p in dir_path.rglob("*")]
            else:
                files = [str(p.relative_to(dir_path)) for p in dir_path.iterdir()]

            return True, sorted(files)

        except Exception as e:
            return False, [f"Error listing files: {str(e)}"]

    @staticmethod
    def delete_file(path: str) -> Tuple[bool, str]:
        """Delete a file"""
        try:
            file_path = Path(FileTool.expand_path(path)).resolve()

            if not file_path.exists():
                return False, f"File not found: {path}"

            if file_path.is_dir():
                return False, "Use delete_directory for directories"

            file_path.unlink()
            return True, f"File deleted: {path}"

        except Exception as e:
            return False, f"Error deleting file: {str(e)}"

    @staticmethod
    def delete_directory(path: str) -> Tuple[bool, str]:
        """Delete a directory"""
        try:
            dir_path = Path(FileTool.expand_path(path)).resolve()

            if not dir_path.exists():
                return False, f"Directory not found: {path}"

            if not dir_path.is_dir():
                return False, "Use delete_file for files"

            shutil.rmtree(dir_path)
            return True, f"Directory deleted: {path}"

        except Exception as e:
            return False, f"Error deleting directory: {str(e)}"

    @staticmethod
    def create_directory(path: str) -> Tuple[bool, str]:
        """Create a directory"""
        try:
            dir_path = Path(FileTool.expand_path(path)).resolve()
            dir_path.mkdir(parents=True, exist_ok=True)
            return True, f"Directory created: {path}"

        except Exception as e:
            return False, f"Error creating directory: {str(e)}"

    @staticmethod
    def file_exists(path: str) -> bool:
        """Check if file exists"""
        return Path(FileTool.expand_path(path)).exists()

    @staticmethod
    def get_file_info(path: str) -> Tuple[bool, dict]:
        """Get file information"""
        try:
            file_path = Path(FileTool.expand_path(path)).resolve()

            if not file_path.exists():
                return False, {}

            stat = file_path.stat()
            return True, {
                "path": str(file_path),
                "size": stat.st_size,
                "is_file": file_path.is_file(),
                "is_dir": file_path.is_dir(),
                "modified": stat.st_mtime,
            }

        except Exception as e:
            return False, {"error": str(e)}
