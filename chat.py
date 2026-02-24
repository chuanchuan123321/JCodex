#!/usr/bin/env python3
"""Minibot - 轻量级 AI 自动化工具"""

import sys

sys.path.insert(0, "/Users/a1-6/Desktop/AI智能体")

# 修复macOS终端UTF-8输入问题
import os
import locale

os.environ["PYTHONIOENCODING"] = "utf-8"
locale.setlocale(locale.LC_ALL, "")

# 加载环境变量
from dotenv import load_dotenv

load_dotenv("/Users/a1-6/Desktop/AI智能体/.env")

from agent.core.ai_engine import AIEngine
from agent.core.extended_tool_executor import ExtendedToolExecutor
from agent.core.skills import SkillsLoader
from agent.core.memory_manager import MemoryManager
from agent.bus.queue import MessageBus
from agent.bus.events import OutboundMessage
from agent.channels.manager import ChannelManager
from agent.config.loader import load_config
import json
import asyncio
from pathlib import Path

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
        self.should_stop = False  # 是否应该停止当前任务
        self.web_search_count = 0  # 网络搜索计数
        self.max_web_searches = MAX_WEB_SEARCHES  # 从环境变量读取
        self.max_steps = MAX_STEPS  # 从环境变量读取
        self.task_compression_summary = ""  # 当前任务的压缩摘要
        # 从记忆文件加载累积的压缩摘要
        self.accumulated_compression = (
            self.memory_manager.load_accumulated_compression()
        )
        self.current_task_start_step = 0  # 当前任务的起始步骤
        self.event_loop = None  # 事件循环（仅在网关模式下设置）

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
            # 压缩前估算token数
            if self.execution_history:
                history_text = "\n".join(self.execution_history)
                tokens_before = self._estimate_tokens(history_text)
            else:
                tokens_before = 0

            self._compress_current_task_manual()
            print(f"✅ 任务历史已自动压缩 (清除了 {tokens_before} tokens)")

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
            print(f"⚠️ 自动压缩失败: {e}")

    def _compress_current_task_async_wrapper(self):
        """异步包装器，在子线程中执行压缩"""
        try:
            self._compress_current_task_manual()
        except Exception as e:
            print(f"压缩失败: {e}")
            # 在网关模式下发送错误消息
            if (
                self.is_gateway_mode
                and self.bus
                and self.current_channel
                and self.current_chat_id
            ):
                asyncio.ensure_future(self._send_to_channel(f"⚠️ 压缩失败: {str(e)}"))

    def execute_task(self, user_request: str):
        """Execute task dynamically with natural flow"""
        # Check for clear command
        if user_request.lower().strip() == "/clear":
            self._clear_history()
            return

        # Check for compact command (压缩历史记录)
        if user_request.lower().strip() == "/compact":
            self._compress_current_task_manual()
            return

        # 重置搜索计数（每个新任务开始时）
        self.web_search_count = 0

        # 记录用户请求到记忆文件
        self.memory_manager.append_execution_step(f"【用户请求】{user_request}")

        # Build context from execution history
        context = self._build_context()

        # First step: Decide what to do
        self.step_count = 1
        self._execute_step(user_request, context)

    def _execute_step(self, user_request: str, context: str):
        """Execute a single step with natural description"""
        # 检查是否应该停止任务
        if self.should_stop:
            print(f"\n⏹️  任务已停止。\n")
            self.should_stop = False
            return

        if self.step_count > self.max_steps:
            print(f"\n⚠️  已达到最大步数限制({self.max_steps})，任务停止。\n")
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
        split_marker = "【用户任务】"
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

        # 替换用户消息中的变量
        user_message = user_message_template
        user_message = user_message.replace("{user_request}", user_request)
        user_message = user_message.replace("{context}", context)

        # 调用 API 时分离传递系统提示词和用户消息
        response = self.ai_engine.call_api(user_message, system_prompt=system_prompt)

        # 清空AI引擎的对话历史（已保存到执行历史文件）
        self.ai_engine.clear_history()

        # 显示AI的回答
        print(response)

        # 提取自然语言部分
        natural_language = self._extract_natural_language(response)

        # 记录AI的自然语言响应到记忆文件
        if natural_language:
            self.memory_manager.append_execution_step(f"【AI响应】{natural_language}")

        # 发送到飞书
        if natural_language and self.is_gateway_mode:
            # 使用 ensure_future 而不是 create_task 来避免 context 冲突
            asyncio.ensure_future(self._send_to_channel(f"🤖 {natural_language}"))

        # 尝试解析JSON，如果失败则重试
        decision = self._parse_json_response(response, max_retries=2)

        if decision is None:
            # 如果多次重试都失败，继续下一步而不是停止
            print("\n⚠️ 无法解析响应，继续下一步...\n")
            self.step_count += 1
            context = self._build_context()
            self._execute_step(user_request, context)
            return

        action = decision.get("action")

        # Handle different actions
        if action == "execute_tool":
            tool_name = decision.get("tool", "unknown")

            # 检查工具是否需要确认
            requires_approval = self._is_tool_requires_approval(tool_name)

            # 如果不是允许所有命令，且工具需要确认，则询问用户
            if not self.allow_all_commands and requires_approval:
                if self.is_gateway_mode:
                    # 网关模式：发送确认请求到飞书，并等待用户回复
                    params = decision.get("params", {})
                    action_desc = self._get_action_description(tool_name, params)

                    approval_msg = f"""
⚠️ 【需要确认】

AI 想要执行以下操作：
{action_desc}

请在飞书中回复：
- "yes" 或 "y" - 执行此命令
- "all" 或 "a" - 允许本任务所有命令
- "no" 或 "n" - 取消此命令
"""
                    # 发送到飞书
                    if self.bus and self.current_channel and self.current_chat_id:
                        msg = OutboundMessage(
                            channel=self.current_channel,
                            chat_id=self.current_chat_id,
                            content=approval_msg,
                        )
                        asyncio.ensure_future(self.bus.publish_outbound(msg))

                    # 保存待执行的决策和上下文
                    self.pending_decision = decision
                    self.pending_user_request = user_request
                    self.pending_context = context

                    # 设置等待标志，暂停执行
                    print(f"⏳ 等待用户在飞书中确认...\n")
                    self.waiting_for_approval = True
                    self.approval_response = None
                    return
                else:
                    # CLI 模式：使用箭头键选择
                    approval = self._ask_for_approval()

                    if approval == "no":
                        print(f"❌ 已取消此命令\n")
                        self.step_count += 1
                        context = self._build_context()
                        self._execute_step(user_request, context)
                        return
                    elif approval == "all":
                        self.allow_all_commands = True
                        print(f"✅ 已允许本任务所有命令\n")

            self._handle_tool_execution(decision)
            # Continue to next step
            self.step_count += 1
            context = self._build_context()
            self._execute_step(user_request, context)

        elif action == "respond":
            response_text = decision.get("response", "")
            print(f"\n{response_text}\n")

            # 记录最终回应到历史
            history_entry = f"最终回应: {response_text}"
            self.execution_history.append(history_entry)

            # 同步保存到记忆文件（确保数据持久化）
            self.memory_manager.append_execution_step(history_entry)

            # 清理大型搜索结果以节省上下文
            self._cleanup_large_results()

            # 自动清理临时文件
            self._cleanup_temp_files()

            # 如果在网关模式下，发送回复到消息总线
            if self.bus and self.current_channel and self.current_chat_id:
                asyncio.ensure_future(self._send_to_channel(response_text))

            # 自动压缩任务记忆
            if self.execution_history:
                # 从文件中读取完整的近期记忆（不是内存中的片段）
                all_history = self.memory_manager.load_execution_history()
                if all_history:
                    history_text = "\n".join(all_history)
                    current_tokens = self._estimate_tokens(history_text)
                else:
                    # 如果文件为空，使用内存中的历史
                    history_text = "\n".join(self.execution_history)
                    current_tokens = self._estimate_tokens(history_text)

                # 只有当超过阈值时才压缩
                if current_tokens > COMPRESS_AT:
                    # 发送压缩提示
                    compact_msg = (
                        f"⏳ 近期记忆已达 {current_tokens} tokens，正在压缩任务历史..."
                    )
                    print(f"{compact_msg}")
                    if self.bus and self.current_channel and self.current_chat_id:
                        asyncio.ensure_future(self._send_to_channel(compact_msg))

                    # 在后台线程中执行压缩（不等待）
                    import threading

                    # 获取事件循环（可能来自网关模式保存的 executor.event_loop）
                    event_loop = getattr(self, "event_loop", None)
                    if not event_loop:
                        try:
                            event_loop = asyncio.get_running_loop()
                        except RuntimeError:
                            event_loop = None

                    compression_thread = threading.Thread(
                        target=self._compress_and_notify,
                        args=(event_loop,),
                        daemon=True,
                    )
                    compression_thread.start()
                else:
                    # 近期记忆未超过限制，显示当前token数
                    print(f"📊 近期记忆: {current_tokens}/{COMPRESS_AT} tokens")

        else:
            print(f"\n⚠️  未知操作: {action}，继续下一步...\n")
            self.step_count += 1
            context = self._build_context()
            self._execute_step(user_request, context)

    async def _execute_step_async(self, user_request: str, context: str):
        """Async wrapper for _execute_step to avoid nested asyncio issues"""
        self._execute_step(user_request, context)

    def _compress_current_task_manual(self) -> None:
        """Manually compress the current execution history into a summary"""

        # 从记忆文件加载执行历史
        execution_history = self.memory_manager.load_execution_history()

        if not execution_history:
            print("⚠️  没有执行历史可以压缩\n")
            return

        # 先调用AI生成简短摘要，确保成功后再保存
        history_text = "\n".join(execution_history)
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
            task_summary = self.ai_engine.call_api(summary_prompt)

            # 清空AI引擎的对话历史（已保存到执行历史文件）
            self.ai_engine.clear_history()

            # 检查AI是否成功返回摘要（不是错误信息）
            if not task_summary or task_summary.strip() == "":
                print("⚠️ AI未能生成摘要，压缩取消\n")
                return
            if task_summary.startswith("API Error:") or "Error:" in task_summary:
                print(f"⚠️ AI调用错误，压缩取消\n")
                return

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

        # 彻底清空 AIEngine 的对话历史以减少上下文
        # 压缩摘要已经保存到文件，不需要再保留在内存中
        self.ai_engine.clear_history()

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
        try:
            # 查找 JSON 标记
            start_marker = "===== JSON START ====="
            start_idx = response.find(start_marker)

            if start_idx > 0:
                # 提取 JSON 标记之前的内容
                natural_part = response[:start_idx].strip()
                # 移除 "接下来我要: " 前缀
                if natural_part.startswith("接下来我要:"):
                    natural_part = natural_part[len("接下来我要:") :].strip()
                return natural_part
            else:
                # 如果没有 JSON 标记，返回整个响应
                return response.strip()
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
        if tool_name == "web_search":
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
            print("✅ 定时器已触发，继续执行任务\n")

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
                if platform.system() == "Windows":
                    # Windows 上使用简单的输入方式
                    ch = input().strip()
                    if ch.lower() == "y":
                        return "yes"
                    elif ch.lower() == "a":
                        return "all"
                    elif ch.lower() == "n":
                        return "no"
                    elif ch.lower() == "q":
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
                print("\n⚠️  已取消\n")
                return "no"
            except Exception as e:
                print(f"\n错误: {e}")
                return "no"

    def _is_tool_requires_approval(self, tool_name: str) -> bool:
        """Check if a tool requires user approval before execution"""
        # 只读和安全操作不需要确认
        safe_tools = {
            "load_skill",  # 加载skill内容
            "read_pdf",  # 读取PDF
            "read_markdown",  # 读取Markdown
            "read_json",  # 读取JSON
            "file_read",  # 读取文件
            "file_list",  # 列出文件
            "search_files",  # 搜索文件
            "get_file_info",  # 获取文件信息
            "web_search",  # 网络搜索
            "read_url",  # 读取URL
            "set_timer",  # 设置定时器
        }
        return tool_name not in safe_tools

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

        if "Error" in result or "错误" in result:
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

        print("✅ 历史会话已清除，记忆文件已删除\n")

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
            print(f"❌ Error sending message to channel: {e}")


