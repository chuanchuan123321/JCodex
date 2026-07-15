"""
文件读取截断策略 - 对齐 OpenCode
实现智能截断、继续提示、完整内容保存
"""

import os
from pathlib import Path
from typing import Tuple, List, Optional


class FileTruncate:
    """文件内容截断管理器"""

    # 默认限制（与 OpenCode 一致）
    MAX_LINES = 2000
    MAX_BYTES = 50 * 1024  # 50 KB
    MAX_LINE_LENGTH = 2000

    # 存储目录
    OUTPUT_DIR = None

    @classmethod
    def init_storage(cls, workspace_path: str):
        """初始化存储目录"""
        cls.OUTPUT_DIR = Path(workspace_path) / "cache" / "file-reads"
        cls.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def truncate_output(
        cls,
        content: str,
        file_path: str,
        offset: int = 1
    ) -> Tuple[str, bool, Optional[str]]:
        """
        截断文件输出（对齐 OpenCode 策略）

        Args:
            content: 文件完整内容
            file_path: 文件路径
            offset: 起始行号

        Returns:
            (截断后的内容, 是否截断, 完整内容保存路径)
        """
        lines = content.split('\n')
        total_lines = len(lines)
        total_bytes = len(content.encode('utf-8'))

        # 检查是否需要截断
        if total_lines <= cls.MAX_LINES and total_bytes <= cls.MAX_BYTES:
            # 小文件：直接返回
            formatted = cls._format_lines(lines, offset)
            return formatted, False, None

        # 大文件：截断并保存完整内容
        truncated_lines = lines[:cls.MAX_LINES]
        removed_lines = total_lines - cls.MAX_LINES

        # 格式化截断后的内容
        formatted = cls._format_lines(truncated_lines, offset)

        # 保存完整内容到文件
        import uuid
        cache_id = f"file_{uuid.uuid4().hex[:8]}"
        cache_file = cls.OUTPUT_DIR / cache_id

        try:
            cache_file.write_text(content, encoding='utf-8')

            # 添加截断提示
            hint = f"\n\n... {removed_lines} lines truncated ...\n\n"
            hint += f"📁 Full output saved to: `{cache_file}`\n"
            hint += f"💡 Use `read` with offset={offset + cls.MAX_LINES} to continue."

            return formatted + hint, True, str(cache_file)

        except Exception as e:
            # 如果保存失败，至少返回截断的内容
            hint = f"\n\n... {removed_lines} lines truncated ...\n\n"
            hint += f"⚠️ Failed to save full output: {e}"
            return formatted + hint, True, None

    @classmethod
    def _format_lines(cls, lines: List[str], offset: int) -> str:
        """格式化行内容（带行号）"""
        formatted = []
        for i, line in enumerate(lines, offset):
            # 截断过长的行
            if len(line) > cls.MAX_LINE_LENGTH:
                line = line[:cls.MAX_LINE_LENGTH] + f"... (line truncated to {cls.MAX_LINE_LENGTH} chars)"

            formatted.append(f"{i}: {line}")

        return '\n'.join(formatted)

    @classmethod
    def get_file_info(cls, file_path: str) -> dict:
        """获取文件信息（用于上下文管理）"""
        path = Path(file_path)

        if not path.exists():
            return {"exists": False}

        try:
            stat = path.stat()
            lines = 0

            if path.is_file():
                # 快速估算行数（读取前 1KB）
                try:
                    sample = path.read_text(encoding='utf-8')[:1024]
                    lines = sample.count('\n') + 1
                except:
                    lines = 0

            return {
                "exists": True,
                "is_file": path.is_file(),
                "is_dir": path.is_dir(),
                "size_bytes": stat.st_size,
                "estimated_lines": lines,
                "path": str(path)
            }
        except Exception as e:
            return {"exists": False, "error": str(e)}
