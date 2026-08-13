"""Memory management system for storing and retrieving compressed context."""

import re
from datetime import datetime
from pathlib import Path


class MemoryManager:
    """Manages persistent memory storage for accumulated compression and metadata."""

    def __init__(self, memory_dir: str | None = None):
        """
        Initialize memory manager.

        Args:
            memory_dir: Path to memory directory. If None, uses default Memory folder.
        """
        if memory_dir is None:
            memory_dir = str(Path(__file__).parent.parent.parent / "Memory")

        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        self.compression_file = self.memory_dir / "accumulated_compression.md"
        self.execution_history_file = self.memory_dir / "execution_history.md"
        self.memory_context_file = self.memory_dir / "memory_context.md"
        self.index_file = self.memory_dir / "index.json"

    def load_memory_context(self) -> str:
        """Load the exact persisted first-turn memory block for prompt reuse."""
        try:
            return self.memory_context_file.read_text(encoding="utf-8").strip()
        except OSError:
            return ""

    def save_memory_context(self, context: str) -> None:
        """Persist the injected memory block verbatim to preserve prompt prefixes."""
        self.memory_context_file.write_text(str(context or "").strip(), encoding="utf-8")

    def _get_today_folder(self) -> Path:
        """Get or create today's date folder."""
        today = datetime.now().strftime("%Y-%m-%d")
        today_folder = self.memory_dir / today
        today_folder.mkdir(parents=True, exist_ok=True)
        return today_folder

    def _get_compression_filename(self) -> str:
        """Get archive filename with timestamp."""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        return f"{timestamp}_历史.md"

    def load_accumulated_compression(self) -> str:
        """Load compressed memory without any leaked reasoning blocks."""
        if self.compression_file.exists():
            with open(self.compression_file, encoding="utf-8") as f:
                return self.strip_reasoning(f.read())
        return ""

    def save_accumulated_compression(self, compression: str) -> None:
        """Save compressed memory after removing reasoning content."""
        with open(self.compression_file, "w", encoding="utf-8") as f:
            f.write(self.strip_reasoning(compression))

    def save_compression_archive(self, compression_content: str) -> str:
        """
        Save compression to archive folder with date and timestamp.

        Returns:
            The relative path to the saved compression file.
        """
        today_folder = self._get_today_folder()
        filename = self._get_compression_filename()
        filepath = today_folder / filename

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(compression_content)

        # Return relative path from Memory folder
        return f"{filepath.relative_to(self.memory_dir)}"

    def load_execution_history(self) -> list[str]:
        """Load execution history without model reasoning content."""
        if self.execution_history_file.exists():
            with open(self.execution_history_file, encoding="utf-8") as f:
                content = self.strip_reasoning(f.read())
                lines = content.strip().split("\n")
                return [line for line in lines if line.strip()]
        return []

    @staticmethod
    def strip_reasoning(content: str) -> str:
        """Remove private reasoning blocks while preserving visible answers."""
        cleaned = re.sub(
            r"<think\b[^>]*>[\s\S]*?</think>", "", str(content or ""), flags=re.IGNORECASE
        )
        cleaned = re.sub(r"<think\b[^>]*>[\s\S]*$", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(
            r"(?m)^【AI思考】[^\n]*(?:\n|$)", "", cleaned
        )
        cleaned = re.sub(r"</?think\b[^>]*>", "", cleaned, flags=re.IGNORECASE)
        return re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    @classmethod
    def extract_visible_commentary(cls, content: str) -> str:
        """Return public model narration outside private reasoning blocks."""
        visible = cls.strip_reasoning(content)
        return re.sub(r"\n{3,}", "\n\n", visible).strip()

    def remove_reasoning_from_execution_history(self) -> bool:
        """Rewrite legacy recent memory after removing stored reasoning."""
        if not self.execution_history_file.exists():
            return False
        original = self.execution_history_file.read_text(encoding="utf-8")
        cleaned = self.strip_reasoning(original)
        normalized = f"{cleaned}\n" if cleaned else ""
        if normalized == original:
            return False
        self.execution_history_file.write_text(normalized, encoding="utf-8")
        return True

    def append_execution_step(self, step: str) -> None:
        """Append a single execution step to history file."""
        with open(self.execution_history_file, "a", encoding="utf-8") as f:
            f.write(step + "\n")

    def clear_all(self) -> None:
        """Clear all memory files including archives."""
        import shutil

        # Clear main memory files
        if self.compression_file.exists():
            self.compression_file.unlink()
        if self.execution_history_file.exists():
            self.execution_history_file.unlink()
        if self.memory_context_file.exists():
            self.memory_context_file.unlink()
        if self.index_file.exists():
            self.index_file.unlink()

        # Clear all archived files in date-based folders
        if self.memory_dir.exists():
            # Remove the entire Memory directory and all its contents
            shutil.rmtree(self.memory_dir)
            # Recreate the basic directory structure
            self.memory_dir.mkdir(parents=True, exist_ok=True)
            # Recreate the main files (empty)
            self.compression_file.touch()
            self.execution_history_file.touch()
            self.memory_context_file.touch()
            self.index_file.touch()

    def clear_execution_history(self) -> None:
        """Clear only the execution history file content (keep the file)."""
        # 清空文件内容而不是删除文件
        with open(self.execution_history_file, "w", encoding="utf-8") as f:
            f.write("")

