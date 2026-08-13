"""JCodex desktop UI - the per-conversation task executor.

Extracted from the legacy monolithic ``main.py``. ``DesktopTaskExecutor``
owns one conversation's isolated runtime; ``DesktopRunContext`` carries the
mutable state of one submitted message. Cross-module pipeline helpers are
imported lazily inside the methods that need them to avoid a cycle.
"""

import contextlib
import json
import queue
import re
import secrets
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from langchain_core.messages import HumanMessage

from agent.core.ai_engine import AIEngine
from agent.core.context_compactor import ContextCompactor
from agent.core.env_utils import env_int
from agent.core.extended_tool_executor import ExtendedToolExecutor, strip_disabled_vision_prompt
from agent.core.langchain_model import AIEngineChatModel
from agent.core.langgraph_runner import (
    QUESTION_TOOL_NAMES,
    LangGraphRunner,
    create_checkpoint_saver,
)
from agent.core.memory_manager import MemoryManager
from agent.core.memory_store import MemoryStore
from agent.core.skills import SkillsLoader
from agent.core.tool_loop_guard import ToolLoopGuard
from agent.core.tool_result import ToolExecutionResult
from agent.tools.preview import PreviewManager
from agent.ui.desktop import constants, helpers, runtime


class DesktopTaskExecutor:
    def __init__(self, shared_from: Optional["DesktopTaskExecutor"] = None):
        self.ai_engine: AIEngine | None = None
        self.tool_executor: ExtendedToolExecutor | None = None
        self.preview_manager: PreviewManager | None = None
        self.skills_loader: SkillsLoader | None = None
        self.memory_manager: MemoryManager | None = None
        self.memory_store: MemoryStore | None = None
        self.langchain_model: AIEngineChatModel | None = None
        self.langgraph_runner: LangGraphRunner | None = None
        self.langgraph_checkpointer = None
        self._langgraph_max_steps = 0
        self.step_count = 0
        self.max_steps = env_int("MAX_STEPS", 100)
        self.allow_all_commands = False
        self.auto_allow_all_commands = False
        self.web_search_count = 0
        self.max_web_searches = env_int("MAX_WEB_SEARCHES", 8)
        self.max_tokens = env_int("MAX_TOKENS", 50000)
        self.context_window = env_int("CONTEXT_WINDOW", 256000)
        self.context_compactor = ContextCompactor(
            ContextCompactor.policy_from_runtime(self.context_window, None)
        )
        self.compress_at = self.context_compactor.policy.trigger_tokens
        self.show_knowledge_appendix = False
        self._memory_context_block = ""
        self._uses_persisted_short_term_context = False
        self.accumulated_compression = ""
        self.pending_approval: dict | None = None
        self.pending_question: dict | None = None
        self.current_user_request = ""
        self.conversation_id: str | None = None
        self.project: dict | None = None
        self.project_root: Path = constants.PROJECT_ROOT
        self.tool_loop_guard = ToolLoopGuard()
        self._compression_lock = threading.Lock()
        self._memory_lock = threading.RLock()
        self._context_usage_lock = threading.RLock()
        self._latest_context_usage: dict | None = None

    def initialize(self):
        try:
            if self.ai_engine is not None:
                return True, "Already initialized"
            self.ai_engine = AIEngine()
            project_root = constants.DATA_ROOT
            workspace_path = project_root / "workspace"
            workspace_path.mkdir(exist_ok=True)
            helpers._seed_bundled_skill_files()
            self.skills_loader = SkillsLoader(workspace_path)
            self.preview_manager = PreviewManager(
                project_root=project_root,
                event_callback=_preview_event_publisher(),
                log_dir=workspace_path / "temp" / "previews",
            )
            self.tool_executor = ExtendedToolExecutor(
                skills_loader=self.skills_loader,
                preview_manager=self.preview_manager,
                project_root=project_root,
                workspace_root=workspace_path,
                protected_root=constants.PROJECT_ROOT,
                data_root=constants.DATA_ROOT,
                restrict_reads_to_project=False,
            )
            checkpoint_path = workspace_path / "data" / "langgraph_checkpoints.sqlite3"
            self.langgraph_checkpointer = create_checkpoint_saver(checkpoint_path)
            active_id = runtime.conversation_store.active_id()
            if not active_id:
                active_id = runtime.conversation_store.create()["id"]
            self.activate_conversation(active_id)

            from agent.core.data_integrator import DataIntegrator

            self.data_integrator = DataIntegrator(data_dir=workspace_path / "data")
            self.rebuild_langgraph_runner()
            self.cleanup_orphaned_desktop_checkpoints()
            helpers._cleanup_orphaned_long_term_memory()

            return True, "Initialized successfully"
        except Exception as e:
            return False, str(e)

    def initialize_conversation_runtime(
        self, conversation_id: str, shared_from: "DesktopTaskExecutor"
    ) -> None:
        """Initialize one isolated executor using shared durable infrastructure."""
        if not shared_from.ai_engine or not shared_from.tool_executor:
            raise RuntimeError("Desktop runtime has not been initialized")

        self.skills_loader = shared_from.skills_loader
        self.langgraph_checkpointer = shared_from.langgraph_checkpointer
        self.max_steps = shared_from.max_steps
        self.max_tokens = shared_from.max_tokens
        self.context_window = shared_from.context_window
        self.max_web_searches = shared_from.max_web_searches
        self.context_compactor.refresh_policy(self.context_window, None)
        self.compress_at = self.context_compactor.policy.trigger_tokens
        self.show_knowledge_appendix = False
        self.auto_allow_all_commands = shared_from.auto_allow_all_commands
        self.allow_all_commands = shared_from.auto_allow_all_commands

        conversation = runtime.conversation_store.load(conversation_id)
        self.project = helpers._project_for_conversation(conversation)
        root_path = str((self.project or {}).get("root_path", "")).strip()
        self.project_root = (
            Path(root_path).expanduser().resolve()
            if root_path and Path(root_path).expanduser().is_dir()
            else constants.PROJECT_ROOT
        )
        workspace_path = constants.DATA_ROOT / "workspace"

        # Model, graph runner, tool state, memory, and data task state are
        # intentionally per conversation. Checkpoints and app-level data remain
        # shared, while code tools and previews bind to the task's project root.
        self.ai_engine = AIEngine()
        self.preview_manager = PreviewManager(
            project_root=self.project_root,
            event_callback=_preview_event_publisher(),
            log_dir=workspace_path / "temp" / "previews",
        )
        self.tool_executor = ExtendedToolExecutor(
            skills_loader=self.skills_loader,
            preview_manager=self.preview_manager,
            project_root=self.project_root,
            workspace_root=workspace_path,
            protected_root=constants.PROJECT_ROOT,
            data_root=constants.DATA_ROOT,
            restrict_reads_to_project=False,
        )
        self.activate_conversation(conversation_id)

        from agent.core.data_integrator import DataIntegrator

        self.data_integrator = DataIntegrator(data_dir=workspace_path / "data")
        self.rebuild_langgraph_runner()

    def initialize_subagent_runtime(
        self,
        parent: "DesktopTaskExecutor",
        *,
        team_id: str,
        agent_id: str,
        write_access: bool = False,
        write_paths: list[str] | None = None,
        workdir: str = "",
    ) -> None:
        """Create a child runtime without sharing active conversation context."""
        if not parent.ai_engine or not parent.tool_executor or not parent.memory_manager:
            raise RuntimeError("Parent desktop runtime has not been initialized")

        self.skills_loader = parent.skills_loader
        # Each child gets its own checkpoint store. An in-memory saver is enough
        # for the lifetime of a collaboration run and avoids cross-agent SQLite
        # contention while keeping graph state completely isolated.
        self.langgraph_checkpointer = create_checkpoint_saver()
        # A child must remain bounded independently, while respecting a lower
        # parent limit selected for a short task.
        self.max_steps = max(4, min(parent.max_steps, 100))
        self.max_tokens = parent.max_tokens
        self.context_window = parent.context_window
        self.max_web_searches = parent.max_web_searches
        self.context_compactor.refresh_policy(self.context_window, None)
        self.compress_at = self.context_compactor.policy.trigger_tokens
        self.show_knowledge_appendix = False
        self.auto_allow_all_commands = True
        self.allow_all_commands = True
        raw_workdir = str(workdir or "").strip()
        workdir_path = Path(raw_workdir).expanduser() if raw_workdir else None
        if workdir_path is not None and not workdir_path.is_absolute():
            workdir_path = parent.project_root / workdir_path
        self.project_root = (
            workdir_path.resolve(strict=False) if workdir_path is not None else parent.project_root
        )
        self.project = dict(parent.project) if parent.project else None
        if raw_workdir and not self.project:
            self.project = {
                "id": f"subagent-workdir:{self.project_root}",
                "name": self.project_root.name or "Subagent Workdir",
                "root_path": str(self.project_root),
                "instructions": "",
                "available": True,
            }
        self.conversation_id = (
            f"{parent.conversation_id}:agent:{str(team_id)[:16]}:{str(agent_id)[:16]}"
        )

        workspace_path = constants.DATA_ROOT / "workspace"
        self.ai_engine = AIEngine()
        self.preview_manager = parent.preview_manager
        self.tool_executor = ExtendedToolExecutor(
            skills_loader=self.skills_loader,
            preview_manager=self.preview_manager,
            project_root=self.project_root,
            workspace_root=workspace_path,
            protected_root=constants.PROJECT_ROOT,
            data_root=constants.DATA_ROOT,
            restrict_reads_to_project=False,
        )
        self.memory_manager = MemoryManager(
            str(parent.memory_manager.memory_dir / "agents" / str(team_id) / str(agent_id))
        )
        # Project long-term memory may be searched, while child execution and
        # compression files remain private to this exact agent.
        self.memory_store = parent.memory_store
        self.tool_executor.memory_store = self.memory_store
        self._memory_context_block = ""
        self.accumulated_compression = ""
        self.current_user_request = ""
        self.pending_approval = None
        self.pending_question = None
        self.tool_loop_guard = ToolLoopGuard()
        self._subagent_write_paths = list(write_paths or [])
        self.tool_executor.mutation_scope_roots = tuple(
            (
                Path(path).expanduser()
                if Path(path).expanduser().is_absolute()
                else self.project_root / Path(path).expanduser()
            )
            for path in self._subagent_write_paths
            if str(path or "").strip()
        )

        from agent.core.data_integrator import DataIntegrator

        self.data_integrator = DataIntegrator(data_dir=self.memory_manager.memory_dir / "data")
        self.langchain_model = AIEngineChatModel(engine=self.ai_engine)
        self.langgraph_runner = None
        self._langgraph_max_steps = 0

    def get_subagent_tools(self, *, write_access: bool = False) -> list[dict]:
        """Expose a bounded child tool set with no nested collaboration or UI waits."""
        allowed = set(constants._SUBAGENT_READ_TOOLS) | constants._SUBAGENT_COLLABORATION_TOOLS
        if write_access:
            allowed.update({"edit", "write"})
        return [
            tool
            for tool in self.get_available_tools()
            if str(tool.get("function", {}).get("name", "")) in allowed
        ]

    def _create_conversation_memory_store(self) -> MemoryStore:
        """Create a project-shared or task-isolated long-term memory index."""
        if not self.conversation_id:
            raise RuntimeError("Conversation id is required for memory storage")
        if self.project and self.project.get("available"):
            return MemoryStore(
                constants.DATA_ROOT / "workspace" / "memory",
                self.project_root,
                include_global=False,
            )
        return helpers._memory_store_for_conversation(
            runtime.conversation_store.load(self.conversation_id)
        )

    def activate_conversation(self, conversation_id: str) -> None:
        """Switch all model memory state to one persisted desktop task."""
        conversation = runtime.conversation_store.load(conversation_id)
        self.project = helpers._project_for_conversation(conversation)
        root_path = str((self.project or {}).get("root_path", "")).strip()
        self.project_root = (
            Path(root_path).expanduser().resolve()
            if root_path and Path(root_path).expanduser().is_dir()
            else constants.PROJECT_ROOT
        )
        clear_plans = getattr(self.tool_executor, "clear_plan_snapshots", None)
        if callable(clear_plans):
            clear_plans(conversation_id)
        self.conversation_id = conversation_id
        self.memory_manager = MemoryManager(
            str(runtime.conversation_store.short_term_memory_dir(conversation_id))
        )
        self._memory_lock = helpers._short_term_memory_lock(self.memory_manager.memory_dir)
        self._compression_lock = helpers._short_term_compression_lock(
            self.memory_manager.memory_dir
        )
        self._uses_persisted_short_term_context = bool(conversation.get("short_term_memory_id"))
        self.memory_store = self._create_conversation_memory_store()
        if self.tool_executor:
            self.tool_executor.memory_store = self.memory_store
        self.tool_loop_guard = ToolLoopGuard()
        self.memory_manager.remove_reasoning_from_execution_history()
        self.accumulated_compression = self.memory_manager.load_accumulated_compression()
        self.step_count = 0
        self.web_search_count = 0
        self.pending_approval = None
        self.pending_question = None
        self.current_user_request = ""
        # Retrieval is cached only while this task runtime stays active. A task
        # switch or desktop restart must re-query its own scoped long-term index
        # instead of trusting a cache created under an earlier shared scope.
        self._memory_context_block = (
            self.memory_manager.load_memory_context()
            if self._uses_persisted_short_term_context
            else ""
        )
        with self._context_usage_lock:
            self._latest_context_usage = None
        if self.ai_engine:
            self.ai_engine.clear_history()

    def get_available_tools(self):
        if not self.tool_executor:
            return []
        return self.tool_executor.get_available_tools()

    def get_runtime_tools(
        self,
        *,
        plan_enabled: bool = True,
        voice_mode: bool = False,
        multi_agent_enabled: bool = False,
    ) -> list[dict]:
        """Return the schemas actually bound for this desktop task mode."""
        hidden = set()
        if not plan_enabled:
            hidden.update({"todo_write", "update_plan"})
        if voice_mode:
            hidden.update(QUESTION_TOOL_NAMES)
        if not multi_agent_enabled:
            hidden.update(constants._MULTI_AGENT_TOOL_NAMES)
        return [
            tool
            for tool in self.get_available_tools()
            if str(tool.get("function", {}).get("name", "")) not in hidden
        ]

    def rebuild_langgraph_runner(self) -> None:
        """Rebind the current model settings while preserving graph checkpoints."""
        if not self.ai_engine or not self.tool_executor:
            return
        self.langchain_model = AIEngineChatModel(engine=self.ai_engine)
        self.langgraph_runner = LangGraphRunner(
            self.langchain_model,
            self.tool_executor.get_available_tools(),
            self.execute_graph_tool,
            checkpointer=self.langgraph_checkpointer,
            requires_approval=self._is_tool_requires_approval,
            max_steps=self.max_steps,
        )
        self._langgraph_max_steps = self.max_steps

    def cleanup_orphaned_desktop_checkpoints(self) -> dict:
        """Remove durable runs left behind by desktop tasks deleted in older builds."""
        runner = self.langgraph_runner
        if runner is None:
            return {"removed_threads": 0, "compacted": False, "error": ""}

        known_ids = {
            str(item.get("id", ""))
            for item in runtime.conversation_store.list().get("conversations", [])
        }
        orphan_ids: set[str] = set()
        try:
            for thread_id in runner.list_checkpoint_thread_ids():
                conversation_id, separator, _message_id = thread_id.partition(":")
                if not separator or conversation_id in known_ids:
                    continue
                if re.fullmatch(
                    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
                    conversation_id,
                    flags=re.IGNORECASE,
                ):
                    orphan_ids.add(conversation_id)
        except Exception as exc:
            return {"removed_threads": 0, "compacted": False, "error": str(exc)}

        removed_threads = 0
        error = ""
        for conversation_id in orphan_ids:
            try:
                removed_threads += runner.delete_threads_with_prefix(f"{conversation_id}:")
            except Exception as exc:
                error = str(exc)
                break

        compacted = False
        if removed_threads:
            try:
                compacted = runner.vacuum_checkpoint_store()
            except Exception as exc:
                error = str(exc)
        return {
            "removed_threads": removed_threads,
            "compacted": compacted,
            "error": error,
        }

    def build_system_prompt(
        self,
        user_request: str,
        context: str = "",
        *,
        plan_enabled: bool = False,
        plan_policy: str = "off",
        voice_mode: bool = False,
        multi_agent_enabled: bool = False,
        child_agent: bool = False,
    ) -> tuple:
        project_root = self.project_root
        workspace_path = constants.DATA_ROOT / "workspace"

        skills_summary = ""
        try:
            skills = self.skills_loader.list_skills()
            skills_summary = "\n".join(
                [f"- **{s.get('name', 'unknown')}**: {s.get('description', '')}" for s in skills]
            )
        except Exception:
            pass

        agent_md_path = constants.PROJECT_ROOT / "Agent.md"

        with open(agent_md_path, encoding="utf-8") as f:
            agent_template = f.read()

        split_marker = "【User Task】"
        split_idx = agent_template.find(split_marker)

        if split_idx >= 0:
            system_prompt_template = agent_template[:split_idx]
            user_message_template = agent_template[split_idx:]
        else:
            system_prompt_template = agent_template
            user_message_template = ""

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        system_prompt = strip_disabled_vision_prompt(system_prompt_template)
        system_prompt = system_prompt.replace("{step_count}", str(self.step_count))
        system_prompt = system_prompt.replace("{max_steps}", str(self.max_steps))
        system_prompt = system_prompt.replace("{step_count_minus_1}", str(self.step_count - 1))
        system_prompt = system_prompt.replace(
            "{steps_remaining}", str(self.max_steps - self.step_count + 1)
        )
        system_prompt = system_prompt.replace(
            "{plan_mode_instruction}",
            helpers._plan_mode_instruction(plan_enabled, plan_policy),
        )
        system_prompt = system_prompt.replace(
            "{multi_agent_mode_instruction}",
            helpers._multi_agent_mode_instruction(multi_agent_enabled, child_agent=child_agent),
        )
        system_prompt = system_prompt.replace(
            "{runtime_mode_instruction}",
            "This task is running locally in the desktop app, not through a "
            "gateway or Feishu channel. Do not claim to send messages or files "
            "to a gateway; provide local file paths in your response instead.",
        )
        system_prompt = system_prompt.replace(
            "{platform_instruction}", helpers._platform_instruction()
        )
        system_prompt = system_prompt.replace(
            "{project_context}", helpers._read_project_context(self.project)
        )
        file_write_boundary = (
            f"This task belongs to a user-bound local project at `{project_root}`. "
            f"You may normally create, edit, move, rename, and delete files in "
            f"that project when the user request requires it. However, the "
            f"JCodex application source tree at `{constants.PROJECT_ROOT}` and its data "
            f"workspace at `{workspace_path}` are always protected from "
            f"file-tool mutations except under "
            f"`{workspace_path / 'temp'}` and `{workspace_path / 'output'}`. "
            f"Paths outside the bound project are not globally read-only: "
            f"Desktop, Documents, Downloads, and other local paths explicitly "
            f"placed in scope by the user may also be created, edited, moved, "
            f"renamed, or deleted. Dropped reference folders have the same "
            f"mutation permissions. Use "
            f"`{workspace_path / 'temp'}` for scratch files and "
            f"`{workspace_path / 'output'}` for exported "
            "artifacts. Normal approval rules still apply to mutating tools."
            if self.project
            else f"Protect the JCodex application source tree at "
            f"`{constants.PROJECT_ROOT}` and its data workspace at `{workspace_path}`: "
            f"you may inspect them, but do not create, edit, overwrite, "
            f"append, move, rename, or delete files inside them except under "
            f"`{workspace_path / 'temp'}` and "
            f"`{workspace_path / 'output'}`. This restriction applies only to "
            "the JCodex source tree. Desktop, Documents, Downloads, dropped "
            "reference folders, and other local paths explicitly placed in "
            "scope by the user may be created, edited, moved, renamed, or "
            "deleted. Normal approval rules still apply to mutating tools."
        )
        system_prompt = system_prompt.replace("{file_write_boundary}", file_write_boundary)
        system_prompt = system_prompt.replace(
            "{accumulated_compression}",
            self.accumulated_compression or "这是第一个任务",
        )

        execution_history = self.memory_manager.load_execution_history()
        history_text = "\n".join(execution_history) if execution_history else "还没有执行任何步骤"
        system_prompt = system_prompt.replace("{execution_history}", history_text)

        system_prompt = system_prompt.replace("{current_time}", current_time)
        system_prompt = system_prompt.replace("{web_search_count}", str(self.web_search_count))
        system_prompt = system_prompt.replace("{max_web_searches}", str(self.max_web_searches))
        system_prompt = system_prompt.replace("{project_root}", str(project_root))
        system_prompt = system_prompt.replace("{workspace_path}", str(workspace_path))
        system_prompt = system_prompt.replace(
            "{builtin_skills_path}", str(constants.PROJECT_ROOT / "agent" / "skills")
        )
        system_prompt = system_prompt.replace(
            "{workspace_skills_path}", str(workspace_path / "skills")
        )
        system_prompt = system_prompt.replace("{desktop_path}", str(Path.home() / "Desktop"))
        system_prompt = system_prompt.replace("{output_path}", str(workspace_path / "output"))
        system_prompt = system_prompt.replace("{temp_path}", str(workspace_path / "temp"))
        system_prompt = system_prompt.replace("{cache_path}", str(workspace_path / "cache"))
        system_prompt = system_prompt.replace("{skills_summary}", skills_summary)

        if self._uses_persisted_short_term_context:
            persisted_memory_context = self.memory_manager.load_memory_context()
            if persisted_memory_context:
                self._memory_context_block = persisted_memory_context
        if self.memory_store and not self._memory_context_block:
            self._memory_context_block = self.memory_store.initial_context(user_request)
            self.memory_manager.save_memory_context(self._memory_context_block)
        if self.memory_store:
            system_prompt = self.memory_store.append_context(
                system_prompt, self._memory_context_block
            )

        voice_instruction = helpers._voice_mode_instruction(bool(voice_mode))
        if voice_instruction:
            system_prompt = f"{system_prompt.rstrip()}\n\n{voice_instruction}\n"

        user_message = user_message_template
        user_message = user_message.replace("{user_request}", user_request)
        user_message = user_message.replace("{context}", context)

        return system_prompt, user_message

    def reload_knowledge_base(self) -> None:
        """Legacy no-op: Grok-style memory reindexes on search."""
        return

    def reload_data_integrator(self) -> None:
        """Refresh the in-memory data integrator used by active chats."""
        project_root = constants.DATA_ROOT
        workspace_path = project_root / "workspace"
        from agent.core.data_integrator import DataIntegrator

        self.data_integrator = DataIntegrator(data_dir=workspace_path / "data")

    def _is_tool_requires_approval(self, tool_name: str, params: dict | None = None) -> bool:
        """Check if a tool requires user approval before execution（与 CLI 完全一致）"""
        if tool_name == "spawn_agent":
            return bool((params or {}).get("write_access", False))
        dangerous_tools = {
            "bash",
            "shell",
            "write",  # 写入文件（OpenCode风格）
            "edit",  # 编辑文件
            "send_file",
            "generate_pdf",
            "project_preview",
        }
        return tool_name in dangerous_tools

    def execute_tool(self, tool_name: str, params: dict, guard_decision: dict | None = None) -> str:
        try:
            # 保存原始 JSON 请求到记忆
            import json

            tool_json = json.dumps({"tool": tool_name, "params": params}, ensure_ascii=False)
            history_entry = f"执行 {tool_name}:\n{tool_json}\n结果: "

            guard_decision = guard_decision or self.tool_loop_guard.before_call(tool_name, params)
            if guard_decision["action"] != "execute":
                result = guard_decision["result"]
                self.memory_manager.append_execution_step(history_entry + result)
                return result

            if tool_name in {"web_search", "websearch"}:
                if self.web_search_count >= self.max_web_searches:
                    result = (
                        f"⚠️ 已达到网络搜索限制({self.max_web_searches}次)，请基于已有信息给出结论"
                    )
                    self.memory_manager.append_execution_step(history_entry + result)
                    return result
                self.web_search_count += 1

            raw_result = self.tool_executor.execute(
                {"tool": tool_name, "params": params},
                conversation_id=self.conversation_id,
                message_id=0,
            )
            result = self._tool_result_text(raw_result)
            self.tool_loop_guard.record_result(
                tool_name,
                params,
                result,
                guard_decision["signature"],
                guard_decision["kind"],
            )

            # 自动记录到数据整合模块
            self.data_integrator.ingest_tool_result(
                tool_name=tool_name, params=params, result=result
            )

            # 追加结果到记忆
            history_entry += result

            self.memory_manager.append_execution_step(history_entry)
            return result
        except Exception as e:
            error_msg = f"Error: {e!s}"
            self.memory_manager.append_execution_step(f"执行 {tool_name} 失败: {error_msg}")
            return error_msg

    def execute_graph_tool(
        self, tool_name: str, params: dict, runtime: dict | None = None
    ) -> object:
        """Execute one LangGraph tool after its graph-level loop guard passes."""
        try:
            tool_json = json.dumps({"tool": tool_name, "params": params}, ensure_ascii=False)
            history_entry = f"执行 {tool_name}:\n{tool_json}\n结果: "

            if tool_name in {"web_search", "websearch"}:
                with self._memory_lock:
                    if self.web_search_count >= self.max_web_searches:
                        result = (
                            f"⚠️ 已达到网络搜索限制({self.max_web_searches}次)，"
                            "请基于已有信息给出结论"
                        )
                        self.memory_manager.append_execution_step(history_entry + result)
                        return result
                    self.web_search_count += 1

            runtime = runtime or {}
            cancelled = runtime.get("cancelled")
            if callable(cancelled) and cancelled():
                return "Error: task cancelled"
            if tool_name == "scheduler_create":
                from agent.ui.desktop.main import (  # late import: avoids cycle
                    _on_scheduled_task_fired,
                    _register_scheduled_task,
                )

                if not self.tool_executor.scheduled_prompt_callback:
                    self.tool_executor.scheduled_prompt_callback = _on_scheduled_task_fired
            raw_result = self.tool_executor.execute(
                {"tool": tool_name, "params": params},
                conversation_id=str(runtime.get("conversation_id") or self.conversation_id or ""),
                message_id=int(runtime.get("message_id", 0) or 0),
                runtime=runtime,
            )
            if callable(cancelled) and cancelled():
                return "Error: task cancelled"
            if tool_name == "scheduler_create":
                conversation_id = str(runtime.get("conversation_id") or self.conversation_id or "")
                _register_scheduled_task(raw_result, conversation_id, self.tool_executor)
            elif tool_name == "scheduler_delete":
                from agent.ui.desktop.main import (  # late import: avoids cycle
                    _unregister_scheduled_task,
                )

                _unregister_scheduled_task(raw_result)
            self.data_integrator.ingest_tool_result(
                tool_name=tool_name,
                params=params,
                result=self._tool_result_text(raw_result),
            )
            with self._memory_lock:
                # A replacement generation can share the same persisted memory
                # path while this old worker unwinds. Never append its late
                # result after cancellation.
                if callable(cancelled) and cancelled():
                    return "Error: task cancelled"
                self.memory_manager.append_execution_step(
                    history_entry + self._tool_result_text(raw_result)
                )
            return raw_result
        except Exception as exc:
            error_msg = f"Error: {exc!s}"
            self.memory_manager.append_execution_step(f"执行 {tool_name} 失败: {error_msg}")
            return error_msg

    @staticmethod
    def _tool_result_text(result: object) -> str:
        """Persist only text from structured model-only tool results."""
        if isinstance(result, ToolExecutionResult):
            return result.content
        return str(result or "")

    def _estimate_tokens(self, text: str) -> int:
        """估算文本的token数量（与 CLI 完全一致）"""
        import re

        chinese_chars = re.findall(r"[\u4e00-\u9fff]", text)
        text_without_chinese = re.sub(r"[\u4e00-\u9fff]", "", text)
        english_words = re.findall(r"\b[a-zA-Z]+\b", text_without_chinese)
        other_chars = len(text) - len(chinese_chars) - sum(len(w) for w in english_words)
        chinese_tokens = int(len(chinese_chars) * 1.7)
        english_tokens = int(len(english_words) * 1.9)
        other_tokens = int(other_chars / 2.5) + 200
        total_tokens = chinese_tokens + english_tokens + other_tokens
        return max(total_tokens, 1)

    def get_compression_snapshot(self) -> dict:
        """Return the current task memory that would be compressed."""
        execution_history = self.memory_manager.load_execution_history()
        history_text = "\n".join(execution_history)
        return {
            "execution_history": execution_history,
            "history_text": history_text,
            "step_count": len(execution_history),
            "tokens_before": self._estimate_tokens(history_text) if history_text else 0,
        }

    def get_graph_compression_snapshot(
        self,
        state: dict,
        *,
        plan_enabled: bool = True,
        voice_mode: bool = False,
        multi_agent_enabled: bool = False,
    ) -> dict:
        """Return the exact system/messages/tools prompt sent by LangGraph."""
        snapshot = ContextCompactor.build_snapshot(
            state,
            self.context_compactor.policy,
            self.get_runtime_tools(
                plan_enabled=plan_enabled,
                voice_mode=voice_mode,
                multi_agent_enabled=multi_agent_enabled,
            ),
        )
        self._cache_context_snapshot(snapshot)
        execution_history = self.memory_manager.load_execution_history()
        return {
            "execution_history": execution_history,
            "history_text": snapshot.transcript,
            "context_snapshot": snapshot,
            "step_count": len(execution_history),
            "tokens_before": snapshot.tokens,
            "threshold": snapshot.trigger_tokens,
            "context_window": snapshot.context_window,
            "usage_percent": snapshot.usage_percent,
        }

    def _sample_compaction_prompt(self, prompt: str) -> str:
        """Sample a summary without mutating normal conversation history."""
        result = self.ai_engine.call_messages(
            [{"role": "user", "content": prompt}],
            tools=None,
            temperature=0.1,
            timeout=max(1, env_int("COMPACTION_TIMEOUT_SECONDS", 300)),
            # ContextCompactor owns the input-stage retry policy. Retrying here
            # multiplied one slow compression request into several minutes.
            max_retries=1,
        )
        if result.get("finish_reason") in {"error", "length"}:
            raise RuntimeError(str(result.get("content", "Compaction model failed")))
        return str(result.get("content", "") or "")

    def _sample_memory_flush(self, messages: list[dict[str, str]]) -> str:
        """Run the pre-compaction memory turn without tools."""
        result = self.ai_engine.call_messages(
            messages,
            tools=None,
            temperature=0.1,
            timeout=max(1, env_int("MEMORY_FLUSH_TIMEOUT_SECONDS", 180)),
            max_retries=1,
        )
        if result.get("finish_reason") in {"error", "length"}:
            raise RuntimeError(str(result.get("content", "Memory flush model failed")))
        return str(result.get("content", "") or "")

    def _sync_long_term_conversation_memory(self) -> str:
        """Persist original user requirements so they remain retrievable after compaction."""
        if not self.memory_store or not self.conversation_id:
            return ""
        try:
            conversation = runtime.conversation_store.load(self.conversation_id)
            # A task can become a split-task parent while it is running. Resolve
            # again at write time so its final record lands in the shared scope.
            resolved_store = helpers._memory_store_for_conversation(conversation)
            if resolved_store.workspace_dir != self.memory_store.workspace_dir:
                self.memory_store = resolved_store
                if self.tool_executor:
                    self.tool_executor.memory_store = resolved_store
            requests = [
                str(event.get("content", ""))
                for event in conversation.get("messages", [])
                if event.get("type") == "user" and str(event.get("content", "")).strip()
            ]
            path = resolved_store.upsert_conversation_record(
                session_id=self.conversation_id,
                title=str(conversation.get("title", "")),
                user_requests=requests,
                summary=self.accumulated_compression,
            )
            return str(path)
        except Exception:
            # Memory indexing must never prevent a user task from completing.
            return ""

    def _auto_compress_if_needed(self, progress_callback=None, cancelled=None):
        """Synchronously compress memory when it exceeds the configured threshold."""
        snapshot = self.get_compression_snapshot()
        if snapshot["tokens_before"] <= self.compress_at:
            return None
        return self._compress_current_task_manual(progress_callback, snapshot, cancelled=cancelled)

    def _history_token_estimate(self) -> int:
        """Return the legacy history-only estimate used before a graph snapshot."""
        all_history = self.memory_manager.load_execution_history()
        if all_history:
            history_text = "\n".join(all_history)
            return self._estimate_tokens(history_text)
        return 0

    def _cache_context_snapshot(self, snapshot) -> dict:
        """Cache the exact compaction snapshot used at a graph boundary."""
        system_transcript = ContextCompactor.format_transcript(
            [{"role": "system", "content": snapshot.system_prompt}]
        )
        system_tokens = ContextCompactor.estimate_text_tokens(system_transcript)
        message_tokens = max(
            0,
            int(snapshot.tokens) - int(snapshot.tool_tokens) - system_tokens,
        )
        usage = {
            "tokens": int(snapshot.tokens),
            "system_tokens": system_tokens,
            "message_tokens": message_tokens,
            "tool_tokens": int(snapshot.tool_tokens),
            "context_window": int(snapshot.context_window),
            "compress_at": int(snapshot.trigger_tokens),
            "source": "graph_snapshot",
        }
        with self._context_usage_lock:
            self._latest_context_usage = usage
        return dict(usage)

    def get_current_token_usage(self) -> dict:
        """Return the same token metric used by automatic compaction."""
        with self._context_usage_lock:
            if self._latest_context_usage is not None:
                return dict(self._latest_context_usage)
        return {
            "tokens": self._history_token_estimate(),
            "system_tokens": 0,
            "message_tokens": 0,
            "tool_tokens": 0,
            "context_window": self.context_window,
            "compress_at": self.compress_at,
            "source": "history_fallback",
        }

    def get_current_tokens(self) -> int:
        """Return the latest full graph-context token estimate."""
        return int(self.get_current_token_usage()["tokens"])

    def _compress_current_task_manual(
        self, progress_callback=None, snapshot=None, cancelled=None
    ) -> dict:
        """Compress recent task memory and report real processing phases."""
        started_at = time.monotonic()
        history_before_compression = self.ai_engine.get_history() if self.ai_engine else []
        snapshot = snapshot or self.get_compression_snapshot()
        execution_history = snapshot["execution_history"]
        tokens_before = int(snapshot.get("tokens_before", 0) or 0)
        step_count = int(snapshot.get("step_count", len(execution_history)) or 0)

        def result(success, status, message, **details):
            tokens_after = int(details.pop("tokens_after", self.get_current_tokens()) or 0)
            return {
                "success": bool(success),
                "status": status,
                "message": message,
                "tokens_before": tokens_before,
                "tokens_after": tokens_after,
                "released_tokens": max(0, tokens_before - tokens_after),
                "step_count": step_count,
                "duration_ms": int(max(0, time.monotonic() - started_at) * 1000),
                "archive_path": details.pop("archive_path", ""),
                **details,
            }

        def report(stage, content):
            if not progress_callback:
                return
            with contextlib.suppress(Exception):
                progress_callback(stage, content)

        def is_cancelled() -> bool:
            try:
                return bool(callable(cancelled) and cancelled())
            except Exception:
                return False

        if not self._compression_lock.acquire(blocking=False):
            return result(False, "busy", "已有记忆压缩正在进行")

        try:
            if not execution_history:
                return result(False, "empty", "当前没有需要压缩的近期记忆")
            if is_cancelled():
                return result(False, "cancelled", "记忆压缩已停止")

            report("memory_flush", "正在压缩前提取可供未来会话复用的长期记忆")
            flush_result = None
            if self.memory_store and self.memory_store.should_flush(
                tokens_before,
                self.context_compactor.policy.context_window,
                self.context_compactor.policy.trigger_percent,
            ):
                flush_result = self.memory_store.flush(
                    snapshot.get("flush_messages")
                    or [{"role": "user", "content": snapshot["history_text"]}],
                    self._sample_memory_flush,
                    session_id=str(
                        snapshot.get("memory_session_id")
                        or self.conversation_id
                        or secrets.token_hex(8)
                    ),
                )

            report("analyzing", "正在分析完整模型上下文与工具调用链")
            history_text = snapshot["history_text"]
            context_snapshot = snapshot.get("context_snapshot")
            if context_snapshot is None:
                context_snapshot = ContextCompactor.build_snapshot(
                    {
                        "system_prompt": "",
                        "messages": [HumanMessage(content=history_text)],
                        "step_count": step_count,
                    },
                    self.context_compactor.policy,
                )
            compacted = self.context_compactor.compact(
                context_snapshot,
                self._sample_compaction_prompt,
                progress=report,
                cancelled=is_cancelled,
            )
            if is_cancelled():
                return result(False, "cancelled", "记忆压缩已停止")
            if not compacted.success:
                return result(
                    False,
                    compacted.status,
                    compacted.message,
                    attempts=compacted.attempts,
                    input_stage=compacted.input_stage,
                    error=compacted.error,
                )
            task_summary = compacted.summary

            report("archiving", "正在保存完整历史存档")
            if is_cancelled():
                return result(False, "cancelled", "记忆压缩已停止")
            archive_path = self.memory_manager.save_compression_archive(history_text)
            full_archive_path = str(self.memory_manager.memory_dir / archive_path)

            report("updating", "正在更新压缩摘要与下一轮上下文")
            if is_cancelled():
                return result(False, "cancelled", "记忆压缩已停止")
            self.accumulated_compression = f"{task_summary}\n📁 详细内容: {full_archive_path}"

            self.memory_manager.save_accumulated_compression(self.accumulated_compression)
            if self.memory_store:
                self._sync_long_term_conversation_memory()
                self._memory_context_block = self.memory_store.initial_context(
                    self.current_user_request
                )
                self.memory_manager.save_memory_context(self._memory_context_block)
            self.ai_engine.clear_history()
            self.step_count = 0
            self.memory_manager.clear_execution_history()

            return result(
                True,
                "success",
                "近期记忆已整理为结构化摘要，并保存了完整历史存档",
                tokens_after=compacted.tokens_after,
                archive_path=full_archive_path,
                attempts=compacted.attempts,
                input_stage=compacted.input_stage,
                two_pass_used=compacted.two_pass_used,
                memory_flush_status=(flush_result.status if flush_result else "below_threshold"),
                memory_flush_path=flush_result.path if flush_result else "",
            )
        finally:
            if self.ai_engine:
                self.ai_engine.conversation_history = history_before_compression
            self._compression_lock.release()

    def _clear_history(self) -> dict:
        """与 CLI 完全一致的清除历史逻辑"""
        if self.ai_engine:
            self.ai_engine.clear_history()
        self.step_count = 0
        self.web_search_count = 0
        self.allow_all_commands = self.auto_allow_all_commands
        self.accumulated_compression = ""
        self._memory_context_block = ""
        self.tool_loop_guard.reset()
        self.memory_manager.clear_all()
        with self._context_usage_lock:
            self._latest_context_usage = None
        return {"success": True, "message": "历史会话已清除，记忆文件已删除"}

    def clear_conversation(self):
        return self._clear_history()

    def _build_context(self) -> str:
        """Build context from memory files and accumulated compression（与 CLI 完全一致）"""
        context_parts = []

        if self._uses_persisted_short_term_context:
            self.accumulated_compression = self.memory_manager.load_accumulated_compression()

        # 添加累积的压缩摘要
        if self.accumulated_compression:
            context_parts.append("【之前的任务摘要】")
            context_parts.append(self.accumulated_compression)
            context_parts.append("")

        # 从记忆文件加载当前执行历史
        execution_history = self.memory_manager.load_execution_history()
        if execution_history:
            context_parts.append("【当前任务执行过程】")
            for entry in execution_history:
                context_parts.append(f"- {entry}")
        else:
            context_parts.append("还没有执行任何步骤。")

        loop_notice = self.tool_loop_guard.context_notice()
        if loop_notice:
            context_parts.extend(["", loop_notice])

        return "\n".join(context_parts)


