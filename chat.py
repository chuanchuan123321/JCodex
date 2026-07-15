#!/usr/bin/env python3
"""麒麟OS-Agent - 智能操作系统助手"""

import sys
import uuid
from pathlib import Path
from typing import Any, Callable, Optional

# 添加项目根目录到 sys.path
PROJECT_ROOT = Path(__file__).parent.absolute()
sys.path.insert(0, str(PROJECT_ROOT))

# 修复macOS终端UTF-8输入问题
import os
import locale

os.environ["PYTHONIOENCODING"] = "utf-8"
locale.setlocale(locale.LC_ALL, "")

# 加载环境变量
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

load_dotenv(PROJECT_ROOT / ".env", override=True)

from agent.core.ai_engine import AIEngine
from agent.core.extended_tool_executor import ExtendedToolExecutor
from agent.core.langchain_model import AIEngineChatModel
from agent.core.langgraph_runner import (
    LangGraphRunner,
    RunResult,
    create_checkpoint_saver,
)
from agent.core.skills import SkillsLoader
from agent.core.memory_manager import MemoryManager
from agent.core.tool_loop_guard import ToolLoopGuard
from agent.bus.queue import MessageBus
from agent.bus.events import OutboundMessage
from agent.channels.manager import ChannelManager
from agent.config.loader import load_config
import json
import asyncio
import itertools
import shutil
import threading
import time


def _supports_ansi() -> bool:
    """Return whether stdout is suitable for ANSI presentation."""
    return sys.stdout.isatty() and os.getenv("TERM", "").lower() != "dumb"


ANSI_ENABLED = _supports_ansi() and "NO_COLOR" not in os.environ


def start_spinner(message: str = "思考中", show_elapsed: bool = False):
    """启动 spinner 动画，在后台线程中运行"""
    global _spinner_running, _spinner_thread
    if not ANSI_ENABLED or _spinner_running:
        return
    _spinner_running = True
    _spinner_thread = threading.Thread(
        target=_spinner_loop, args=(message, show_elapsed), daemon=True
    )
    _spinner_thread.start()
    time.sleep(0.05)  # 短暂等待确保线程开始运行

def _spinner_loop(message: str, show_elapsed: bool = False):
    """Spinner 循环"""
    import sys
    import time
    spinner_chars = ['⠋','⠙','⠹','⠸','⠼','⠴','⠦','⠧','⠇','⠏']
    started_at = time.monotonic()
    for char in itertools.cycle(spinner_chars):
        if not _spinner_running:
            break
        elapsed = f" · {int(time.monotonic() - started_at)} 秒" if show_elapsed else ""
        sys.stdout.write(
            f'\r{Colors.CYAN}{char}{Colors.RESET} '
            f'{Colors.BOLD}{message}{Colors.RESET}{Colors.DIM}{elapsed}{Colors.RESET}'
        )
        sys.stdout.flush()
        time.sleep(0.1)
    sys.stdout.write('\r' + ' ' * 60 + '\r')
    sys.stdout.flush()

def stop_spinner():
    """停止 spinner 动画"""
    global _spinner_running, _spinner_thread

    # Streaming events call this for every chunk. Once the spinner has already
    # stopped, clearing the line again would erase the chunks already printed.
    if not _spinner_running and _spinner_thread is None:
        return

    _spinner_running = False
    if _spinner_thread:
        _spinner_thread.join(timeout=0.3)  # 等待线程真正结束
    _spinner_thread = None
    # 额外清理
    import sys
    sys.stdout.write('\r' + ' ' * 60 + '\r')
    sys.stdout.flush()

_spinner_running = False
_spinner_thread = None


# 终端输出格式化类
class Colors:
    """ANSI color codes for terminal output"""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Foreground colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright foreground
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # Background colors
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"


if not ANSI_ENABLED:
    for _color_name, _color_value in vars(Colors).items():
        if _color_name.isupper() and isinstance(_color_value, str):
            setattr(Colors, _color_name, "")


class Symbols:
    """Unicode symbols for terminal output"""
    TOOL = "🔧"
    USER = "👤"
    AI = "🤖"
    THINKING = "💭"
    CHECK = "✓"
    CROSS = "✗"
    WARNING = "⚠"
    INFO = "ℹ"
    ARROW_RIGHT = "→"
    ARROW_DOWN = "↓"
    BULLET = "•"
    TAB = "  "
    VERTICAL = "│"
    UP_RIGHT = "╰"
    # Box drawing
    HORIZONTAL = "─"
    VERTICAL2 = "│"
    TOP_LEFT = "╭"
    TOP_RIGHT = "╮"
    BOTTOM_LEFT = "╰"
    BOTTOM_RIGHT = "╯"
    # Spinner variants
    SPINNER_CHARS = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']


class Box:
    """Box drawing utilities for terminal output"""

    @staticmethod
    def draw(title: str, content: str, width: int = 60) -> str:
        """Draw a box with title"""
        lines = content.split('\n')
        top = f"{Colors.DIM}{Symbols.TOP_LEFT}{Symbols.HORIZONTAL * (width - 2)}{Symbols.TOP_RIGHT}{Colors.RESET}"
        bottom = f"{Colors.DIM}{Symbols.BOTTOM_LEFT}{Symbols.HORIZONTAL * (width - 2)}{Symbols.BOTTOM_RIGHT}{Colors.RESET}"
        middle_lines = []
        for line in lines:
            if len(line) > width - 4:
                line = line[:width - 7] + "..."
            middle_lines.append(f"{Colors.DIM}{Symbols.VERTICAL2}{Colors.RESET} {line} {' ' * (width - len(line) - 4)} {Colors.DIM}{Symbols.VERTICAL2}{Colors.RESET}")
        return f"{top}\n{Colors.DIM}{Symbols.VERTICAL2}{Colors.RESET} {Colors.BOLD}{title}{Colors.RESET} {' ' * (width - len(title) - 3)} {Colors.DIM}{Symbols.VERTICAL2}{Colors.RESET}\n{Colors.DIM}{Symbols.VERTICAL2}{Colors.RESET} {Symbols.HORIZONTAL * (width - 4)} {Colors.DIM}{Symbols.VERTICAL2}{Colors.RESET}\n" + "\n".join(middle_lines) + f"\n{bottom}"


class ProgressBar:
    """Knight Rider style progress bar"""

    @staticmethod
    def knight_rider(width: int = 20, progress: float = 0.0, color: str = Colors.CYAN) -> str:
        """Draw a Knight Rider style progress bar"""
        active_pos = int(progress * (width - 1))
        trail_colors = [
            color,  # Brightest
            color,  # Slightly dimmer
            Colors.DIM + color,
            Colors.DIM,
        ]
        bar = ""
        for i in range(width):
            if i == active_pos:
                bar += f"{color}●{Colors.RESET}"
            elif i < active_pos:
                dist = active_pos - i
                if dist < len(trail_colors):
                    bar += f"{trail_colors[dist]}▪{Colors.RESET}"
                else:
                    bar += f"{Colors.DIM}·{Colors.RESET}"
            else:
                bar += f"{Colors.DIM}·{Colors.RESET}"
        return bar


class Toast:
    """Toast notification system"""

    _messages: list = []

    @classmethod
    def show(cls, message: str, variant: str = "info", duration: float = 3.0):
        """Show a toast notification"""
        symbols = {
            "success": f"{Colors.GREEN}{Symbols.CHECK}{Colors.RESET}",
            "error": f"{Colors.RED}{Symbols.CROSS}{Colors.RESET}",
            "warning": f"{Colors.YELLOW}{Symbols.WARNING}{Colors.RESET}",
            "info": f"{Colors.CYAN}{Symbols.INFO}{Colors.RESET}",
        }
        icon = symbols.get(variant, symbols["info"])
        print(f"\n{Colors.CYAN}{Symbols.VERTICAL}{Colors.RESET} {icon} {message}")

    @classmethod
    def success(cls, message: str):
        """Show success toast"""
        cls.show(message, "success")

    @classmethod
    def error(cls, message: str):
        """Show error toast"""
        cls.show(message, "error")

    @classmethod
    def warning(cls, message: str):
        """Show warning toast"""
        cls.show(message, "warning")

    @classmethod
    def info(cls, message: str):
        """Show info toast"""
        cls.show(message, "info")


# 从环境变量读取配置
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "30000"))
COMPRESS_AT = int(os.getenv("COMPRESS_AT", "25000"))
MAX_STEPS = int(os.getenv("MAX_STEPS", "20"))
MAX_WEB_SEARCHES = int(os.getenv("MAX_WEB_SEARCHES", "3"))


