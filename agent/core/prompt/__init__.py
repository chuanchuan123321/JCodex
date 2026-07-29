"""Dynamic prompt system inspired by OpenCode"""

import os
import platform
from pathlib import Path
from typing import List, Optional
from datetime import datetime


class PromptBuilder:
    """Build system prompts dynamically from modular components"""

    def __init__(self):
        self.base_dir = Path(__file__).parent
        self._base_prompt: Optional[str] = None
        self._tools_prompt: Optional[str] = None
        self._environment_prompt: Optional[str] = None

    def _load_template(self, filename: str) -> str:
        """Load a prompt template file"""
        filepath = self.base_dir / filename
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
        return ""

    @property
    def base_prompt(self) -> str:
        """Load base prompt"""
        if self._base_prompt is None:
            self._base_prompt = self._load_template("base.txt")
        return self._base_prompt

    @property
    def tools_prompt(self) -> str:
        """Load tools prompt"""
        if self._tools_prompt is None:
            self._tools_prompt = self._load_template("tools.txt")
        return self._tools_prompt

    @property
    def environment_prompt(self) -> str:
        """Load environment prompt template"""
        if self._environment_prompt is None:
            self._environment_prompt = self._load_template("environment.txt")
        return self._environment_prompt

    def build_system_prompt(
        self,
        working_directory: str,
        project_root: str,
        workspace_path: str,
        builtin_skills_path: str,
        workspace_skills_path: str,
        desktop_path: str,
        output_path: str,
        temp_path: str,
        cache_path: str,
        is_git_repo: bool = False,
        skills_summary: str = "",
    ) -> str:
        """Build complete system prompt with all variables filled"""

        # Environment info
        today_date = datetime.now().strftime("%Y-%m-%d")
        platform_name = platform.system()

        # Fill environment template
        env_prompt = self.environment_prompt.format(
            working_directory=working_directory,
            is_git_repo="yes" if is_git_repo else "no",
            platform=platform_name,
            today_date=today_date,
            directories=skills_summary if skills_summary else "(No skills loaded)",
            project_root=project_root,
            workspace_path=workspace_path,
            builtin_skills_path=builtin_skills_path,
            workspace_skills_path=workspace_skills_path,
            desktop_path=desktop_path,
            output_path=output_path,
            temp_path=temp_path,
            cache_path=cache_path,
        )

        # Combine all prompts
        parts = [
            self.base_prompt,
            "",
            "---",
            "",
            self.tools_prompt,
            "",
            "---",
            "",
            env_prompt,
        ]

        return "\n".join(parts)

    def build_user_prompt(
        self,
        user_request: str,
        context: str,
        step_count: int,
        max_steps: int,
        web_search_count: int = 0,
        max_web_searches: int = 8,
        accumulated_compression: str = "",
    ) -> str:
        """Build user message with task and context"""

        steps_remaining = max_steps - step_count + 1
        steps_done = step_count - 1

        # Build context section
        context_parts = []

        if accumulated_compression:
            context_parts.append("【之前的任务摘要】")
            context_parts.append(accumulated_compression)
            context_parts.append("")

        if context:
            context_parts.append("【当前任务执行过程】")
            context_parts.append(context)

        context_section = (
            "\n".join(context_parts)
            if context_parts
            else "这是第一个任务，还没有执行任何步骤。"
        )

        user_prompt = f"""【用户任务】
{user_request}

【执行上下文】
{context_section}

【步骤进度】
当前步骤: [{step_count}/{max_steps}]
你已经执行了 {steps_done} 步，还有 {steps_remaining} 步可用
网络搜索次数: {web_search_count}/{max_web_searches}

---
现在开始执行任务。"""

        return user_prompt


# Global instance
prompt_builder = PromptBuilder()