@dataclass(frozen=True)
class _ModifiedFileSnapshot:
    """One bounded filesystem state used for a task-end change summary."""

    path: Path
    display_path: str
    exists: bool
    is_file: bool
    text: str | None
    fingerprint: str


@dataclass
class _ModifiedFileChange:
    """Keep the first and latest state when a task edits a file repeatedly."""

    before: _ModifiedFileSnapshot
    after: _ModifiedFileSnapshot


@dataclass
class DesktopRunContext:
    """Mutable state for one conversation's current submitted message."""

    conversation_id: str
    message_id: int
    generation: int
    executor: DesktopTaskExecutor
    plan_enabled: bool = False
    plan_policy: str = "off"
    voice_mode: bool = False
    multi_agent_enabled: bool = False
    mode: str = "jcodex"
    image_paths: list[str] = field(default_factory=list)
    reference_folder_paths: list[str] = field(default_factory=list)
    cancel_event: threading.Event = field(default_factory=threading.Event)
    events: queue.Queue = field(default_factory=queue.Queue)
    status: str = "running"
    # A terminal stream response can arrive before task-end summaries are
    # persisted. Frontend polling waits for this barrier before it stops.
    finalized: bool = False
    stopping: bool = False
    detached: bool = False
    worker: threading.Thread | None = None
    pending_modified_file_snapshots: dict[str, list[_ModifiedFileSnapshot]] = field(
        default_factory=dict
    )
    modified_file_changes: dict[str, _ModifiedFileChange] = field(default_factory=dict)
    # Paths already backed up this task. Each file is snapshotted only on its
    # first modification because rollback is task-level, not per-tool.
    rollback_snapshot_paths: set[str] = field(default_factory=set)
    modified_files_emitted: bool = False
    modified_files_summary: dict | None = None
    agent_team: object | None = None
    subagent_executors: dict[str, DesktopTaskExecutor] = field(default_factory=dict)


def _preview_event_publisher():
    """Late-bound preview event publisher (avoids the executor/pipeline cycle)."""
    from agent.ui.desktop.pipeline import _publish_preview_event

    return _publish_preview_event


__all__ = [
    "DesktopRunContext",
    "DesktopTaskExecutor",
    "_ModifiedFileChange",
    "_ModifiedFileSnapshot",
]