def get_user_input(prompt: str = "你: ") -> str:
    """Get user input with proper UTF-8 handling for macOS"""
    try:
        # 对于macOS，使用更简单的方法
        import sys

        sys.stdout.write(prompt)
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


async def gateway_mode():
    """Run Minibot in gateway mode with multiple channels."""
    # Fix event loop issue for lark-oapi WebSocket client
    try:
        import nest_asyncio

        nest_asyncio.apply()
    except ImportError:
        print("⚠️  nest_asyncio not installed, some asyncio warnings may appear")
        pass

    # Suppress asyncio warnings
    import warnings

    warnings.filterwarnings("ignore", category=RuntimeWarning)
    warnings.filterwarnings("ignore", message=".*cannot enter context.*")

    print("\n🚀 启动 Minibot 网关模式...\n")

    # Load configuration
    config = load_config()

    # Check if any channels are enabled
    if not config.channels.feishu.enabled:
        print("❌ 没有启用任何通道。请在配置文件中启用至少一个通道。")
        print(f"📝 配置文件位置: ~/.minibot/config.json")
        return

    # Create message bus
    bus = MessageBus()

    # Create channel manager
    channel_manager = ChannelManager(config, bus)

    # Create executor with bus
    executor = NaturalTaskExecutor(bus=bus)

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

                # 检查是否在等待用户确认
                if executor.waiting_for_approval:
                    print(f"✅ 【收到用户确认】\n")
                    response = msg.content.lower().strip()

                    if response in ["yes", "y"]:
                        print(f"✅ 用户同意执行命令\n")
                        executor.waiting_for_approval = False
                        executor.approval_response = "yes"

                        # 执行待执行的命令
                        if executor.pending_decision:
                            print(f"🤖 【继续执行命令】\n")
                            decision = executor.pending_decision

                            # 执行工具
                            executor._handle_tool_execution(decision)

                            # 继续下一步 - 使用ensure_future避免嵌套asyncio问题
                            executor.step_count += 1
                            context = executor._build_context()
                            asyncio.ensure_future(
                                executor._execute_step_async(
                                    executor.pending_user_request, context
                                )
                            )

                            executor.pending_decision = None
                            executor.pending_user_request = None
                            executor.pending_context = None
                        continue

                    elif response in ["all", "a"]:
                        print(f"✅ 用户允许所有命令\n")
                        executor.allow_all_commands = True
                        executor.waiting_for_approval = False
                        executor.approval_response = "all"

                        # 执行待执行的命令
                        if executor.pending_decision:
                            print(f"🤖 【继续执行命令】\n")
                            decision = executor.pending_decision
                            executor._handle_tool_execution(decision)
                            executor.step_count += 1
                            context = executor._build_context()
                            asyncio.ensure_future(
                                executor._execute_step_async(
                                    executor.pending_user_request, context
                                )
                            )

                            executor.pending_decision = None
                            executor.pending_user_request = None
                            executor.pending_context = None
                        continue

                    elif response in ["no", "n"]:
                        print(f"❌ 用户拒绝执行命令\n")
                        executor.waiting_for_approval = False
                        executor.approval_response = "no"
                        executor.pending_decision = None
                        executor.pending_user_request = None
                        executor.pending_context = None

                        # 发送拒绝消息
                        reject_msg = OutboundMessage(
                            channel=msg.channel,
                            chat_id=msg.sender_id,
                            content="❌ 命令已取消",
                        )
                        await bus.publish_outbound(reject_msg)
                        continue
                    else:
                        # 无效的回复
                        invalid_msg = OutboundMessage(
                            channel=msg.channel,
                            chat_id=msg.sender_id,
                            content="⚠️ 无效的回复，请回复 yes/all/no",
                        )
                        await bus.publish_outbound(invalid_msg)
                        continue

                # 正常处理消息
                # Store message context
                executor.current_sender_id = msg.sender_id
                executor.current_chat_id = msg.chat_id
                executor.current_channel = msg.channel

                # Check for /clear command
                if msg.content.lower().strip() == "/clear":
                    executor._clear_history()
                    await executor._send_to_channel("✅ 历史会话已清除")
                    continue

                # Check for /stop command
                if msg.content.lower().strip() == "/stop":
                    executor.should_stop = True
                    executor.waiting_for_approval = False
                    executor.pending_decision = None
                    await executor._send_to_channel("⏹️ 任务已停止")
                    continue

                # Check for /compact command
                if msg.content.lower().strip() == "/compact":
                    # 显示当前记忆大小（从文件读取完整历史）
                    all_history = executor.memory_manager.load_execution_history()
                    if all_history:
                        history_text = "\n".join(all_history)
                        current_tokens = executor._estimate_tokens(history_text)
                        compact_msg = (
                            f"📊 近期记忆: {current_tokens} tokens，正在压缩..."
                        )
                    else:
                        compact_msg = "⏳ 正在压缩任务历史记录..."

                    await executor._send_to_channel(compact_msg)
                    # 在后台线程中执行压缩（不等待）
                    import threading

                    event_loop = asyncio.get_running_loop()
                    compression_thread = threading.Thread(
                        target=executor._compress_and_notify,
                        args=(event_loop,),
                        daemon=True,
                    )
                    compression_thread.start()
                    continue

                # Reset execution state for new message
                executor._cleanup_large_results()  # 清理上一个任务的大型网页结果
                executor.ai_engine.truncate_web_results(
                    max_length=300
                )  # 截断AI引擎对话历史中的网页结果
                executor.ai_engine.clear_history()  # 清空AI引擎的对话历史
                # 不清空 execution_history，让它积累所有任务的执行历史
                # 直到用户输入 /compact 时才压缩
                executor.step_count = 0  # 重置步数计数器（每个新任务重新开始计数）
                executor.web_search_count = 0  # 重置搜索计数
                executor.allow_all_commands = False
                executor.should_stop = False

                # Execute task
                print(f"🤖 【AI 开始处理】\n")
                executor.execute_task(msg.content)
                print(f"\n✅ 【处理完成】\n")

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"❌ 处理消息错误: {e}")

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
    # ASCII Art 欢迎图案
    ascii_art = """
    ███╗   ███╗██╗███╗   ██╗██╗██████╗  ██████╗ ████████╗
    ████╗ ████║██║████╗  ██║██║██╔══██╗██╔═══██╗╚══██╔══╝
    ██╔████╔██║██║██╔██╗ ██║██║██║  ██║██║   ██║   ██║
    ██║╚██╔╝██║██║██║╚██╗██║██║██║  ██║██║   ██║   ██║
    ██║ ╚═╝ ██║██║██║ ╚████║██║██████╔╝╚██████╔╝   ██║
    ╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝╚═╝╚═════╝  ╚═════╝    ╚═╝

    轻量级 AI 自动化工具
    """
    print(ascii_art)
    print("✨ 我会一步步帮你完成任务")
    print("💡 按 Ctrl+C 可以中断当前任务，继续提问\n")

    executor = NaturalTaskExecutor()

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
                executor._compress_current_task_manual()
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
            print("\n\n⚠️  任务已中断")
            print("💡 你可以继续提问新的任务\n")
            # 不退出，继续循环
            continue
        except Exception as e:
            print(f"\n❌ 错误: {str(e)}\n")


if __name__ == "__main__":
    import sys

    # Check for gateway mode or desktop mode
    if len(sys.argv) > 1:
        if sys.argv[1] == "gateway":
            asyncio.run(gateway_mode())
        elif sys.argv[1] == "desktop":
            from agent.ui.desktop import main as desktop_main

            desktop_main.main()
        else:
            print(f"Unknown command: {sys.argv[1]}")
            print("Usage: python chat.py [gateway|desktop]")
    else:
        main()