class NaturalTaskExecutor:
    """Execute tasks with natural conversational flow"""

    def __init__(self, bus: MessageBus | None = None):
        self.ai_engine = AIEngine()

        # Initialize memory manager
        memory_dir = Path(__file__).parent / "Memory"
        self.memory_manager = MemoryManager(str(memory_dir))

        # Initialize skills loader
        workspace_path = Path(__file__).parent / "workspace"
        workspace_path.mkdir(exist_ok=True)
        self.skills_loader = SkillsLoader(workspace_path)

        # Initialize tool executor with skills loader
        self.tool_executor = ExtendedToolExecutor(skills_loader=self.skills_loader)
        self.available_tools = self.tool_executor.get_available_tools()

        # Initialize new modules for automatic data integration
        from agent.core.data_integrator import DataIntegrator
        from agent.core.preference_manager import PreferenceManager
        from agent.core.knowledge_base import KnowledgeBase
        self.data_integrator = DataIntegrator()
        self.preference_manager = PreferenceManager()
        self.knowledge_base = KnowledgeBase()

        self.execution_history = []
        self.step_count = 0
        self.max_steps = 15  # 改为15步
        self.allow_all_commands = False  # 是否允许所有命令
        self.timer_triggered = False  # 定时器是否被触发
        self.waiting_for_timer = False  # 是否在等待定时器
        self.bus = bus  # 消息总线（用于网关模式）
        self.current_sender_id = None  # 当前消息发送者
        self.current_chat_id = None  # 当前聊天 ID
        self.current_channel = None  # 当前通道
        self.is_gateway_mode = bus is not None  # 是否在网关模式
        self.waiting_for_approval = False  # 是否在等待用户确认
        self.approval_response = None  # 用户的确认响应
        self.pending_decision = None  # 待执行的决策
        self.pending_user_request = None  # 待执行的用户请求
        self.pending_context = None  # 待执行的上下文
        self.current_user_request = ""  # 当前任务用户请求
        self.should_stop = False  # 是否应该停止当前任务
        self.is_compressing = False  # 是否正在压缩（防止消息发送）
        self.web_search_count = 0  # 网络搜索计数
        self.max_web_searches = MAX_WEB_SEARCHES  # 从环境变量读取
        self.max_steps = MAX_STEPS  # 从环境变量读取
        self.compress_at = int(os.getenv("COMPRESS_AT", "25000"))
        self.task_compression_summary = ""  # 当前任务的压缩摘要
        # 从记忆文件加载累积的压缩摘要
        self.accumulated_compression = (
            self.memory_manager.load_accumulated_compression()
        )
        self.current_task_start_step = 0  # 当前任务的起始步骤
        self.event_loop = None  # 事件循环（仅在网关模式下设置）
        self._stop_event = threading.Event()
        self.tool_loop_guard = ToolLoopGuard()
        self.langchain_model = AIEngineChatModel(engine=self.ai_engine)
        checkpoint_path = workspace_path / "data" / "langgraph_checkpoints.sqlite3"
        self.langgraph_runner = LangGraphRunner(
            self.langchain_model,
            self.available_tools,
            self._execute_langgraph_tool,
            checkpointer=create_checkpoint_saver(checkpoint_path),
            requires_approval=lambda name, _params: self._is_tool_requires_approval(
                name
            ),
            max_steps=self.max_steps,
        )
        self._known_graph_threads: set[str] = set()
        self._gateway_pending: dict[str, dict[str, Any]] = {}
        self._gateway_active: dict[str, dict[str, Any]] = {}
        self._gateway_tasks: dict[str, Any] = {}
        self._active_graph_runtime: Optional[dict[str, Any]] = None
        self._active_cancel_event: Optional[threading.Event] = None
        self._compression_lock = threading.Lock()

    def _estimate_tokens(self, text: str) -> int:
        """估算文本的token数量（基于实际测试优化）

        根据实际反馈调整的系数：
        - 中文字符：1个汉字 ≈ 1.6-1.8个token
        - 英文单词：1个单词 ≈ 1.8-2.0个token
        - 其他字符：包括标点、空格、特殊符号
        """
        import re

        # 分离中文字符、英文单词和其他字符
        chinese_chars = re.findall(r"[\u4e00-\u9fff]", text)
        text_without_chinese = re.sub(r"[\u4e00-\u9fff]", "", text)
        english_words = re.findall(r"\b[a-zA-Z]+\b", text_without_chinese)
        other_chars = (
            len(text) - len(chinese_chars) - sum(len(w) for w in english_words)
        )

        # 基于实际反馈优化的token估算
        # 中文：1汉字 ≈ 1.7 token
        chinese_tokens = int(len(chinese_chars) * 1.7)

        # 英文：1单词 ≈ 1.9 tokens
        english_tokens = int(len(english_words) * 1.9)

        # 其他字符：2.5字符 ≈ 1 token
        other_tokens = int(other_chars / 2.5) + 200  # 加上baseline和格式开销

        total_tokens = chinese_tokens + english_tokens + other_tokens
        return max(total_tokens, 1)

    def _compress_and_notify(self, event_loop=None):
        """在后台线程中执行压缩并通知用户"""
        try:
            # 压缩前估算token数（包括累积压缩摘要和执行历史）
            tokens_before = 0
            if self.accumulated_compression:
                tokens_before += self._estimate_tokens(self.accumulated_compression)
            if self.execution_history:
                history_text = "\n".join(self.execution_history)
                tokens_before += self._estimate_tokens(history_text)

            start_spinner("正在自动整理近期记忆", show_elapsed=True)
            try:
                self._compress_current_task_manual()
            finally:
                stop_spinner()
            print(
                f"{Colors.GREEN}{Symbols.CHECK} {Colors.BOLD}自动压缩完成{Colors.RESET} "
                f"{Colors.DIM}· 已整理约 {tokens_before} tokens{Colors.RESET}"
            )

            # 在网关模式下向飞书发送通知
            if (
                event_loop
                and self.is_gateway_mode
                and self.bus
                and self.current_channel
                and self.current_chat_id
            ):
                try:
                    msg = f"✅ 任务历史已自动压缩 (清除了 {tokens_before} tokens)"
                    coro = self._send_to_channel(msg)
                    asyncio.run_coroutine_threadsafe(coro, event_loop)
                except Exception:
                    pass
        except Exception as e:
            Toast.error(f"自动压缩失败: {e}")

    def _compress_current_task_async_wrapper(self):
        """异步包装器，在子线程中执行压缩"""
        try:
            self._compress_current_task_manual()
        except Exception as e:
            Toast.error(f"压缩失败: {e}")
            # 在网关模式下发送错误消息
            if (
                self.is_gateway_mode
                and self.bus
                and self.current_channel
                and self.current_chat_id
            ):
                asyncio.ensure_future(self._send_to_channel(f"⚠️ 压缩失败: {str(e)}"))

    def execute_task(
        self,
        user_request: str,
        *,
        thread_id: Optional[str] = None,
        session_key: Optional[str] = None,
        channel: Optional[str] = None,
        chat_id: Optional[str] = None,
        sender_id: Optional[str] = None,
        interactive: Optional[bool] = None,
    ) -> RunResult | None:
        """Execute one isolated task through the shared LangGraph runtime."""
        # Check for clear command
        if user_request.lower().strip() == "/clear":
            self._clear_history()
            return None

        # Check for compact command (压缩历史记录)
        if user_request.lower().strip() == "/compact":
            self._compress_current_task_manual()
            return None

        interactive = not self.is_gateway_mode if interactive is None else interactive
        normalized_thread = thread_id or f"cli:{uuid.uuid4().hex}"
        run_id = uuid.uuid4().hex
        self.web_search_count = 0
        self.tool_loop_guard.reset()
        self.current_user_request = user_request
        self.should_stop = False
        self._stop_event.clear()
        self.step_count = 0

        memory_manager = self._memory_for_session(session_key)
        accumulated_compression = memory_manager.load_accumulated_compression()
        memory_manager.append_execution_step(f"【用户请求】{user_request}")

        data_integrator = self._data_integrator_for_session(session_key)
        task_id = data_integrator.start_task(user_request)
        context = self._build_context_for(memory_manager, accumulated_compression)
        system_prompt, user_message = self._build_langgraph_prompt(
            user_request,
            context,
            memory_manager=memory_manager,
            accumulated_compression=accumulated_compression,
        )
        cancel_event = threading.Event()
        legacy_cancel_event = None if session_key else self._stop_event
        task_execution_history = (
            self.execution_history if not session_key else []
        )
        runtime = {
            "cancel_event": cancel_event,
            "cancelled": lambda: cancel_event.is_set()
            or bool(legacy_cancel_event and legacy_cancel_event.is_set()),
            "thread_id": normalized_thread,
            "run_id": run_id,
            "session_key": session_key,
            "channel": channel or self.current_channel,
            "chat_id": chat_id or self.current_chat_id,
            "sender_id": sender_id or self.current_sender_id,
            "memory_manager": memory_manager,
            "data_integrator": data_integrator,
            "task_id": task_id,
            "task_state": {"web_search_count": 0},
            "event_state": {},
            "execution_history": task_execution_history,
            "user_request": user_request,
            "compression_check": lambda state: self._graph_compression_check(
                state, memory_manager
            ),
            "compression_handler": lambda state, snapshot, progress: (
                self._graph_compression_handler(
                    state,
                    snapshot,
                    progress,
                    memory_manager=memory_manager,
                    user_request=user_request,
                )
            ),
        }
        if session_key:
            self._gateway_active[session_key] = runtime
        else:
            self._active_graph_runtime = runtime
            self._active_cancel_event = cancel_event
        self._known_graph_threads.add(normalized_thread)
        result = self.langgraph_runner.run(
            normalized_thread,
            user_message,
            system_prompt=system_prompt,
            runtime=runtime,
            emit=lambda event: self._handle_langgraph_event(event, runtime),
            run_id=run_id,
        )

        while result.status == "waiting" and interactive:
            resume_payload = self._prompt_for_graph_interrupt(result)
            if resume_payload is None:
                self.langgraph_runner.cancel(normalized_thread)
                result = RunResult("cancelled", normalized_thread, run_id)
                break
            self._record_interrupt_answer(result, resume_payload, runtime)
            result = self.langgraph_runner.resume(
                normalized_thread,
                resume_payload,
                runtime=runtime,
                emit=lambda event: self._handle_langgraph_event(event, runtime),
                run_id=run_id,
            )

        if result.status == "waiting" and session_key:
            self._store_gateway_pending(session_key, result, runtime)
            self._gateway_active.pop(session_key, None)
        else:
            self._finish_langgraph_task(result, runtime)
        if not session_key:
            self._active_graph_runtime = None
            self._active_cancel_event = None
        return result

    def _build_langgraph_prompt(
        self,
        user_request: str,
        context: str,
        *,
        memory_manager: MemoryManager,
        accumulated_compression: str,
    ) -> tuple[str, str]:
        """Render the existing Agent.md prompt for a LangGraph task."""
        from agent.tools.time_tool import TimeTool

        project_root = Path(__file__).parent
        workspace_path = project_root / "workspace"
        values = {
            "step_count": "1",
            "max_steps": str(self.max_steps),
            "step_count_minus_1": "0",
            "steps_remaining": str(self.max_steps),
            "accumulated_compression": accumulated_compression or "这是第一个任务",
            "execution_history": "\n".join(memory_manager.load_execution_history())
            or "还没有执行任何步骤",
            "current_time": TimeTool.get_current_time(),
            "web_search_count": "0",
            "max_web_searches": str(self.max_web_searches),
            "project_root": str(project_root),
            "workspace_path": str(workspace_path),
            "builtin_skills_path": str(project_root / "agent" / "skills"),
            "workspace_skills_path": str(workspace_path / "skills"),
            "desktop_path": str(Path.home() / "Desktop"),
            "output_path": str(workspace_path / "output"),
            "temp_path": str(workspace_path / "temp"),
            "cache_path": str(workspace_path / "cache"),
            "skills_summary": self.skills_loader.build_skills_summary(),
            "user_request": user_request,
            "context": context,
        }
        try:
            self.preference_manager._load_preferences()
            values["user_preferences"] = (
                self.preference_manager.generate_prompt_context()
            )
        except Exception:
            values["user_preferences"] = ""
        try:
            values["knowledge_context"] = self.knowledge_base.build_query_context(
                user_request=user_request,
                current_context=context,
                accumulated_compression=accumulated_compression,
                execution_history=values["execution_history"],
            )
        except Exception:
            values["knowledge_context"] = "（暂无相关知识）"

        template = (project_root / "Agent.md").read_text(encoding="utf-8")
        marker = "【User Task】"
        split_index = template.find(marker)
        if split_index >= 0:
            system_prompt = template[:split_index]
            user_message = template[split_index:]
        else:
            system_prompt = template
            user_message = "{user_request}\n\n{context}"
        for key, value in values.items():
            placeholder = "{" + key + "}"
            system_prompt = system_prompt.replace(placeholder, str(value))
            user_message = user_message.replace(placeholder, str(value))
        return system_prompt, user_message

    def _build_context_for(
        self, memory_manager: MemoryManager, accumulated_compression: str
    ) -> str:
        """Build task context from one CLI or gateway session only."""
        parts = []
        if accumulated_compression:
            parts.extend(["【之前的任务摘要】", accumulated_compression, ""])
        history = memory_manager.load_execution_history()
        if history:
            parts.append("【当前任务执行过程】")
            parts.extend(f"- {entry}" for entry in history)
        else:
            parts.append("还没有执行任何步骤。")
        return "\n".join(parts)

    def _graph_compression_check(
        self, state: dict[str, Any], memory_manager: MemoryManager
    ) -> Optional[dict[str, Any]]:
        """Check the active CLI/gateway memory at a graph step boundary."""
        history = memory_manager.load_execution_history()
        history_text = "\n".join(history)
        tokens_before = self._estimate_tokens(history_text) if history_text else 0
        if tokens_before <= self.compress_at:
            return None
        return {
            "execution_history": history,
            "history_text": history_text,
            "step_count": len(history),
            "tokens_before": tokens_before,
            "threshold": self.compress_at,
            "compression_id": (
                f"auto:{state.get('run_id', '')}:"
                f"{int(state.get('step_count', 0) or 0)}"
            ),
        }

    @staticmethod
    def _graph_continuation_message(user_message: str) -> str:
        return (
            "【上下文压缩后继续执行】\n"
            "请继续完成当前尚未结束的任务。不要重复摘要中已经完成的工具操作，"
            "直接从下一项未完成工作继续。\n\n"
            f"{user_message}"
        )

    def _graph_compression_handler(
        self,
        state: dict[str, Any],
        snapshot: dict[str, Any],
        progress: Callable[[str, str], None],
        *,
        memory_manager: MemoryManager,
        user_request: str,
    ) -> dict[str, Any]:
        """Compress the current session and rebuild the next model context."""
        cancel_event = None
        if str(state.get("thread_id", "")) == str(
            (self._active_graph_runtime or {}).get("thread_id", "")
        ):
            cancel_event = self._active_cancel_event
        else:
            for active in self._gateway_active.values():
                if str(active.get("thread_id", "")) == str(
                    state.get("thread_id", "")
                ):
                    cancel_event = active.get("cancel_event")
                    break
        result = self._compress_memory_snapshot(
            memory_manager,
            snapshot,
            progress=progress,
            cancelled=lambda: bool(
                cancel_event is not None
                and hasattr(cancel_event, "is_set")
                and cancel_event.is_set()
            ),
        )
        if not result.get("success"):
            return result

        accumulated = memory_manager.load_accumulated_compression()
        context = self._build_context_for(memory_manager, accumulated)
        system_prompt, user_message = self._build_langgraph_prompt(
            user_request,
            context,
            memory_manager=memory_manager,
            accumulated_compression=accumulated,
        )
        result["system_prompt"] = system_prompt
        result["replacement_messages"] = [
            HumanMessage(content=self._graph_continuation_message(user_message))
        ]
        return result

    def _memory_for_session(self, session_key: Optional[str]) -> MemoryManager:
        """Return persistent memory isolated to one gateway chat."""
        if not session_key:
            return self.memory_manager
        import hashlib

        digest = hashlib.sha256(session_key.encode("utf-8")).hexdigest()[:20]
        return MemoryManager(str(PROJECT_ROOT / "Memory" / "gateway" / digest))

    def _data_integrator_for_session(self, session_key: Optional[str]):
        """Return analytics storage isolated to one gateway chat."""
        if not session_key:
            return self.data_integrator
        from agent.core.data_integrator import DataIntegrator

        import hashlib

        digest = hashlib.sha256(session_key.encode("utf-8")).hexdigest()[:20]
        return DataIntegrator(
            data_dir=PROJECT_ROOT / "workspace" / "data" / "gateway" / digest
        )

    def _execute_langgraph_tool(
        self, name: str, params: dict[str, Any], runtime: dict[str, Any]
    ) -> str:
        """Execute a graph tool while preserving limits and memory hooks."""
        is_web_search = name in {"web_search", "websearch"}
        task_state = runtime.setdefault("task_state", {})
        search_count = int(task_state.get("web_search_count", 0))
        if is_web_search and search_count >= self.max_web_searches:
            result = (
                f"⚠️ 已达到网络搜索限制({self.max_web_searches}次)，"
                "请基于已有信息给出结论"
            )
        elif name == "set_timer":
            timer_params = dict(params)
            timer_params["executor"] = self
            self.waiting_for_timer = True
            self.timer_triggered = False
            result = self.tool_executor.execute(
                {"tool": name, "params": timer_params}
            )
            while self.waiting_for_timer and not self.timer_triggered:
                cancel_event = runtime.get("cancel_event")
                if hasattr(cancel_event, "wait") and cancel_event.wait(0.5):
                    break
        elif name == "send_file":
            result = self._send_graph_file(params, runtime)
        else:
            tool_params = dict(params)
            if name == "generate_pdf":
                tool_params["input_path"] = tool_params.get("input_path", "") or tool_params.get("input", "")
                tool_params["output_path"] = tool_params.get("output_path", "") or tool_params.get("output", "")
                tool_params.pop("input", None)
                tool_params.pop("output", None)
            result = self.tool_executor.execute(
                {"tool": name, "params": tool_params},
                conversation_id=runtime.get("session_key"),
                message_id=runtime.get("run_id"),
                runtime=runtime,
            )

        if is_web_search and not result.startswith("⚠️ 已达到网络搜索限制"):
            task_state["web_search_count"] = search_count + 1
        return str(result)

    def _send_graph_file(
        self, params: dict[str, Any], runtime: dict[str, Any]
    ) -> str:
        """Queue a file using immutable gateway routing from the task runtime."""
        if not self.bus or not runtime.get("channel") or not runtime.get("chat_id"):
            return "❌ send_file 工具仅在网关模式下可用"
        file_path = str(params.get("path") or params.get("file_path") or "")
        expanded_path = str(Path(file_path).expanduser())
        if not os.path.isabs(expanded_path):
            expanded_path = str(Path.home() / expanded_path)
        if not os.path.isfile(expanded_path):
            return f"❌ 文件不存在: {expanded_path}"
        message = OutboundMessage(
            channel=str(runtime["channel"]),
            chat_id=str(runtime["chat_id"]),
            content=expanded_path,
        )
        self._publish_gateway_message(message)
        return f"✅ 文件已发送: {Path(expanded_path).name}"

    def _handle_langgraph_event(
        self, event: dict[str, Any], runtime: dict[str, Any]
    ) -> None:
        """Render shared graph events using the existing CLI/gateway style."""
        event_type = str(event.get("type", ""))
        state = runtime.setdefault("event_state", {})
        if event_type == "model_start":
            self.step_count = int(event.get("step", self.step_count + 1))
            state["reasoning_open"] = False
            state["content_started"] = False
            start_spinner("AI思考中")
            return
        if event_type == "reasoning_delta":
            stop_spinner()
            if not state.get("reasoning_open"):
                print(
                    f"\n{Colors.DIM}{Symbols.THINKING} "
                    f"{Colors.BOLD}思考:{Colors.RESET}\n{Colors.DIM}",
                    end="",
                    flush=True,
                )
                state["reasoning_open"] = True
            print(str(event.get("content", "")), end="", flush=True)
            return
        if event_type == "content_delta":
            stop_spinner()
            if state.get("reasoning_open"):
                print(Colors.RESET + "\n")
                state["reasoning_open"] = False
            content = str(event.get("content", ""))
            print(content, end="", flush=True)
            state["content_started"] = True
            return
        if event_type == "model_end":
            stop_spinner()
            if state.get("reasoning_open"):
                print(Colors.RESET + "\n")
                state["reasoning_open"] = False
            if state.get("content_started"):
                print()
            visible_content = runtime.get("memory_manager", self.memory_manager).strip_reasoning(
                str(event.get("content", ""))
            )
            tool_calls = event.get("tool_calls") or []
            if visible_content and tool_calls:
                runtime.get("memory_manager", self.memory_manager).append_execution_step(
                    f"【AI响应】{visible_content}"
                )
                if self.is_gateway_mode:
                    self._send_runtime_message(runtime, f"🤖 {visible_content}")
            state["content_started"] = False
            return
        if event_type == "tool_preparing":
            stop_spinner()
            name = str(event.get("tool", "工具"))
            print(
                f"\n{Colors.CYAN}{Symbols.TOOL} {Colors.BOLD}"
                f"正在准备 {name}{Colors.RESET}"
            )
            start_spinner(f"生成{name}参数", show_elapsed=True)
            return
        if event_type == "tool_start":
            stop_spinner()
            name = str(event.get("tool", "工具"))
            print(
                f"\n{Colors.CYAN}{Symbols.TOOL} {Colors.BOLD}"
                f"执行工具: {name}{Colors.RESET}"
            )
            start_spinner(f"执行{name}", show_elapsed=True)
            return
        if event_type == "tool_end":
            stop_spinner()
            name = str(event.get("tool", "工具"))
            result = str(event.get("result", ""))
            params = event.get("params", {})
            memory_manager = runtime.get("memory_manager", self.memory_manager)
            data_integrator = runtime.get("data_integrator", self.data_integrator)
            history_entry = (
                f"执行 {name}:\n"
                f"{json.dumps({'tool': name, 'params': params}, ensure_ascii=False)}\n"
                f"结果: {result}"
            )
            runtime.setdefault("execution_history", self.execution_history).append(
                history_entry
            )
            memory_manager.append_execution_step(history_entry)
            try:
                data_integrator.ingest_tool_result(
                    tool_name=name,
                    params=params if isinstance(params, dict) else {},
                    result=result,
                    task_id=runtime.get("task_id"),
                )
            except Exception:
                pass
            print(self._format_tool_result(name, result))
            return
        if event_type == "compression_start":
            stop_spinner()
            tokens = int(event.get("tokens_before", 0) or 0)
            print(
                f"\n{Colors.MAGENTA}{Symbols.INFO} {Colors.BOLD}"
                f"近期记忆达到 {tokens} tokens，暂停下一步骤进行压缩{Colors.RESET}"
            )
            start_spinner("正在自动压缩近期记忆", show_elapsed=True)
            return
        if event_type == "compression_progress":
            stop_spinner()
            content = str(event.get("content", "正在整理近期记忆"))
            start_spinner(content, show_elapsed=True)
            return
        if event_type == "compression_end":
            stop_spinner()
            success = bool(event.get("success", False))
            message = str(event.get("message", "记忆压缩已结束"))
            released = int(event.get("released_tokens", 0) or 0)
            if success:
                print(
                    f"{Colors.GREEN}{Symbols.CHECK} {Colors.BOLD}"
                    f"{message}{Colors.RESET} {Colors.DIM}· 释放约 {released} tokens，"
                    f"继续当前任务{Colors.RESET}"
                )
            else:
                print(
                    f"{Colors.YELLOW}{Symbols.WARNING} {message}，"
                    f"保留原上下文继续任务{Colors.RESET}"
                )
            return
        if event_type == "interrupt":
            stop_spinner()
            return
        if event_type == "error":
            stop_spinner()
            Toast.error(str(event.get("error", "任务执行失败")))
        elif event_type == "cancelled":
            stop_spinner()
            Toast.warning("任务已停止")

    def _prompt_for_graph_interrupt(
        self, result: RunResult
    ) -> Optional[dict[str, Any]]:
        """Collect a CLI answer for a graph interrupt and resume it."""
        if not result.pending:
            return None
        payload = result.pending.value
        if result.pending.kind == "approval":
            tool_name = str(payload.get("tool", "工具"))
            params = payload.get("params", {})
            print(
                f"\n{Colors.YELLOW}{Symbols.WARNING} {Colors.BOLD}"
                f"AI 想要执行:{Colors.RESET} {tool_name}"
            )
            print(
                f"{Colors.DIM}{Symbols.VERTICAL} 详情: "
                f"{self._get_action_description(tool_name, params)}{Colors.RESET}\n"
            )
            action = self._ask_for_approval()
            action_map = {"yes": "approve", "all": "all", "no": "deny"}
            return {
                "kind": "approval",
                "action": action_map.get(action, "deny"),
            }
        return self._ask_graph_questions(payload.get("questions", []))

    def _ask_graph_questions(
        self, questions: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Ask question-tool choices synchronously in terminal mode."""
        answers: list[list[str]] = []
        supplements: list[str] = []
        lines = []
        for index, question in enumerate(questions, 1):
            header = str(question.get("header") or f"问题 {index}")
            prompt = str(question.get("question") or header)
            options = [
                option
                for option in question.get("options", [])
                if isinstance(option, dict) and str(option.get("label", "")).strip()
            ]
            print(f"\n{Colors.CYAN}{Colors.BOLD}【{header}】{Colors.RESET}")
            print(prompt)
            for option_index, option in enumerate(options, 1):
                description = str(option.get("description", "")).strip()
                suffix = f" — {description}" if description else ""
                print(f"  {option_index}. {option['label']}{suffix}")
            multiple = bool(question.get("multiple", False))
            allow_free_text = bool(question.get("allow_free_text", False))
            selection_required = bool(question.get("selection_required", True))
            free_text_required = bool(question.get("free_text_required", False))
            hint = "可多选，用逗号分隔" if multiple else "输入序号或选项文字"
            if allow_free_text:
                hint += "；也可直接输入补充文字"
                free_text_label = str(
                    question.get("free_text_label", "补充说明")
                ).strip()
                placeholder = str(question.get("free_text_placeholder", "")).strip()
                print(
                    f"  {free_text_label}"
                    f"{'（必填）' if free_text_required else '（可选）'}"
                    f"{f'：{placeholder}' if placeholder else ''}"
                )
            while True:
                raw = input(f"{hint}: ").strip()
                choices = [item.strip() for item in raw.replace("，", ",").split(",")]
                selected = []
                labels = [str(option["label"]) for option in options]
                for choice in choices:
                    if choice.isdigit() and 1 <= int(choice) <= len(labels):
                        selected.append(labels[int(choice) - 1])
                    elif choice in labels:
                        selected.append(choice)
                selected = list(dict.fromkeys(selected))
                supplement = ""
                if allow_free_text:
                    unmatched = [
                        choice
                        for choice in choices
                        if choice
                        and not (
                            choice.isdigit()
                            and 1 <= int(choice) <= len(labels)
                        )
                        and choice not in labels
                    ]
                    if unmatched:
                        supplement = ", ".join(unmatched)
                    if not supplement:
                        supplement = input("补充内容（留空跳过）: ").strip()
                if not multiple:
                    selected = selected[:1]
                valid_selection = (
                    not selection_required
                    or bool(selected)
                    or (allow_free_text and bool(supplement))
                )
                if valid_selection and (not free_text_required or supplement):
                    break
                print(f"{Colors.YELLOW}请选择有效选项或填写补充内容。{Colors.RESET}")
            answers.append(selected)
            supplements.append(supplement)
            response = ", ".join(selected)
            if supplement:
                response = f"{response}；补充：{supplement}" if response else f"补充：{supplement}"
            lines.append(f"- {prompt}: {response}")
        content = "用户已回答 question 工具：\n" + "\n".join(lines)
        return {
            "kind": "question",
            "answers": answers,
            "supplements": supplements,
            "content": content,
        }

    def _record_interrupt_answer(
        self,
        result: RunResult,
        resume_payload: dict[str, Any],
        runtime: dict[str, Any],
    ) -> None:
        """Persist only the visible answer/approval, never model reasoning."""
        memory_manager = runtime.get("memory_manager", self.memory_manager)
        if result.pending and result.pending.kind == "question":
            content = str(resume_payload.get("content", "")).strip()
            if content:
                memory_manager.append_execution_step(content)
        elif result.pending and result.pending.kind == "approval":
            action = str(resume_payload.get("action", "deny"))
            memory_manager.append_execution_step(f"【用户审批】{action}")

    def _store_gateway_pending(
        self, session_key: str, result: RunResult, runtime: dict[str, Any]
    ) -> None:
        """Store an interrupt under its gateway chat instead of global flags."""
        self._gateway_pending[session_key] = {
            "thread_id": result.thread_id,
            "run_id": result.run_id,
            "pending": result.pending,
            "runtime": runtime,
        }
        if result.pending:
            self._send_runtime_message(
                runtime, self._format_gateway_interrupt(result.pending)
            )

    def _format_gateway_interrupt(self, pending) -> str:
        """Render approval/question interrupts as a compact gateway prompt."""
        payload = pending.value
        if pending.kind == "approval":
            tool_name = str(payload.get("tool", "工具"))
            params = payload.get("params", {})
            return (
                "⚠️ 【需要确认】\n\n"
                f"AI 想要执行：{self._get_action_description(tool_name, params)}\n\n"
                "请回复 yes / all / no"
            )
        blocks = ["❓ 【需要你的选择】"]
        questions = payload.get("questions", [])
        for question_index, question in enumerate(questions, 1):
            blocks.append(
                f"\n{question_index}. {question.get('question', question.get('header', '请选择'))}"
            )
            for option_index, option in enumerate(question.get("options", []), 1):
                description = str(option.get("description", "")).strip()
                suffix = f" — {description}" if description else ""
                blocks.append(f"   {option_index}) {option.get('label', '')}{suffix}")
            if question.get("allow_free_text", False):
                label = str(question.get("free_text_label", "补充说明")).strip()
                required = "（必填）" if question.get("free_text_required", False) else "（可选）"
                blocks.append(f"   可补充文字：{label}{required}")
        if len(questions) > 1:
            blocks.append("\n多个问题请用分号分隔回答；多选请用逗号分隔。")
        else:
            blocks.append("\n请回复序号或选项文字；多选请用逗号分隔。")
        return "\n".join(blocks)

    def resume_gateway_task(
        self, session_key: str, response: str
    ) -> RunResult | None:
        """Resume only the pending task belonging to one gateway session."""
        stored = self._gateway_pending.get(session_key)
        if not stored:
            return None
        pending = stored["pending"]
        if pending.kind == "approval":
            normalized = response.strip().lower()
            action_map = {
                "yes": "approve",
                "y": "approve",
                "all": "all",
                "a": "all",
                "no": "deny",
                "n": "deny",
            }
            if normalized not in action_map:
                return RunResult(
                    "waiting",
                    stored["thread_id"],
                    stored["run_id"],
                    pending=pending,
                    error="请回复 yes/all/no",
                )
            resume_payload = {"kind": "approval", "action": action_map[normalized]}
        else:
            resume_payload = self._parse_gateway_question_answer(
                pending.value.get("questions", []), response
            )
            if resume_payload is None:
                return RunResult(
                    "waiting",
                    stored["thread_id"],
                    stored["run_id"],
                    pending=pending,
                    error="请回复有效选项（序号或选项文字）",
                )
        runtime = stored["runtime"]
        self._gateway_active[session_key] = runtime
        self._record_interrupt_answer(
            RunResult(
                "waiting",
                stored["thread_id"],
                stored["run_id"],
                pending=pending,
            ),
            resume_payload,
            runtime,
        )
        result = self.langgraph_runner.resume(
            stored["thread_id"],
            resume_payload,
            runtime=runtime,
            emit=lambda event: self._handle_langgraph_event(event, runtime),
            run_id=stored["run_id"],
        )
        if result.status == "waiting":
            self._store_gateway_pending(session_key, result, runtime)
            self._gateway_active.pop(session_key, None)
        else:
            self._gateway_pending.pop(session_key, None)
            self._finish_langgraph_task(result, runtime)
        return result

    @staticmethod
    def _parse_gateway_question_answer(
        questions: list[dict[str, Any]], response: str
    ) -> Optional[dict[str, Any]]:
        """Parse one text response into ordered question answers."""
        raw_groups = [item.strip() for item in response.split(";")]
        if len(questions) > 1 and len(raw_groups) != len(questions):
            return None
        if len(questions) == 1:
            raw_groups = [response.strip()]
        answers = []
        supplements = []
        lines = []
        for question, raw_group in zip(questions, raw_groups):
            labels = [
                str(item.get("label", "")).strip()
                for item in question.get("options", [])
                if isinstance(item, dict) and str(item.get("label", "")).strip()
            ]
            selected = []
            for item in raw_group.replace("，", ",").split(","):
                value = item.strip()
                if value.isdigit() and 1 <= int(value) <= len(labels):
                    selected.append(labels[int(value) - 1])
                elif value in labels:
                    selected.append(value)
            selected = list(dict.fromkeys(selected))
            allow_free_text = bool(question.get("allow_free_text", False))
            selection_required = bool(question.get("selection_required", True))
            free_text_required = bool(question.get("free_text_required", False))
            supplement = ""
            if allow_free_text:
                unmatched = []
                for item in raw_group.replace("，", ",").split(","):
                    value = item.strip()
                    if (
                        value
                        and not (
                            value.isdigit() and 1 <= int(value) <= len(labels)
                        )
                        and value not in labels
                    ):
                        unmatched.append(value)
                supplement = ", ".join(unmatched)
            if selection_required and not selected and not supplement:
                return None
            if free_text_required and not supplement:
                return None
            if not question.get("multiple", False):
                selected = selected[:1]
            answers.append(selected)
            supplements.append(supplement)
            response_text = ", ".join(selected)
            if supplement:
                response_text = (
                    f"{response_text}；补充：{supplement}"
                    if response_text
                    else f"补充：{supplement}"
                )
            lines.append(
                f"- {question.get('question', question.get('header', '问题'))}: "
                f"{response_text}"
            )
        return {
            "kind": "question",
            "answers": answers,
            "supplements": supplements,
            "content": "用户已回答 question 工具：\n" + "\n".join(lines),
        }

    def _finish_langgraph_task(
        self, result: RunResult, runtime: dict[str, Any]
    ) -> None:
        """Close task bookkeeping after a terminal graph run."""
        stop_spinner()
        session_key = runtime.get("session_key")
        if session_key:
            self._gateway_active.pop(str(session_key), None)
        if result.status != "waiting":
            deleted_checkpoint = False
            try:
                self.langgraph_runner.delete_thread(result.thread_id)
                deleted_checkpoint = True
            except Exception:
                pass
            self._known_graph_threads.discard(result.thread_id)
            discard_plan = getattr(
                getattr(self, "tool_executor", None),
                "discard_plan_snapshot",
                None,
            )
            if callable(discard_plan):
                try:
                    discard_plan(
                        runtime.get("session_key"),
                        runtime.get("run_id") or result.run_id,
                    )
                except Exception:
                    pass
            if deleted_checkpoint:
                try:
                    self.langgraph_runner.vacuum_checkpoint_store()
                except Exception:
                    pass
        memory_manager = runtime.get("memory_manager", self.memory_manager)
        data_integrator = runtime.get("data_integrator", self.data_integrator)
        if result.status == "complete":
            final_content = memory_manager.strip_reasoning(result.content)
            if final_content:
                memory_manager.append_execution_step(f"【最终回应】{final_content}")
                if self.is_gateway_mode:
                    self._send_runtime_message(runtime, f"✅ {final_content}")
            print(
                f"\n{Colors.GREEN}{Symbols.CHECK} {Colors.BOLD}"
                f"任务完成{Colors.RESET}\n"
            )
            data_integrator.end_task("已完成")
        elif result.status == "cancelled":
            data_integrator.end_task("已停止")
        elif result.status == "error":
            data_integrator.end_task("失败")

    def _send_runtime_message(
        self, runtime: dict[str, Any], content: str
    ) -> None:
        """Publish using the routing captured when the gateway task began."""
        if not self.bus or not runtime.get("channel") or not runtime.get("chat_id"):
            return
        self._publish_gateway_message(
            OutboundMessage(
                channel=str(runtime["channel"]),
                chat_id=str(runtime["chat_id"]),
                content=content,
            )
        )

    def _publish_gateway_message(self, message: OutboundMessage) -> None:
        """Publish safely from the gateway loop or a worker thread."""
        if not self.bus:
            return
        coroutine = self.bus.publish_outbound(message)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            loop.create_task(coroutine)
        elif self.event_loop and self.event_loop.is_running():
            asyncio.run_coroutine_threadsafe(coroutine, self.event_loop)
        else:
            coroutine.close()

    def _execute_step(self, user_request: str, context: str):
        """Execute a single step with natural description"""
        # 检查是否应该停止任务
        if self.should_stop or self._stop_event.is_set():
            print(f"\n⏹️  {Colors.BOLD}任务已停止{Colors.RESET}\n")
            self.should_stop = False
            self._stop_event.clear()
            self.data_integrator.end_task("已停止")
            return

        if self.step_count > self.max_steps:
            print(f"\n{Colors.YELLOW}{Symbols.WARNING} {Colors.BOLD}已达到最大步数限制({self.max_steps})，任务停止{Colors.RESET}\n")
            self.data_integrator.end_task("已停止")
            return

        # Get current time
        from agent.tools.time_tool import TimeTool

        current_time = TimeTool.get_current_time()

        # Build skills context (two-layer strategy like nanobot)
        # 1. Get all skills summary
        skills_summary = self.skills_loader.build_skills_summary()

        # 2. AI 根据需要主动调用 load_skill 来加载 skills

        # 3. Get project paths
        project_root = Path(__file__).parent
        workspace_path = project_root / "workspace"
        builtin_skills_path = project_root / "agent" / "skills"
        workspace_skills_path = workspace_path / "skills"
        output_path = workspace_path / "output"
        temp_path = workspace_path / "temp"
        cache_path = workspace_path / "cache"
        desktop_path = Path.home() / "Desktop"

        # Build the prompt for this step
        # 从 Agent.md 读取提示词模板
        agent_md_path = Path(__file__).parent / "Agent.md"

        # 读取 Agent.md 模板
        with open(agent_md_path, "r", encoding="utf-8") as f:
            agent_template = f.read()

        # 分离系统提示词和用户消息部分
        # 系统提示词：从开头到【用户任务】之前
        # 用户消息：从【用户任务】开始
        split_marker = "【User Task】"
        split_idx = agent_template.find(split_marker)

        if split_idx >= 0:
            system_prompt_template = agent_template[:split_idx]
            user_message_template = agent_template[split_idx:]
        else:
            # 如果找不到分割点，全部作为系统提示词
            system_prompt_template = agent_template
            user_message_template = ""

        # 替换系统提示词中的变量
        system_prompt = system_prompt_template
        system_prompt = system_prompt.replace("{step_count}", str(self.step_count))
        system_prompt = system_prompt.replace("{max_steps}", str(self.max_steps))
        system_prompt = system_prompt.replace(
            "{step_count_minus_1}", str(self.step_count - 1)
        )
        system_prompt = system_prompt.replace(
            "{steps_remaining}", str(self.max_steps - self.step_count + 1)
        )
        system_prompt = system_prompt.replace(
            "{accumulated_compression}",
            self.accumulated_compression
            if self.accumulated_compression
            else "这是第一个任务",
        )

        # 加载execution_history文件内容
        execution_history_content = self.memory_manager.load_execution_history()
        execution_history_text = (
            "\n".join(execution_history_content)
            if execution_history_content
            else "还没有执行任何步骤"
        )
        system_prompt = system_prompt.replace(
            "{execution_history}", execution_history_text
        )

        system_prompt = system_prompt.replace("{current_time}", current_time)
        system_prompt = system_prompt.replace(
            "{web_search_count}", str(self.web_search_count)
        )
        system_prompt = system_prompt.replace(
            "{max_web_searches}", str(self.max_web_searches)
        )
        system_prompt = system_prompt.replace("{project_root}", str(project_root))
        system_prompt = system_prompt.replace("{workspace_path}", str(workspace_path))
        system_prompt = system_prompt.replace(
            "{builtin_skills_path}", str(builtin_skills_path)
        )
        system_prompt = system_prompt.replace(
            "{workspace_skills_path}", str(workspace_skills_path)
        )
        system_prompt = system_prompt.replace("{desktop_path}", str(desktop_path))
        system_prompt = system_prompt.replace("{output_path}", str(output_path))
        system_prompt = system_prompt.replace("{temp_path}", str(temp_path))
        system_prompt = system_prompt.replace("{cache_path}", str(cache_path))
        system_prompt = system_prompt.replace("{skills_summary}", skills_summary)

        # 添加用户偏好上下文
        try:
            # 使用实例的preference_manager，并重新加载以获取最新变化
            self.preference_manager._load_preferences()
            preference_context = self.preference_manager.generate_prompt_context()
            system_prompt = system_prompt.replace("{user_preferences}", preference_context)
        except Exception:
            system_prompt = system_prompt.replace("{user_preferences}", "")

        # 添加知识库检索上下文
        try:
            knowledge_context = self.knowledge_base.build_query_context(
                user_request=user_request,
                current_context=context,
                accumulated_compression=self.accumulated_compression,
                execution_history=execution_history_text,
            )
            system_prompt = system_prompt.replace("{knowledge_context}", knowledge_context)
        except Exception:
            system_prompt = system_prompt.replace("{knowledge_context}", "（暂无相关知识）")

        # 替换用户消息中的变量
        user_message = user_message_template
        user_message = user_message.replace("{user_request}", user_request)
        user_message = user_message.replace("{context}", context)

        # 获取工具定义
        available_tools = self.tool_executor.get_available_tools()

        # AI 思考时显示 spinner
        start_spinner("AI思考中")

        try:
            result = self.ai_engine.process_with_tools(
                user_message,
                system_prompt=system_prompt,
                tools=available_tools,
            )
        finally:
            stop_spinner()

        if self.should_stop or self._stop_event.is_set():
            self.should_stop = False
            self._stop_event.clear()
            self.data_integrator.end_task("已停止")
            Toast.warning("任务已停止")
            return

        # 检查是否有工具调用
        if result.get("tool_calls"):
            # 有工具调用 - 先显示思考内容（从 <think> 标签中提取）
            thinking_content = result.get("content", "")
            if thinking_content:
                # 提取 <think>...</think> 标签之间的内容
                import re
                think_match = re.search(r'<think>([\s\S]*?)</think>', thinking_content)
                if think_match:
                    think_content = think_match.group(1).strip()
                    # 移除response中的think标签，避免重复打印
                    thinking_content_clean = re.sub(r'<think>[\s\S]*?</think>', '', thinking_content)
                    if think_content:
                        print(f"\n{Colors.DIM}{Symbols.THINKING} {Colors.BOLD}思考:{Colors.RESET}\n{Colors.DIM}{think_content}{Colors.RESET}\n")
                        if (
                            self.is_gateway_mode
                            and self.bus
                            and self.current_channel
                            and self.current_chat_id
                        ):
                            asyncio.ensure_future(self._send_to_channel(f"💭 *思考:*\n{think_content}"))
                    # 打印去除think标签后的内容
                    if thinking_content_clean.strip():
                        print(thinking_content_clean)

            # 逐个处理工具调用
            for tool_call in result["tool_calls"]:
                tool_name = tool_call.name
                params = tool_call.arguments

                # 保存到记忆
                import json

                tool_json = json.dumps(
                    {
                        "tool": tool_name,
                        "params": params,
                    },
                    ensure_ascii=False,
                )
                history_entry = f"执行 {tool_name}:\n{tool_json}\n结果: "
                is_web_search_tool = tool_name in {"web_search", "websearch"}

                guard_decision = self.tool_loop_guard.before_call(tool_name, params)
                if guard_decision["action"] != "execute":
                    tool_result = guard_decision["result"]
                    history_entry += tool_result
                    print(
                        f"\n{Colors.YELLOW}{Symbols.WARNING} "
                        f"{tool_result}{Colors.RESET}\n"
                    )
                    self.execution_history.append(history_entry)
                    self.memory_manager.append_execution_step(history_entry)
                    continue

                if is_web_search_tool and self.web_search_count >= self.max_web_searches:
                    tool_result = f"⚠️ 已达到网络搜索限制({self.max_web_searches}次)"
                    history_entry += tool_result
                    print(f"\n{Colors.YELLOW}{Symbols.WARNING} {tool_result}{Colors.RESET}")
                    self.execution_history.append(history_entry)
                    self.memory_manager.append_execution_step(history_entry)
                    continue

                # 检查工具是否需要确认
                requires_approval = self._is_tool_requires_approval(tool_name)

                # 如果不是允许所有命令，且工具需要确认，则询问用户
                if not self.allow_all_commands and requires_approval:
                    if self.is_gateway_mode:
                        # 网关模式：发送确认请求到飞书
                        action_desc = self._get_action_description(tool_name, params)
                        approval_msg = f"""⚠️ 【需要确认】

AI 想要执行以下操作：
{action_desc}

请在飞书中回复：
- "yes" 或 "y" - 执行此命令
- "all" 或 "a" - 允许本任务所有命令
- "no" 或 "n" - 取消此命令
"""
                        if self.bus and self.current_channel and self.current_chat_id:
                            msg = OutboundMessage(
                                channel=self.current_channel,
                                chat_id=self.current_chat_id,
                                content=approval_msg,
                            )
                            asyncio.ensure_future(self.bus.publish_outbound(msg))

                        # 设置等待标志
                        self.waiting_for_approval = True

                        self.pending_decision = {
                            "action": "execute_tool",
                            "tool": tool_name,
                            "params": params,
                        }
                        self.pending_user_request = user_request
                        self.pending_context = context
                        print(f"\n{Colors.YELLOW}{Symbols.WARNING} {Colors.BOLD}等待用户确认...{Colors.RESET}\n")
                        return
                    else:
                        # CLI 模式
                        print(f"\n{Colors.YELLOW}{Symbols.WARNING} {Colors.BOLD}AI 想要执行:{Colors.RESET} {tool_name}")
                        action_desc = self._get_action_description(tool_name, params)
                        print(f"{Colors.DIM}{Symbols.VERTICAL} 详情: {action_desc}{Colors.RESET}\n")
                        approval = self._ask_for_approval()
                        if approval == "no":
                            tool_result = "用户拒绝执行此命令"
                            print(f"\n{Colors.RED}{Symbols.CROSS} {tool_result}{Colors.RESET}\n")
                            history_entry += tool_result
                            self.execution_history.append(history_entry)
                            self.memory_manager.append_execution_step(history_entry)
                            self.step_count += 1
                            context = self._build_context()
                            self._execute_step(user_request, context)
                            return
                        elif approval == "all":
                            self.allow_all_commands = True

                # 执行工具
                print(f"\n{Colors.CYAN}{Symbols.TOOL} {Colors.BOLD}执行工具: {tool_name}{Colors.RESET}")
                stop_spinner()  # 先停止AI思考spinner
                start_spinner(f"执行{tool_name}")

                tool_result = self.tool_executor.execute(
                    {"tool": tool_name, "params": params}
                )
                self.tool_loop_guard.record_result(
                    tool_name,
                    params,
                    tool_result,
                    guard_decision["signature"],
                    guard_decision["kind"],
                )
                stop_spinner()

                # 格式化输出结果（支持折叠长输出）
                formatted_result = self._format_tool_result(tool_name, tool_result)
                print(formatted_result)

                # 自动记录到数据整合模块
                self.data_integrator.ingest_tool_result(
                    tool_name=tool_name,
                    params=params,
                    result=tool_result
                )

                history_entry += tool_result
                self.execution_history.append(history_entry)
                self.memory_manager.append_execution_step(history_entry)

                # 网络搜索计数
                if is_web_search_tool:
                    self.web_search_count += 1

            # 清空对话历史，继续下一步
            self.ai_engine.clear_history()
            context = self._build_context()
            self._execute_step(user_request, context)
            return

        # 没有工具调用 - 最终响应
        response = result.get("content", "")

        # 提取并显示思考内容（从 <think> 标签中提取）
        import re
        think_match = re.search(r'<think>([\s\S]*?)</think>', response)
        if think_match:
            think_content = think_match.group(1).strip()
            if think_content:
                print(f"\n{Colors.DIM}{Symbols.THINKING} {Colors.BOLD}思考:{Colors.RESET}\n{Colors.DIM}{think_content}{Colors.RESET}\n")
                if self.is_gateway_mode and self.bus and self.current_channel and self.current_chat_id:
                    asyncio.ensure_future(self._send_to_channel(f"💭 *思考:*\n{think_content}"))

        # 清空AI引擎的对话历史
        self.ai_engine.clear_history()

        # 显示AI的回答（移除think标签后打印）
        response_clean = self.memory_manager.strip_reasoning(response)
        print(response_clean)

        # 提取自然语言部分（使用移除think标签后的内容）
        natural_language = self._extract_natural_language(response_clean)

        is_final = result.get("finish_reason") == "stop" and not result.get("tool_calls")

        # 记录AI的自然语言响应到记忆文件
        # 最终响应不保存中间响应，避免重复
        if natural_language and not is_final:
            self.memory_manager.append_execution_step(f"【AI响应】{natural_language}")

        # 发送到飞书
        if natural_language and self.is_gateway_mode:
            asyncio.ensure_future(self._send_to_channel(f"🤖 {natural_language}"))

        # 检查是否是最终响应
        if is_final:
            self.memory_manager.append_execution_step(f"【最终回应】{natural_language}")
            print(f"\n{Colors.GREEN}{Symbols.CHECK} {Colors.BOLD}任务完成{Colors.RESET}\n")

            # 结束任务记录
            self.data_integrator.end_task("已完成")

            # 发送最终响应到飞书
            if response and self.is_gateway_mode:
                asyncio.ensure_future(self._send_to_channel(f"✅ {response}"))

            return

        # 继续执行下一步
        self.step_count += 1
        context = self._build_context()
        self._execute_step(user_request, context)

    async def _execute_step_async(self, user_request: str, context: str):
        """Async wrapper for _execute_step to avoid nested asyncio issues"""
        self._execute_step(user_request, context)

    def _compress_current_task_manual(self) -> None:
        """Manually compress the current execution history into a summary"""
        if self.is_compressing:
            Toast.info("记忆压缩已经在进行中")
            return
        # 设置压缩标志，防止消息发送
        self.is_compressing = True
        try:
            self._compress_current_task_impl()
        finally:
            self.is_compressing = False

    def _compress_memory_for_gateway(self, memory_manager: MemoryManager) -> str:
        """Compress one isolated gateway chat without swapping global memory."""
        history = memory_manager.load_execution_history()
        if not history:
            return "⚠️ 没有执行历史可以压缩"
        history_text = "\n".join(history)
        snapshot = {
            "execution_history": history,
            "history_text": history_text,
            "step_count": len(history),
            "tokens_before": self._estimate_tokens(history_text),
        }
        result = self._compress_memory_snapshot(memory_manager, snapshot)
        if not result.get("success"):
            return f"❌ 压缩失败: {result.get('message', '未知错误')}"
        return f"✅ 历史记录已压缩\n📁 存档位置: {result.get('archive_path', '')}"

    def _compress_memory_snapshot(
        self,
        memory_manager: MemoryManager,
        snapshot: dict[str, Any],
        *,
        progress: Optional[Callable[[str, str], None]] = None,
        cancelled: Optional[Callable[[], bool]] = None,
    ) -> dict[str, Any]:
        """Compress one session without mutating another session's memory."""
        started_at = time.monotonic()
        history = list(snapshot.get("execution_history") or [])
        history_text = memory_manager.strip_reasoning(
            str(snapshot.get("history_text") or "\n".join(history))
        )
        tokens_before = int(snapshot.get("tokens_before", 0) or 0)
        step_count = int(snapshot.get("step_count", len(history)) or 0)

        def build_result(success: bool, status: str, message: str, **details):
            tokens_after = int(details.pop("tokens_after", tokens_before) or 0)
            return {
                "success": success,
                "status": status,
                "message": message,
                "tokens_before": tokens_before,
                "tokens_after": tokens_after,
                "released_tokens": max(0, tokens_before - tokens_after),
                "step_count": step_count,
                "duration_ms": int(max(0, time.monotonic() - started_at) * 1000),
                "archive_path": str(details.pop("archive_path", "")),
                **details,
            }

        def is_cancelled() -> bool:
            try:
                return bool(cancelled and cancelled())
            except Exception:
                return False

        def report(stage: str, content: str) -> None:
            if progress:
                progress(stage, content)

        if not self._compression_lock.acquire(blocking=False):
            return build_result(False, "busy", "已有记忆压缩正在进行")
        try:
            if not history_text.strip():
                return build_result(False, "empty", "当前没有需要压缩的近期记忆")
            if is_cancelled():
                return build_result(False, "cancelled", "记忆压缩已停止")

            report("analyzing", "正在分析近期对话与执行记录")
            prompt = (
                "请简洁总结以下执行过程，保留用户请求、已完成步骤、关键工具参数、"
                "重要结果和仍未完成事项。使用 Markdown 表格，不要输出思考过程。\n\n"
                + history_text
            )
            report("summarizing", "正在提炼关键决策、工具结果与未完成事项")
            try:
                response = self.langchain_model.invoke(prompt)
                summary = memory_manager.strip_reasoning(str(response.content or ""))
            except Exception as exc:
                return build_result(False, "error", f"AI调用失败: {exc}")
            if is_cancelled():
                return build_result(False, "cancelled", "记忆压缩已停止")
            if not summary:
                return build_result(False, "error", "AI未生成有效摘要，压缩已取消")

            report("archiving", "正在保存完整历史存档")
            archive_path = memory_manager.save_compression_archive(history_text)
            full_archive = str(memory_manager.memory_dir / archive_path)
            if is_cancelled():
                return build_result(False, "cancelled", "记忆压缩已停止")

            report("updating", "正在更新长期记忆与下一轮上下文")
            previous = memory_manager.load_accumulated_compression()
            combined = f"{summary}\n📁 详细内容: {full_archive}"
            if previous:
                combined += f"\n\n{previous}"
            memory_manager.save_accumulated_compression(combined)
            memory_manager.clear_execution_history()
            return build_result(
                True,
                "success",
                "近期记忆已整理为摘要，任务将从当前步骤继续",
                tokens_after=0,
                archive_path=full_archive,
            )
        finally:
            self._compression_lock.release()

    def _compress_current_task_impl(self) -> None:
        """Run the compression work while the lifecycle flag is held."""
        execution_history = self.memory_manager.load_execution_history()

        if not execution_history:
            Toast.warning("没有执行历史可以压缩")
            return

        # 先调用AI生成简短摘要，确保成功后再保存
        import re
        history_text = "\n".join(execution_history)
        # 移除history_text中的think标签，避免AI看到重复的思考过程
        history_text = re.sub(r'<think>[\s\S]*?</think>', '', history_text)
        step_count = len(execution_history)
        summary_prompt = f"""请以简洁的表格形式总结以下执行过程：

【执行步骤】（共 {step_count} 步）
{history_text}

请生成一个表格，包含以下列：
- 用户问题
- 步骤
- 操作描述
- 工具/命令
- 执行结果

格式：
| 用户问题 | 步骤 | 操作 | 工具/命令 | 结果 |
|---------|------|------|---------|------|
| [用户的问题] | 1 | [描述] | [工具名] | [结果] |
| | 2 | [描述] | [工具名] | [结果] |

要求：
1. 用户问题只在第一行填写，后续行留空
2. 每一步对应一行
3. 表格简洁清晰，突出关键信息
4. 不要省略任何重要步骤

表格："""

        try:
            result = self.ai_engine.call_api(summary_prompt)
            task_summary = (
                result.get("content", "") if isinstance(result, dict) else result
            )

            # 清空AI引擎的对话历史（已保存到执行历史文件）
            self.ai_engine.clear_history()

            # 检查AI是否成功返回摘要（不是错误信息）
            if not task_summary or task_summary.strip() == "":
                Toast.warning(f"AI未能生成摘要，压缩取消")
                return
            if task_summary.startswith("API Error:") or "Error:" in task_summary:
                Toast.error(f"AI调用错误，压缩取消")
                return

            # 提取并移除task_summary中的think标签内容
            import re as re_module
            think_match = re_module.search(r'<think>([\s\S]*?)</think>', task_summary)
            if think_match:
                think_content = think_match.group(1).strip()
                if think_content:
                    # 将think标签内容移除
                    task_summary = re_module.sub(r'<think>[\s\S]*?</think>', '', task_summary)

        except Exception as e:
            print(f"⚠️ AI调用失败，压缩取消\n")
            return

        # 只有AI成功返回摘要，才保存完整的执行历史到存档文件夹（按日期组织）
        archive_path = self.memory_manager.save_compression_archive(history_text)

        # 构建完整的存档路径（绝对路径）
        full_archive_path = str(self.memory_manager.memory_dir / archive_path)

        # 添加到累积压缩摘要（新的压缩添加到前面，包含存档路径和简短摘要）
        if self.accumulated_compression:
            # 新的压缩摘要添加到前面，包含存档路径和简短摘要（不显示编号）
            self.accumulated_compression = f"{task_summary}\n📁 详细内容: {full_archive_path}\n\n{self.accumulated_compression}"
        else:
            self.accumulated_compression = (
                f"{task_summary}\n📁 详细内容: {full_archive_path}"
            )

        # 保存到记忆文件
        self.memory_manager.save_accumulated_compression(self.accumulated_compression)

        # 同步记忆快照到知识库，供后续检索片段复用
        try:
            sync_result = self.knowledge_base.sync_memory_snapshot(
                archive_path=full_archive_path,
                user_request=self.current_user_request,
                summary_text=task_summary,
                history_text=history_text,
                task_id=self.data_integrator.get_current_task_id(),
            )
            print(
                f"🧠 记忆已同步到知识库: 摘要 {sync_result.get('summary_entry_id')}, "
                f"片段 {sync_result.get('fragment_count')}"
            )
        except Exception as e:
            print(f"⚠️ 记忆同步到知识库失败: {e}")

        # 回显本轮检索到的知识片段
        try:
            retrieved_summary = self.knowledge_base.format_last_retrieved_entries()
            if retrieved_summary and retrieved_summary != "（未检索到知识片段）":
                print(retrieved_summary)
        except Exception:
            pass

        # 彻底清空 AIEngine 的对话历史以减少上下文
        # 压缩摘要已经保存到文件，不需要再保留在内存中
        self.ai_engine.clear_history()
        self.current_user_request = ""

        # 清空执行历史（内存和文件）
        self.execution_history = []
        self.step_count = 0

        # 清除执行历史文件（已压缩，不再需要）
        self.memory_manager.clear_execution_history()

        print(f"✅ 历史记录已压缩并保存到记忆文件\n📁 存档位置: {full_archive_path}\n")

    def _truncate_response(self, response: str, max_length: int = 50) -> str:
        """截断长响应，超过max_length的部分用省略号表示"""
        if len(response) <= max_length:
            return response

        # 找到第max_length个字符的位置
        truncated = response[:max_length]

        # 如果截断位置在JSON标记中间，需要特殊处理
        if "===== JSON START =====" in response:
            # 分别处理自然语言部分和JSON部分
            parts = response.split("===== JSON START =====")
            if len(parts) == 2:
                natural_part = parts[0]
                json_part = "===== JSON START =====" + parts[1]

                # 截断自然语言部分
                if len(natural_part) > max_length:
                    natural_part = natural_part[:max_length] + "...\n"

                # JSON部分保持原样（因为需要解析）
                return natural_part + json_part

        return truncated + "..."

    def _extract_natural_language(self, response: str) -> str:
        """从AI响应中提取自然语言部分"""
        import re
        try:
            # 移除 <think>...</think> 内容
            cleaned = re.sub(r'<think>[\s\S]*?</think>', '', response)

            # 查找 JSON 标记
            start_marker = "===== JSON START ====="
            start_idx = cleaned.find(start_marker)

            if start_idx > 0:
                # 提取 JSON 标记之前的内容
                natural_part = cleaned[:start_idx].strip()
                # 移除 "接下来我要: " 前缀
                if natural_part.startswith("接下来我要:"):
                    natural_part = natural_part[len("接下来我要:") :].strip()
                return natural_part
            else:
                # 如果没有 JSON 标记，返回整个响应
                return cleaned.strip()
        except Exception:
            return ""

    def _parse_json_response(self, response: str, max_retries: int = 2) -> dict:
        """尝试解析JSON响应，失败时重试"""
        import re

        for attempt in range(max_retries):
            try:
                # 首先尝试使用分隔符提取JSON
                start_marker = "===== JSON START ====="
                end_marker = "===== JSON END ====="

                start_idx = response.find(start_marker)
                end_idx = response.find(end_marker)

                if start_idx >= 0 and end_idx > start_idx:
                    # 使用分隔符提取JSON
                    json_str = response[start_idx + len(start_marker) : end_idx].strip()
                else:
                    # 备选方案：查找 { 和 }
                    start_idx = response.find("{")
                    end_idx = response.rfind("}") + 1

                    if start_idx < 0 or end_idx <= start_idx:
                        if attempt == max_retries - 1:
                            print(f"⚠️  无法找到JSON对象")
                        continue

                    json_str = response[start_idx:end_idx]

                # 尝试修复常见的JSON问题
                json_str = json_str.replace("\n", " ")  # 移除换行符
                json_str = json_str.replace("\r", "")  # 移除回车符

                # 移除可能的代码块标记
                if json_str.startswith("```"):
                    json_str = json_str[3:]
                if json_str.endswith("```"):
                    json_str = json_str[:-3]
                json_str = json_str.strip()

                # 首先尝试直接解析
                try:
                    decision = json.loads(json_str)

                    # 自动修复：如果action不是execute_tool或respond，尝试修复
                    if decision.get("action") not in ["execute_tool", "respond"]:
                        # 检查是否是工具名称被当作action
                        possible_tool = decision.get("action")
                        if "params" in decision:
                            # 这看起来像是工具调用，修复为正确格式
                            decision = {
                                "action": "execute_tool",
                                "tool": possible_tool,
                                "params": decision.get("params", {}),
                            }

                    return decision
                except json.JSONDecodeError as e:
                    # 如果失败，尝试修复常见问题
                    error_pos = e.pos if hasattr(e, "pos") else 0

                    # 修复策略1：处理content字段中的未转义引号
                    # 对于content字段中的HTML/长文本，需要特殊处理
                    json_str = re.sub(
                        r'("content"\s*:\s*")((?:[^"\\]|\\.)*?)(")',
                        lambda m: m.group(1)
                        + m.group(2).replace('"', '\\"')
                        + m.group(3),
                        json_str,
                        flags=re.DOTALL,
                    )

                    try:
                        decision = json.loads(json_str)

                        # 自动修复：如果action不是execute_tool或respond，尝试修复
                        if decision.get("action") not in ["execute_tool", "respond"]:
                            possible_tool = decision.get("action")
                            if "params" in decision:
                                decision = {
                                    "action": "execute_tool",
                                    "tool": possible_tool,
                                    "params": decision.get("params", {}),
                                }

                        return decision
                    except json.JSONDecodeError:
                        # 修复策略2：处理 HTML 内容中的引号
                        json_str = re.sub(
                            r'(?<=[a-zA-Z0-9])"(?=[a-zA-Z0-9=])', '\\"', json_str
                        )

                        try:
                            decision = json.loads(json_str)

                            # 自动修复：如果action不是execute_tool或respond，尝试修复
                            if decision.get("action") not in [
                                "execute_tool",
                                "respond",
                            ]:
                                possible_tool = decision.get("action")
                                if "params" in decision:
                                    decision = {
                                        "action": "execute_tool",
                                        "tool": possible_tool,
                                        "params": decision.get("params", {}),
                                    }

                            return decision
                        except json.JSONDecodeError:
                            # 修复策略3：尝试找到最后一个完整的JSON对象
                            # 从后往前找，确保JSON是完整的
                            for i in range(len(json_str) - 1, 0, -1):
                                if json_str[i] == "}":
                                    try:
                                        decision = json.loads(json_str[: i + 1])

                                        # 自动修复：如果action不是execute_tool或respond，尝试修复
                                        if decision.get("action") not in [
                                            "execute_tool",
                                            "respond",
                                        ]:
                                            possible_tool = decision.get("action")
                                            if "params" in decision:
                                                decision = {
                                                    "action": "execute_tool",
                                                    "tool": possible_tool,
                                                    "params": decision.get(
                                                        "params", {}
                                                    ),
                                                }

                                        return decision
                                    except json.JSONDecodeError:
                                        continue

            except json.JSONDecodeError as e:
                if attempt == max_retries - 1:
                    print(f"⚠️  JSON解析错误: {str(e)}")
                    print(f"原始响应: {response[:300]}...")
                continue
            except Exception as e:
                if attempt == max_retries - 1:
                    print(f"⚠️  错误: {e}")
                continue

        return None

    def _handle_tool_execution(self, decision: dict):
        """Execute a tool"""
        tool_name = decision.get("tool")
        params = decision.get("params", {})

        # 如果是网络搜索，检查是否超过限制
        if tool_name in {"web_search", "websearch"}:
            if self.web_search_count >= self.max_web_searches:
                result = f"⚠️ 已达到网络搜索限制({self.max_web_searches}次)，请基于已有信息给出结论"
                print(f"\n执行结果:\n{result}\n")
                import json

                tool_json = json.dumps(
                    {"tool": tool_name, "params": params}, ensure_ascii=False
                )
                history_entry = f"执行 {tool_name}:\n{tool_json}\n结果: {result}"
                self.execution_history.append(history_entry)
                # 保存到记忆文件
                self.memory_manager.append_execution_step(history_entry)
                return
            self.web_search_count += 1

        # 如果是设置定时器，传入执行器引用
        if tool_name == "set_timer":
            params["executor"] = self
            self.waiting_for_timer = True
            self.timer_triggered = False

        # 如果是发送文件，在网关模式下处理
        if tool_name == "send_file":
            file_path = params.get("path", "") or params.get("file_path", "")
            if (
                self.is_gateway_mode
                and self.bus
                and self.current_channel
                and self.current_chat_id
            ):
                result = self._send_file_to_channel(file_path)
            else:
                result = "❌ send_file 工具仅在网关模式下可用"
            print(f"\n执行结果:\n{result}\n")
            import json

            tool_json = json.dumps(
                {"tool": tool_name, "params": params}, ensure_ascii=False
            )
            history_entry = f"执行 {tool_name}:\n{tool_json}\n结果: {result}"
            self.execution_history.append(history_entry)
            # 保存到记忆文件
            self.memory_manager.append_execution_step(history_entry)
            return

        # 如果是生成PDF，处理参数映射（支持 input/input_path 和 output/output_path 两种方式）
        if tool_name == "generate_pdf":
            params["input_path"] = params.get("input_path", "") or params.get(
                "input", ""
            )
            params["output_path"] = params.get("output_path", "") or params.get(
                "output", ""
            )
            # 移除旧参数，避免混淆
            params.pop("input", None)
            params.pop("output", None)

        # Execute the tool
        tool_call = {"tool": tool_name, "params": params}
        result = self.tool_executor.execute(tool_call)

        # 显示执行结果
        print(f"\n执行结果:\n{result}\n")

        # 完整保存到记忆（包含完整 JSON 请求）
        import json

        tool_json = json.dumps(
            {"tool": tool_name, "params": params}, ensure_ascii=False
        )
        history_entry = f"执行 {tool_name}:\n{tool_json}\n结果: {result}"

        self.execution_history.append(history_entry)

        # 同步保存到记忆文件（确保下一步能读到）
        self.memory_manager.append_execution_step(history_entry)

        # 如果设置了定时器，等待其触发
        if tool_name == "set_timer" and self.waiting_for_timer:
            print("⏳ 等待定时器触发...\n")
            import time

            while self.waiting_for_timer and not self.timer_triggered:
                time.sleep(0.5)
            Toast.success("定时器已触发，继续执行任务")

    def _ask_for_approval(self) -> str:
        """Ask user for approval to execute command with arrow keys"""
        options = ["yes", "all", "no"]
        selected = 0  # 默认选中第一个选项
        first_display = True

        while True:
            try:
                # 显示选项
                display = "[yes/all/no] 允许执行? "
                for i, opt in enumerate(options):
                    if i == selected:
                        display += f"[{opt}] "  # 当前选中的选项用方括号
                    else:
                        display += f" {opt}  "

                if first_display:
                    print(display, end="", flush=True)
                    first_display = False
                else:
                    # 使用 ANSI 转义序列清除当前行并重新打印
                    sys.stdout.write("\r\033[K" + display)
                    sys.stdout.flush()

                # 获取用户输入
                import sys
                import platform

                # Windows 和 Unix 的不同处理方式
                if platform.system() == "Windows" or not sys.stdin.isatty():
                    # 非交互输入不切换终端 raw 模式。
                    ch = input("yes/all/no: ").strip().lower()
                    if ch in {"y", "yes"}:
                        return "yes"
                    elif ch in {"a", "all"}:
                        return "all"
                    elif ch in {"n", "no", "q", "quit"}:
                        return "no"
                    else:
                        return options[selected]
                else:
                    # Unix/Linux/macOS 上使用 termios 处理箭头键
                    import tty
                    import termios

                    # 保存终端设置
                    fd = sys.stdin.fileno()
                    old_settings = termios.tcgetattr(fd)

                    try:
                        tty.setraw(fd)
                        ch = sys.stdin.read(1)

                        if ch == "\x1b":  # ESC序列
                            next1 = sys.stdin.read(1)
                            if next1 == "[":
                                next2 = sys.stdin.read(1)
                                if next2 == "C":  # 右箭头
                                    selected = (selected + 1) % len(options)
                                elif next2 == "D":  # 左箭头
                                    selected = (selected - 1) % len(options)
                                elif next2 == "A":  # 上箭头
                                    selected = (selected - 1) % len(options)
                                elif next2 == "B":  # 下箭头
                                    selected = (selected + 1) % len(options)
                        elif ch == "\r" or ch == "\n":  # 回车
                            print()  # 换行
                            return options[selected]
                        elif ch.lower() == "y":  # 快捷键 y
                            print()
                            return "yes"
                        elif ch.lower() == "a":  # 快捷键 a
                            print()
                            return "all"
                        elif ch.lower() == "n":  # 快捷键 n
                            print()
                            return "no"
                        elif ch == "q" or ch == "\x03":  # q 或 Ctrl+C
                            print()
                            return "no"

                    finally:
                        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

            except KeyboardInterrupt:
                Toast.warning("已取消")
                return "no"
            except Exception as e:
                print(f"\n错误: {e}")
                return "no"

    def _is_tool_requires_approval(self, tool_name: str) -> bool:
        """Check if a tool requires user approval before execution"""
        dangerous_tools = {
            "bash",
            "shell",
            "file_write",  # 写入文件
            "write",  # 写入文件（OpenCode风格）
            "edit",  # 编辑文件
            "file_delete",  # 删除文件
            "dir_change",  # 切换目录（可能影响后续操作）
            "dir_create",
            "create_file",
            "copy_file",
            "move_file",
            "send_file",
            "generate_pdf",
            "project_preview",
        }
        return tool_name in dangerous_tools

    def _get_action_description(self, tool_name: str, params: dict) -> str:
        """Get natural description of the action"""
        descriptions = {
            "file_list": f"列出 {params.get('path', '当前目录')} 中的文件",
            "file_read": f"读取文件 {params.get('path')}",
            "file_write": f"写入文件 {params.get('path')}",
            "file_delete": f"删除文件 {params.get('path')}",
            "dir_create": f"创建目录 {params.get('path')}",
            "dir_change": f"切换到目录 {params.get('path')}",
            "shell": f"执行命令: {params.get('command', '')[:50]}",
            "read_pdf": f"读取PDF文件 {params.get('path')}",
            "read_markdown": f"读取Markdown文件 {params.get('path')}",
            "read_json": f"读取JSON文件 {params.get('path')}",
            "search_files": f"搜索文件 {params.get('pattern')}",
            "get_file_info": f"获取文件信息 {params.get('path')}",
            "copy_file": f"复制文件 {params.get('source')} 到 {params.get('destination')}",
            "move_file": f"移动文件 {params.get('source')} 到 {params.get('destination')}",
            "create_file": f"创建文件 {params.get('path')}",
            "send_file": f"发送文件到飞书 {params.get('path')}",
            "load_skill": f"加载 skill: {params.get('skill_name')}",
        }
        return descriptions.get(tool_name, f"执行 {tool_name}")

    def _get_result_description(self, tool_name: str, result: str) -> str:
        """Get natural description of the result"""
        # Truncate long results
        if len(result) > 500:
            result_preview = result[:500] + "..."
        else:
            result_preview = result

        result_stripped = result.lstrip()
        is_error = (
            result_stripped.startswith("Error:")
            or result_stripped.startswith("错误:")
            or result_stripped.startswith("Traceback")
            or "\nTraceback (most recent call last):" in result
            or result_stripped.startswith("✗ Failed")
        )

        if is_error:
            return f"出现错误: {result_preview}"
        elif (
            "Success" in result
            or "成功" in result
            or "created" in result
            or "已创建" in result
        ):
            return f"成功完成。{result_preview}"
        else:
            return f"得到结果: {result_preview}"

    def _format_tool_result(self, tool_name: str, result: str) -> str:
        """Format tool result with collapsible style for long output"""
        MAX_LINES = 20

        lines = result.split("\n")
        has_long_output = len(lines) > MAX_LINES or len(result) > 1000

        # Check for error state
        result_stripped = result.lstrip()
        is_error = (
            result_stripped.startswith("Error:")
            or result_stripped.startswith("错误:")
            or result_stripped.startswith("Traceback")
            or "\nTraceback (most recent call last):" in result
            or result_stripped.startswith("✗ Failed")
        )

        if is_error:
            # Error output - show full content with red styling
            error_header = f"{Colors.RED}{Symbols.CROSS} 执行失败{Colors.RESET}\n"
            return f"\n{error_header}{Box.draw('错误详情', result[:500] if len(result) > 500 else result, width=70)}\n"

        if not has_long_output:
            # Short output - show directly with green checkmark
            return f"\n{Colors.GREEN}{Symbols.CHECK} 结果:{Colors.RESET}\n{result}\n"

        # Long output - use collapsible box style
        preview = "\n".join(lines[:MAX_LINES])
        if len(result) > 1000:
            preview = preview[:1000] + "..."

        box_content = f"""
{Symbols.UP_RIGHT} ─ {Colors.BOLD}显示前 {MAX_LINES} 行 ({len(lines) - MAX_LINES} more lines){Colors.RESET}
{preview}
{Colors.DIM}{Symbols.VERTICAL} 完整输出 ({len(lines)} 行, {len(result)} 字符) 已保存到执行历史{Colors.RESET}
"""
        return f"\n{Box.draw(f'工具结果 {tool_name}', box_content, width=70)}\n"

    def _build_context(self) -> str:
        """Build context from memory files and accumulated compression"""

        context_parts = []

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

    def _cleanup_large_results(self) -> None:
        """Clean up large results from web_search and read_url to reduce context size"""
        # 不再截断任何结果，保留完整内容
        pass

    def _cleanup_temp_files(self) -> None:
        """Automatically clean up temporary files after task completion"""
        import shutil

        workspace_path = Path(__file__).parent / "workspace"
        temp_path = workspace_path / "temp"

        try:
            if temp_path.exists():
                # 列出要删除的文件
                files_to_delete = list(temp_path.glob("*"))

                if files_to_delete:
                    print(f"\n🧹 清理临时文件...")
                    for file in files_to_delete:
                        try:
                            if file.is_dir():
                                shutil.rmtree(file)
                                print(f"  ✓ 删除目录: {file.name}")
                            else:
                                file.unlink()
                                print(f"  ✓ 删除文件: {file.name}")
                        except Exception as e:
                            print(f"  ⚠️  无法删除 {file.name}: {e}")
                    print(f"✅ 临时文件清理完成\n")
        except Exception as e:
            print(f"⚠️  清理临时文件出错: {e}\n")

    def _clear_history(self) -> None:
        """Clear conversation history and execution history"""
        deleted_checkpoint = False
        if self._active_graph_runtime:
            runtime = self._active_graph_runtime
            runtime.get("cancel_event", threading.Event()).set()
            try:
                self.langgraph_runner.delete_thread(runtime["thread_id"])
                deleted_checkpoint = True
            except Exception:
                pass
        for thread_id in list(self._known_graph_threads):
            try:
                self.langgraph_runner.delete_thread(thread_id)
                deleted_checkpoint = True
            except Exception:
                pass
            self._known_graph_threads.discard(thread_id)
        for pending in list(self._gateway_pending.values()):
            try:
                pending["runtime"].get("cancel_event", threading.Event()).set()
                self.langgraph_runner.delete_thread(pending["thread_id"])
                deleted_checkpoint = True
            except Exception:
                pass
        self._gateway_pending.clear()
        clear_plans = getattr(
            getattr(self, "tool_executor", None),
            "clear_plan_snapshots",
            None,
        )
        if callable(clear_plans):
            try:
                clear_plans()
            except Exception:
                pass
        if deleted_checkpoint:
            try:
                self.langgraph_runner.vacuum_checkpoint_store()
            except Exception:
                pass
        # Clear AI engine history
        self.ai_engine.clear_history()

        # Clear execution history
        self.execution_history = []

        # Reset step counter
        self.step_count = 0

        # Reset web search counter
        self.web_search_count = 0

        # Reset command approval state
        self.allow_all_commands = False

        # 清空压缩摘要链
        self.accumulated_compression = ""
        self.task_compression_summary = ""

        # 清除记忆文件
        self.memory_manager.clear_all()

        Toast.success("历史会话已清除，记忆文件已删除")

    def _auto_compress_if_needed(self, silent: bool = True) -> None:
        """检查是否需要自动压缩（silent=True 时静默执行，不打印信息）"""
        all_history = self.memory_manager.load_execution_history()
        if all_history:
            history_text = "\n".join(all_history)
            current_tokens = self._estimate_tokens(history_text)
            if current_tokens > self.compress_at:
                if not silent:
                    print(f"📊 近期记忆已达 {current_tokens} tokens，准备自动压缩")
                start_spinner("正在自动整理近期记忆", show_elapsed=True)
                try:
                    self._compress_current_task_manual()
                finally:
                    stop_spinner()

    def _start_auto_compress_monitor(self) -> None:
        """Compatibility no-op; LangGraph compacts synchronously at step boundaries."""
        self._monitor_running = False

    def _stop_auto_compress_monitor(self) -> None:
        """停止后台自动压缩监测线程"""
        self._monitor_running = False

    def _send_file_to_channel(self, file_path: str) -> str:
        """Send file to channel via message bus."""
        if not self.bus or not self.current_channel or not self.current_chat_id:
            return "❌ 无法发送文件：消息总线未初始化"

        try:
            import os
            from pathlib import Path

            # Expand path
            expanded_path = os.path.expanduser(file_path)

            if not expanded_path.startswith("/"):
                expanded_path = os.path.expanduser("~") + "/" + expanded_path

            if not os.path.isfile(expanded_path):
                # 提供更详细的错误信息
                error_msg = f"❌ 文件不存在\n"
                error_msg += f"   原始路径: {file_path}\n"
                error_msg += f"   展开路径: {expanded_path}\n"
                error_msg += f"   路径存在: {os.path.exists(expanded_path)}\n"

                # 检查父目录
                parent_dir = os.path.dirname(expanded_path)
                if os.path.exists(parent_dir):
                    error_msg += f"   父目录存在: ✓\n"
                    error_msg += f"   父目录内容: {os.listdir(parent_dir)[:5]}"
                else:
                    error_msg += f"   父目录存在: ✗ ({parent_dir})"

                return error_msg

            file_size = os.path.getsize(expanded_path)
            file_name = os.path.basename(expanded_path)

            print(f"✅ 文件找到 - 名称: {file_name}, 大小: {file_size} bytes")

            # Create OutboundMessage with file path
            # The Feishu channel will detect it's a file and handle it
            msg = OutboundMessage(
                channel=self.current_channel,
                chat_id=self.current_chat_id,
                content=expanded_path,  # Pass the full file path
            )

            # Send asynchronously
            asyncio.ensure_future(self.bus.publish_outbound(msg))

            return f"✅ 文件已发送: {file_name} ({file_size} bytes)"
        except Exception as e:
            import traceback

            error_trace = traceback.format_exc()
            return f"❌ 发送文件出错:\n{error_trace}"

    async def _send_to_channel(self, content: str) -> None:
        """Send response to channel via message bus."""
        # 如果正在压缩，不发送消息
        if self.is_compressing:
            return

        if not self.bus or not self.current_channel or not self.current_chat_id:
            return

        try:
            msg = OutboundMessage(
                channel=self.current_channel,
                chat_id=self.current_chat_id,
                content=content,
            )
            await self.bus.publish_outbound(msg)
        except Exception as e:
            Toast.error(f"Error sending message to channel: {e}")


def get_user_input(prompt: str = "你: ") -> str:
    """Get user input with proper UTF-8 handling for macOS"""
    try:
        # 对于macOS，使用更简单的方法
        import sys
        import time

        # 确保之前的输出被清除
        time.sleep(0.05)
        sys.stdout.write('\r' + ' ' * 50 + '\r')
        sys.stdout.flush()
        time.sleep(0.05)

        sys.stdout.write(f"{Colors.YELLOW}{Symbols.USER} {Colors.BOLD}你: {Colors.RESET}")  # 黄色提示符
        sys.stdout.flush()

        # 直接读取，不使用readline
        line = sys.stdin.readline()
        if line:
            return line.rstrip("\n\r")
        return ""
    except KeyboardInterrupt:
        return "exit"
    except EOFError:
        return "exit"


def _print_terminal_header() -> None:
    """Print a compact welcome header that adapts to terminal width."""
    width = shutil.get_terminal_size(fallback=(100, 24)).columns
    if width >= 92:
        ascii_art = """
    ██████╗ ███████╗       █████╗  ██████╗  ███████╗███╗   ██╗████████╗
    ██╔═══██╗██╔════╝      ██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝
    ██║   ██║███████╗█████╗███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║
    ██║   ██║╚════██║╚════╝██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║
    ╚██████╔╝███████║      ██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║
    ╚═════╝ ╚══════╝      ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝
"""
        print(Colors.CYAN + ascii_art.rstrip() + Colors.RESET)
    else:
        print(f"\n{Colors.CYAN}{Colors.BOLD}麒麟 OS-Agent{Colors.RESET}")

    print(f"{Colors.BOLD}系统自动化与知识记忆工作台{Colors.RESET}")
    print(
        f"{Colors.DIM}/clear 清空会话  /compact 压缩记忆  "
        f"Ctrl+C 中断任务  exit 退出{Colors.RESET}\n"
    )


async def gateway_mode():
    """Run 麒麟OS-Agent in gateway mode with multiple channels."""
    # Fix event loop issue for lark-oapi WebSocket client
    try:
        import nest_asyncio

        nest_asyncio.apply()
    except ImportError:
        Toast.warning("nest_asyncio not installed, some asyncio warnings may appear")
        pass

    # Suppress asyncio warnings
    import warnings

    warnings.filterwarnings("ignore", category=RuntimeWarning)
    warnings.filterwarnings("ignore", message=".*cannot enter context.*")

    print("\n🚀 启动麒麟OS-Agent网关模式...\n")

    # Load configuration
    config = load_config()

    # Check if any channels are enabled
    if not config.channels.feishu.enabled:
        Toast.error("没有启用任何通道。请在配置文件中启用至少一个通道。")
        print(f"📝 配置文件位置: ~/.os-agent/config.json")
        return

    # Create message bus
    bus = MessageBus()

    # Create channel manager
    channel_manager = ChannelManager(config, bus)

    # Create executor with bus
    executor = NaturalTaskExecutor(bus=bus)

    # 启动后台自动压缩监测线程
    executor._start_auto_compress_monitor()

    # Save event loop for background compression notifications
    executor.event_loop = asyncio.get_running_loop()

    # Start channels and message processing
    async def process_messages():
        """Process inbound messages from channels."""
        while True:
            try:
                # Wait for inbound message with timeout
                msg = await asyncio.wait_for(bus.consume_inbound(), timeout=1.0)

                print(f"\n{'=' * 60}")
                print(f"📨 【收到飞书消息】")
                print(f"发送者: {msg.sender_id}")
                print(f"内容: {msg.content}")
                print(f"{'=' * 60}\n")

                session_key = msg.session_key
                executor.current_sender_id = msg.sender_id
                executor.current_chat_id = msg.chat_id
                executor.current_channel = msg.channel

                command = msg.content.lower().strip()
                if command == "/stop":
                    pending = executor._gateway_pending.pop(session_key, None)
                    active = executor._gateway_active.get(session_key)
                    if not pending and not active:
                        queued = executor._gateway_tasks.get(session_key)
                        if queued and not queued.done():
                            queued.cancel()
                    target = pending or (
                        {
                            "runtime": active,
                            "thread_id": active.get("thread_id", ""),
                        }
                        if active
                        else None
                    )
                    if target:
                        target["runtime"].get(
                            "cancel_event", threading.Event()
                        ).set()
                        executor.langgraph_runner.cancel(target["thread_id"])
                        try:
                            executor.langgraph_runner.delete_thread(target["thread_id"])
                        except Exception:
                            pass
                        if pending:
                            target["runtime"]["data_integrator"].end_task("已停止")
                    await bus.publish_outbound(
                        OutboundMessage(
                            channel=msg.channel,
                            chat_id=msg.chat_id,
                            content="⏹️ 当前会话任务已停止",
                        )
                    )
                    continue

                if command == "/clear":
                    pending = executor._gateway_pending.pop(session_key, None)
                    active = executor._gateway_active.get(session_key)
                    if not pending and not active:
                        queued = executor._gateway_tasks.get(session_key)
                        if queued and not queued.done():
                            queued.cancel()
                    target = pending or (
                        {
                            "runtime": active,
                            "thread_id": active.get("thread_id", ""),
                        }
                        if active
                        else None
                    )
                    if target:
                        target["runtime"].get(
                            "cancel_event", threading.Event()
                        ).set()
                        try:
                            executor.langgraph_runner.delete_thread(target["thread_id"])
                        except Exception:
                            pass
                    executor._memory_for_session(session_key).clear_all()
                    await bus.publish_outbound(
                        OutboundMessage(
                            channel=msg.channel,
                            chat_id=msg.chat_id,
                            content="✅ 当前会话历史已清除",
                        )
                    )
                    continue

                if session_key in executor._gateway_pending:
                    result = await asyncio.to_thread(
                        executor.resume_gateway_task, session_key, msg.content
                    )
                    if result and result.status == "waiting" and result.error:
                        await bus.publish_outbound(
                            OutboundMessage(
                                channel=msg.channel,
                                chat_id=msg.chat_id,
                                content=f"⚠️ {result.error}",
                            )
                        )
                    continue

                queued_task = executor._gateway_tasks.get(session_key)
                if session_key in executor._gateway_active or (
                    queued_task and not queued_task.done()
                ):
                    await bus.publish_outbound(
                        OutboundMessage(
                            channel=msg.channel,
                            chat_id=msg.chat_id,
                            content=(
                                "⏳ 当前会话已有任务在执行。"
                                "请等待完成，或发送 /stop 后再提交新任务。"
                            ),
                        )
                    )
                    continue

                # Check for /compact command
                if command == "/compact":
                    session_memory = executor._memory_for_session(session_key)
                    history = session_memory.load_execution_history()
                    token_count = executor._estimate_tokens("\n".join(history)) if history else 0
                    await bus.publish_outbound(
                        OutboundMessage(
                            channel=msg.channel,
                            chat_id=msg.chat_id,
                            content=(
                                f"⏳ 正在整理当前会话记忆（约 {token_count} tokens）..."
                                if history
                                else "⚠️ 当前会话没有可压缩的执行历史"
                            ),
                        )
                    )
                    if history:
                        compressed = await asyncio.to_thread(
                            executor._compress_memory_for_gateway, session_memory
                        )
                        await bus.publish_outbound(
                            OutboundMessage(
                                channel=msg.channel,
                                chat_id=msg.chat_id,
                                content=compressed,
                            )
                        )
                    continue

                print(f"🤖 【AI 开始处理】\n")
                thread_id = f"{session_key}:{uuid.uuid4().hex}"
                task = asyncio.create_task(
                    asyncio.to_thread(
                        executor.execute_task,
                        msg.content,
                        thread_id=thread_id,
                        session_key=session_key,
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        sender_id=msg.sender_id,
                        interactive=False,
                    )
                )
                executor._gateway_tasks[session_key] = task

                def task_finished(_task, key=session_key):
                    executor._gateway_tasks.pop(key, None)

                task.add_done_callback(task_finished)

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                Toast.error(f"处理消息错误: {e}")

    # Run channels and message processor concurrently
    try:
        await asyncio.gather(
            channel_manager.start_all(), process_messages(), return_exceptions=True
        )
    except KeyboardInterrupt:
        print("\n\n🛑 正在关闭...\n")
        await channel_manager.stop_all()


def main():
    """Main chat loop"""
    # 尝试加载配置管理器
    try:
        from agent.core.config_manager import ConfigManager

        config_manager = ConfigManager()
        configs = config_manager.list_configs()

        # 如果有保存的配置，显示选择菜单
        if configs.get("available"):
            print("\n📋 可用的 API 配置:")
            for i, config_name in enumerate(configs["available"], 1):
                marker = "✓ " if config_name == configs["active"] else "  "
                print(f"  {marker}{i}. {config_name}")

            print(f"  {len(configs['available']) + 1}. 使用环境变量配置")
            print(f"  {len(configs['available']) + 2}. 跳过选择")

            try:
                choice = input("\n请选择配置 (默认: 跳过): ").strip()
                if choice:
                    choice_num = int(choice)
                    if 1 <= choice_num <= len(configs["available"]):
                        selected_config = configs["available"][choice_num - 1]
                        config_manager.set_active_config(selected_config)
                        config_manager.export_to_env()
                        print(f"✅ 已选择配置: {selected_config}\n")
            except (ValueError, IndexError):
                pass
    except ImportError:
        pass  # 配置管理器不可用

    try:
        executor = NaturalTaskExecutor()
    except ValueError as exc:
        Toast.error(str(exc))
        print("请复制 .env.example 为 .env，并配置 API_KEY 后重试。")
        return 1

    _print_terminal_header()
    executor._start_auto_compress_monitor()

    while True:
        try:
            user_input = get_user_input()

            if not user_input:
                continue

            if user_input.lower() in ["exit", "quit"]:
                print("\n👋 再见！\n")
                break

            # Handle /clear command
            if user_input.lower().strip() == "/clear":
                executor._clear_history()
                continue

            # Handle /compact command
            if user_input.lower().strip() == "/compact":
                # 显示当前记忆大小（从文件读取完整历史）
                all_history = executor.memory_manager.load_execution_history()
                if all_history:
                    history_text = "\n".join(all_history)
                    current_tokens = executor._estimate_tokens(history_text)
                    print(f"📊 近期记忆: {current_tokens} tokens，正在压缩...\n")
                else:
                    print(f"⚠️  没有执行历史可以压缩\n")
                if all_history:
                    start_spinner("正在整理近期记忆并生成结构化摘要", show_elapsed=True)
                    try:
                        executor._compress_current_task_manual()
                    finally:
                        stop_spinner()
                # 压缩完成后显示用户提示
                print("💡 你可以继续提问新的任务\n")
                continue

            # 清理上一个任务的大型网页结果
            executor._cleanup_large_results()
            executor.ai_engine.truncate_web_results(
                max_length=300
            )  # 截断AI引擎对话历史中的网页结果

            # 清空AI引擎的对话历史，为新任务开始做准备
            executor.ai_engine.clear_history()

            # Reset for new task
            # 不清空 execution_history，让它积累所有任务的执行历史
            # 直到用户输入 /compact 时才压缩
            executor.step_count = 0  # 重置步数计数器（每个新任务重新开始计数）
            executor.web_search_count = 0  # 重置搜索计数
            executor.allow_all_commands = False  # 重置命令允许状态

            print()
            executor.execute_task(user_input)

        except KeyboardInterrupt:
            executor.should_stop = True
            executor._stop_event.set()
            if executor._active_cancel_event is not None:
                executor._active_cancel_event.set()
            if executor._active_graph_runtime:
                try:
                    executor.langgraph_runner.cancel(
                        executor._active_graph_runtime["thread_id"]
                    )
                except Exception:
                    pass
            Toast.warning("任务已中断")
            print("💡 你可以继续提问新的任务\n")
            stop_spinner()  # 停止 spinner 动画
            # 不退出，继续循环
            continue
        except Exception as e:
            stop_spinner()
            Toast.error(f"错误: {str(e)}")

    return 0


if __name__ == "__main__":
    import sys

    # Check for gateway mode or desktop mode
    if len(sys.argv) > 1:
        if sys.argv[1] == "gateway":
            asyncio.run(gateway_mode())
        elif sys.argv[1] == "desktop":
            from agent.ui.desktop import main as desktop_main

            desktop_main.main()
        elif sys.argv[1] in {"-h", "--help", "help"}:
            print("Usage: python chat.py [desktop|gateway]")
        else:
            print(f"Unknown command: {sys.argv[1]}")
            print("Usage: python chat.py [gateway|desktop]")
            raise SystemExit(2)
    else:
        raise SystemExit(main())
