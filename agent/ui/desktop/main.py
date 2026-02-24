#!/usr/bin/env python3
"""Minibot Desktop UI - Full Featured Desktop Application"""

import sys
import os
import threading
import queue
import eel
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agent.core.ai_engine import AIEngine
from agent.core.extended_tool_executor import ExtendedToolExecutor
from agent.core.skills import SkillsLoader
from agent.core.memory_manager import MemoryManager
from datetime import datetime

# 加载环境变量
project_root = Path(__file__).parent.parent.parent.parent
load_dotenv(project_root / ".env")


class DesktopTaskExecutor:
    def __init__(self):
        self.ai_engine: Optional[AIEngine] = None
        self.tool_executor: Optional[ExtendedToolExecutor] = None
        self.skills_loader: Optional[SkillsLoader] = None
        self.memory_manager: Optional[MemoryManager] = None
        self.step_count = 0
        self.max_steps = int(os.getenv("MAX_STEPS", "20"))
        self.allow_all_commands = False
        self.web_search_count = 0
        self.max_web_searches = int(os.getenv("MAX_WEB_SEARCHES", "3"))
        self.max_tokens = int(os.getenv("MAX_TOKENS", "30000"))
        self.compress_at = int(os.getenv("COMPRESS_AT", "25000"))
        self.accumulated_compression = ""
        self.pending_approval: Optional[dict] = None
        self.current_user_message = ""
        self.current_context = ""
        self._current_thread: Optional[threading.Thread] = None

    def initialize(self):
        try:
            self.ai_engine = AIEngine()
            project_root = Path(__file__).parent.parent.parent.parent
            workspace_path = project_root / "workspace"
            workspace_path.mkdir(exist_ok=True)
            self.skills_loader = SkillsLoader(workspace_path)
            self.tool_executor = ExtendedToolExecutor(skills_loader=self.skills_loader)
            memory_dir = project_root / "Memory"
            self.memory_manager = MemoryManager(str(memory_dir))
            self.accumulated_compression = (
                self.memory_manager.load_accumulated_compression()
            )
            return True, "Initialized successfully"
        except Exception as e:
            return False, str(e)

    def get_available_tools(self):
        return self.tool_executor.get_available_tools()

    def build_system_prompt(self, user_request: str, context: str = "") -> tuple:
        project_root = Path(__file__).parent.parent.parent.parent
        workspace_path = project_root / "workspace"

        skills_summary = ""
        try:
            skills = self.skills_loader.list_skills()
            skills_summary = "\n".join(
                [
                    f"- **{s.get('name', 'unknown')}**: {s.get('description', '')}"
                    for s in skills
                ]
            )
        except:
            pass

        agent_md_path = project_root / "Agent.md"
        with open(agent_md_path, "r", encoding="utf-8") as f:
            agent_template = f.read()

        split_marker = "【用户任务】"
        split_idx = agent_template.find(split_marker)

        if split_idx >= 0:
            system_prompt_template = agent_template[:split_idx]
            user_message_template = agent_template[split_idx:]
        else:
            system_prompt_template = agent_template
            user_message_template = ""

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
            self.accumulated_compression or "这是第一个任务",
        )

        execution_history = self.memory_manager.load_execution_history()
        history_text = (
            "\n".join(execution_history) if execution_history else "还没有执行任何步骤"
        )
        system_prompt = system_prompt.replace("{execution_history}", history_text)

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
            "{builtin_skills_path}", str(project_root / "agent" / "skills")
        )
        system_prompt = system_prompt.replace(
            "{workspace_skills_path}", str(workspace_path / "skills")
        )
        system_prompt = system_prompt.replace(
            "{desktop_path}", str(Path.home() / "Desktop")
        )
        system_prompt = system_prompt.replace(
            "{output_path}", str(workspace_path / "output")
        )
        system_prompt = system_prompt.replace(
            "{temp_path}", str(workspace_path / "temp")
        )
        system_prompt = system_prompt.replace(
            "{cache_path}", str(workspace_path / "cache")
        )
        system_prompt = system_prompt.replace("{skills_summary}", skills_summary)

        user_message = user_message_template
        user_message = user_message.replace("{user_request}", user_request)
        user_message = user_message.replace("{context}", context)

        return system_prompt, user_message

    def parse_response(self, response: str, max_retries: int = 2) -> dict:
        """尝试解析JSON响应，失败时重试（与 CLI 完全一致）"""
        import json
        import re

        for attempt in range(max_retries):
            try:
                # 首先尝试使用分隔符提取JSON
                start_marker = "===== JSON START ====="
                end_marker = "===== JSON END ====="

                start_idx = response.find(start_marker)
                end_idx = response.find(end_marker)

                if start_idx >= 0 and end_idx > start_idx:
                    json_str = response[start_idx + len(start_marker) : end_idx].strip()
                else:
                    start_idx = response.find("{")
                    end_idx = response.rfind("}") + 1

                    if start_idx < 0 or end_idx <= start_idx:
                        if attempt == max_retries - 1:
                            print(f"⚠️  无法找到JSON对象")
                        continue

                    json_str = response[start_idx:end_idx]

                # 尝试修复常见的JSON问题
                json_str = json_str.replace("\n", " ")
                json_str = json_str.replace("\r", "")

                if json_str.startswith("```"):
                    json_str = json_str[3:]
                if json_str.endswith("```"):
                    json_str = json_str[:-3]
                json_str = json_str.strip()

                try:
                    decision = json.loads(json_str)
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
                    # 修复策略1
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
                        # 修复策略2
                        json_str = re.sub(
                            r'(?<=[a-zA-Z0-9])"(?=[a-zA-Z0-9=])', '\\"', json_str
                        )

                        try:
                            decision = json.loads(json_str)
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
                            # 修复策略3
                            for i in range(len(json_str) - 1, 0, -1):
                                if json_str[i] == "}":
                                    try:
                                        decision = json.loads(json_str[: i + 1])
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

    def _is_tool_requires_approval(self, tool_name: str) -> bool:
        """Check if a tool requires user approval before execution（与 CLI 完全一致）"""
        safe_tools = {
            "load_skill",
            "read_pdf",
            "read_markdown",
            "read_json",
            "file_read",
            "file_list",
            "search_files",
            "get_file_info",
            "web_search",
            "read_url",
            "set_timer",
        }
        return tool_name not in safe_tools

    def execute_tool(self, tool_name: str, params: dict) -> str:
        try:
            # 保存原始 JSON 请求到记忆
            import json

            tool_json = json.dumps(
                {"tool": tool_name, "params": params}, ensure_ascii=False
            )
            history_entry = f"执行 {tool_name}:\n{tool_json}\n结果: "

            result = self.tool_executor.execute({"tool": tool_name, "params": params})

            # 追加结果到记忆
            history_entry += result

            self.memory_manager.append_execution_step(history_entry)
            return result
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            self.memory_manager.append_execution_step(
                f"执行 {tool_name} 失败: {error_msg}"
            )
            return error_msg

    def _estimate_tokens(self, text: str) -> int:
        """估算文本的token数量（与 CLI 完全一致）"""
        import re

        chinese_chars = re.findall(r"[\u4e00-\u9fff]", text)
        text_without_chinese = re.sub(r"[\u4e00-\u9fff]", "", text)
        english_words = re.findall(r"\b[a-zA-Z]+\b", text_without_chinese)
        other_chars = (
            len(text) - len(chinese_chars) - sum(len(w) for w in english_words)
        )
        chinese_tokens = int(len(chinese_chars) * 1.7)
        english_tokens = int(len(english_words) * 1.9)
        other_tokens = int(other_chars / 2.5) + 200
        total_tokens = chinese_tokens + english_tokens + other_tokens
        return max(total_tokens, 1)

    def _auto_compress_if_needed(self):
        """检查是否需要自动压缩（超过配置的 max_tokens 才压缩）"""
        all_history = self.memory_manager.load_execution_history()
        if all_history:
            history_text = "\n".join(all_history)
            current_tokens = self._estimate_tokens(history_text)
            if current_tokens > self.compress_at:
                print(f"⏳ 近期记忆已达 {current_tokens} tokens，正在压缩任务历史...")

                # 延迟压缩，不阻塞当前响应
                def compress_in_background():
                    import time

                    time.sleep(1)  # 等待1秒让当前响应完成
                    success, msg = self._compress_current_task_manual()
                    if success:
                        print(f"✅ {msg}")
                    else:
                        print(f"⚠️ {msg}")

                compress_thread = threading.Thread(
                    target=compress_in_background, daemon=True
                )
                compress_thread.start()

    def get_current_tokens(self) -> int:
        """获取当前执行历史的token数量"""
        all_history = self.memory_manager.load_execution_history()
        if all_history:
            history_text = "\n".join(all_history)
            return self._estimate_tokens(history_text)
        return 0

    def _compress_current_task_manual(self) -> tuple:
        """与 CLI 完全一致的压缩逻辑，调用 AI 生成摘要"""
        execution_history = self.memory_manager.load_execution_history()

        if not execution_history:
            return False, "没有执行历史可以压缩"

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
            self.ai_engine.clear_history()

            print(
                f"[DEBUG] Compression API response: {task_summary[:200] if task_summary else 'None'}"
            )

            if not task_summary or task_summary.strip() == "":
                return False, "AI未能生成摘要，压缩取消"
            # 检查连接错误
            if (
                "ConnectionResetError" in task_summary
                or "Connection aborted" in task_summary
            ):
                return False, f"网络连接错误: 连接被重置"
            # 只检查明确的API错误前缀
            if task_summary.startswith("API Error:"):
                return False, f"API错误: {task_summary[:100]}"

        except Exception as e:
            return False, f"AI调用失败: {str(e)}"

        archive_path = self.memory_manager.save_compression_archive(history_text)
        full_archive_path = str(self.memory_manager.memory_dir / archive_path)

        if self.accumulated_compression:
            self.accumulated_compression = f"{task_summary}\n📁 详细内容: {full_archive_path}\n\n{self.accumulated_compression}"
        else:
            self.accumulated_compression = (
                f"{task_summary}\n📁 详细内容: {full_archive_path}"
            )

        self.memory_manager.save_accumulated_compression(self.accumulated_compression)
        self.ai_engine.clear_history()
        self.step_count = 0
        self.memory_manager.clear_execution_history()

        return True, f"历史记录已压缩并保存到记忆文件\n📁 存档位置: {full_archive_path}"

    def _clear_history(self) -> dict:
        """与 CLI 完全一致的清除历史逻辑"""
        if self.ai_engine:
            self.ai_engine.clear_history()
        self.step_count = 0
        self.web_search_count = 0
        self.allow_all_commands = False
        self.accumulated_compression = ""
        self.memory_manager.clear_all()
        return {"success": True, "message": "历史会话已清除，记忆文件已删除"}

    def clear_conversation(self):
        return self._clear_history()

    def _build_context(self) -> str:
        """Build context from memory files and accumulated compression（与 CLI 完全一致）"""
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


minibot = DesktopTaskExecutor()
current_message_id = 0
step_queue = queue.Queue()


def push_step(step):
    step_queue.put(step)


@eel.expose
def initialize():
    return minibot.initialize()


@eel.expose
def send_message(message: str, message_id: int = 0):
    """处理消息，支持 /clear、/compact 和 /stop 快捷命令（与 CLI 完全一致）"""
    global current_message_id
    current_message_id = message_id

    message_lower = message.lower().strip()

    if message_lower == "/clear":
        result = minibot._clear_history()
        push_step({"type": "final", "content": "✅ 历史会话已清除，记忆文件已删除"})
        return {"status": "done", "command": "clear"}

    if message_lower == "/compact":
        push_step({"type": "compressing", "content": "⏳ 压缩中..."})
        success, msg = minibot._compress_current_task_manual()
        if success:
            push_step({"type": "final", "content": f"✅ {msg}"})
        else:
            push_step({"type": "final", "content": f"⚠️ {msg}"})
        return {"status": "done", "command": "compact"}

    # 新消息，重置所有状态
    minibot.pending_approval = None
    minibot.step_count = 0
    minibot.allow_all_commands = False
    minibot.current_user_message = ""
    minibot.current_context = ""

    # 清除之前的轮询
    global poll_active
    poll_active = False

    def process_in_thread():
        try:
            minibot.step_count = 0
            minibot.web_search_count = 0
            minibot.pending_approval = None
            # 不清空执行历史（与 CLI 一致，历史跨任务保持直到压缩）
            minibot.memory_manager.append_execution_step(f"【用户请求】{message}")

            # 使用 _build_context 从记忆文件加载完整内容（与 CLI 一致）
            context = minibot._build_context()

            while minibot.step_count < minibot.max_steps:
                system_prompt, user_msg = minibot.build_system_prompt(message, context)
                response = minibot.ai_engine.call_api(
                    user_msg, system_prompt=system_prompt
                )
                minibot.ai_engine.clear_history()

                json_start = response.find("=====")
                natural_lang = ""
                if json_start > 0:
                    before_json = response[:json_start].strip()
                    if "接下来我要:" in before_json:
                        idx = before_json.find("接下来我要:")
                        natural_lang = before_json[idx:].strip()
                        if natural_lang:
                            push_step({"type": "thinking", "content": natural_lang})
                            minibot.memory_manager.append_execution_step(
                                f"【AI响应】{natural_lang}"
                            )

                decision = minibot.parse_response(response)

                # 如果解析失败，继续下一步（与 CLI 一致）
                if decision is None:
                    print("\n⚠️ 无法解析响应，继续下一步...\n")
                    push_step(
                        {"type": "thinking", "content": "⚠️ 无法解析响应，重试中..."}
                    )
                    minibot.step_count += 1
                    context = minibot._build_context()
                    continue

                action = decision.get("action")

                if action == "execute_tool":
                    tool_name = decision.get("tool", "")
                    params = decision.get("params", {})

                    # 检查是否需要确认（与 CLI 一致，安全工具直接执行）
                    if (
                        minibot._is_tool_requires_approval(tool_name)
                        and not minibot.allow_all_commands
                    ):
                        minibot.pending_approval = {
                            "tool": tool_name,
                            "params": params,
                            "thinking": natural_lang,
                        }
                        minibot.current_user_message = message
                        push_step(
                            {
                                "type": "pending_approval",
                                "tool": tool_name,
                                "params": params,
                                "thinking": natural_lang,
                            }
                        )
                        return
                    else:
                        tool_result = minibot.execute_tool(tool_name, params)
                        push_step(
                            {"type": "tool", "tool": tool_name, "result": tool_result}
                        )
                        if tool_name == "web_search":
                            minibot.web_search_count += 1
                        # 截断 web_search 和 read_url 结果（与 CLI 一致）
                        minibot.ai_engine.truncate_web_results(max_length=300)
                        # 使用 _build_context 从记忆文件加载完整内容（与 CLI 一致）
                        context = minibot._build_context()

                elif action == "respond":
                    final_response = decision.get("response", response)
                    final_response = final_response.split("=====")[0].strip()
                    push_step({"type": "final", "content": final_response})
                    minibot.memory_manager.append_execution_step(
                        f"最终回应: {final_response}"
                    )
                    # 检查是否需要自动压缩（与 CLI 一致，超过 30000 token 才压缩）
                    minibot._auto_compress_if_needed()
                    return
                else:
                    clean_response = response.split("=====")[0].strip()
                    push_step({"type": "final", "content": clean_response})
                    minibot.memory_manager.append_execution_step(
                        f"最终回应: {clean_response}"
                    )
                    return

            push_step({"type": "final", "content": "任务已达最大步数"})

        except Exception as e:
            push_step({"type": "error", "content": str(e)})

    thread = threading.Thread(target=process_in_thread)
    thread.daemon = True
    thread.start()
    return {"status": "processing"}


@eel.expose
def approve_tool(action: str):
    def process_in_thread():
        try:
            if action == "deny" or not minibot.pending_approval:
                push_step({"type": "final", "content": "操作已取消"})
                minibot.pending_approval = None
                return

            if action == "all":
                minibot.allow_all_commands = True

            tool_name = minibot.pending_approval["tool"]
            params = minibot.pending_approval["params"]
            user_message = minibot.current_user_message
            minibot.pending_approval = None

            tool_result = minibot.execute_tool(tool_name, params)
            push_step({"type": "tool", "tool": tool_name, "result": tool_result})

            if tool_name == "web_search":
                minibot.web_search_count += 1
            # 截断 web_search 和 read_url 结果（与 CLI 一致）
            minibot.ai_engine.truncate_web_results(max_length=300)
            # 使用 _build_context 从记忆文件加载完整内容（与 CLI 一致）
            context = minibot._build_context()

            while minibot.step_count < minibot.max_steps:
                minibot.step_count += 1

                system_prompt, user_msg = minibot.build_system_prompt(
                    user_message, context
                )
                response = minibot.ai_engine.call_api(
                    user_msg, system_prompt=system_prompt
                )
                minibot.ai_engine.clear_history()

                json_start = response.find("=====")
                natural_lang = ""
                if json_start > 0:
                    before_json = response[:json_start].strip()
                    if "接下来我要:" in before_json:
                        idx = before_json.find("接下来我要:")
                        natural_lang = before_json[idx:].strip()
                        if natural_lang:
                            push_step({"type": "thinking", "content": natural_lang})
                            minibot.memory_manager.append_execution_step(
                                f"【AI响应】{natural_lang}"
                            )

                decision = minibot.parse_response(response)

                # 如果解析失败，继续下一步（与 CLI 一致）
                if decision is None:
                    print("\n⚠️ 无法解析响应，继续下一步...\n")
                    push_step(
                        {"type": "thinking", "content": "⚠️ 无法解析响应，重试中..."}
                    )
                    context = minibot._build_context()
                    continue

                resp_action = decision.get("action")

                if resp_action == "execute_tool":
                    tool_name = decision.get("tool", "")
                    params = decision.get("params", {})

                    # 检查是否需要确认（与 CLI 一致，安全工具直接执行）
                    if (
                        minibot._is_tool_requires_approval(tool_name)
                        and not minibot.allow_all_commands
                    ):
                        minibot.pending_approval = {
                            "tool": tool_name,
                            "params": params,
                            "thinking": natural_lang,
                        }
                        push_step(
                            {
                                "type": "pending_approval",
                                "tool": tool_name,
                                "params": params,
                                "thinking": natural_lang,
                            }
                        )
                        return

                    tool_result = minibot.execute_tool(tool_name, params)
                    push_step(
                        {"type": "tool", "tool": tool_name, "result": tool_result}
                    )
                    if tool_name == "web_search":
                        minibot.web_search_count += 1
                    # 使用 _build_context 从记忆文件加载完整内容（与 CLI 一致）
                    context = minibot._build_context()
                    continue

                elif resp_action == "respond":
                    final_response = decision.get("response", response)
                    final_response = final_response.split("=====")[0].strip()
                    push_step({"type": "final", "content": final_response})
                    minibot.memory_manager.append_execution_step(
                        f"最终回应: {final_response}"
                    )
                    # 检查是否需要自动压缩（与 CLI 一致，超过 30000 token 才压缩）
                    minibot._auto_compress_if_needed()
                    return
                else:
                    clean_response = response.split("=====")[0].strip()
                    push_step({"type": "final", "content": clean_response})
                    minibot.memory_manager.append_execution_step(
                        f"最终回应: {clean_response}"
                    )
                    return

            push_step({"type": "final", "content": "任务已达最大步数"})

        except Exception as e:
            push_step({"type": "error", "content": str(e)})

    thread = threading.Thread(target=process_in_thread)
    thread.daemon = True
    thread.start()


@eel.expose
def get_next_result():
    try:
        if not step_queue.empty():
            return step_queue.get_nowait()
    except:
        pass
    return None


@eel.expose
def clear_conversation():
    return minibot._clear_history()


@eel.expose
def compact_memory():
    success, msg = minibot._compress_current_task_manual()
    if success:
        return {"success": True, "message": msg}
    else:
        return {"success": False, "error": msg}


@eel.expose
def get_tools():
    return minibot.get_available_tools()


@eel.expose
def list_workspace_files(folder: str):
    """List files and folders in workspace output or temp folder"""
    try:
        project_root = Path(__file__).parent.parent.parent.parent
        folder_path = project_root / "workspace" / folder

        if not folder_path.exists():
            return []

        items = []
        for item in folder_path.iterdir():
            if item.name.startswith("."):
                continue
            if item.is_dir():
                items.append(
                    {
                        "name": item.name,
                        "type": "folder",
                        "size": 0,
                        "modified": item.stat().st_mtime,
                    }
                )
            else:
                items.append(
                    {
                        "name": item.name,
                        "type": "file",
                        "size": item.stat().st_size,
                        "modified": item.stat().st_mtime,
                    }
                )

        # 文件夹在前，文件在后，按修改时间排序
        items.sort(key=lambda x: (x["type"] == "file", -x["modified"]))
        return items
    except Exception as e:
        print(f"Error listing files: {e}")
        return []

        files = []
        for f in folder_path.iterdir():
            if f.is_file():
                files.append(
                    {
                        "name": f.name,
                        "size": f.stat().st_size,
                        "modified": f.stat().st_mtime,
                    }
                )

        files.sort(key=lambda x: x["modified"], reverse=True)
        return files
    except Exception as e:
        print(f"Error listing files: {e}")
        return []


@eel.expose
def read_workspace_file(folder: str, filename: str):
    """Read a file from workspace output or temp folder"""
    try:
        project_root = Path(__file__).parent.parent.parent.parent
        file_path = project_root / "workspace" / folder / filename

        if not file_path.exists():
            return {"error": "File not found"}

        # Check file size (limit to 1MB)
        if file_path.stat().st_size > 1024 * 1024:
            return {"error": "File too large (max 1MB)"}

        # Try to read as text
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            return {"content": content}
        except UnicodeDecodeError:
            return {"error": "Binary file, cannot display as text"}
    except Exception as e:
        return {"error": str(e)}


@eel.expose
def read_memory_file(file_type: str):
    """Read memory files (execution_history or accumulated_compression)"""
    try:
        project_root = Path(__file__).parent.parent.parent.parent
        memory_dir = project_root / "Memory"

        if file_type == "execution_history":
            file_path = memory_dir / "execution_history.md"
        elif file_type == "accumulated_compression":
            file_path = memory_dir / "accumulated_compression.md"
        else:
            return {"error": "Unknown memory file type"}

        if not file_path.exists():
            return {"content": "(file does not exist)"}

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"content": content if content.strip() else "(empty)"}
    except Exception as e:
        return {"error": str(e)}


@eel.expose
def open_workspace_file(folder: str, filename: str):
    """Open a file from workspace with system default application"""
    try:
        import subprocess
        import platform

        project_root = Path(__file__).parent.parent.parent.parent
        file_path = project_root / "workspace" / folder / filename

        if not file_path.exists():
            return {"error": "File not found"}

        abs_path = str(file_path.resolve())

        if platform.system() == "Darwin":  # macOS
            subprocess.run(["open", abs_path])
        elif platform.system() == "Windows":
            os.startfile(abs_path)
        else:  # Linux
            subprocess.run(["xdg-open", abs_path])

        return {"success": True}
    except Exception as e:
        return {"error": str(e)}


@eel.expose
def open_memory_file(file_type: str):
    """Open memory file with system default application"""
    try:
        import subprocess
        import platform

        project_root = Path(__file__).parent.parent.parent.parent
        memory_dir = project_root / "Memory"

        if file_type == "execution_history":
            file_path = memory_dir / "execution_history.md"
        elif file_type == "accumulated_compression":
            file_path = memory_dir / "accumulated_compression.md"
        else:
            return {"error": "Unknown memory file type"}

        if not file_path.exists():
            # 创建空文件
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.touch()

        abs_path = str(file_path.resolve())

        if platform.system() == "Darwin":  # macOS
            subprocess.run(["open", abs_path])
        elif platform.system() == "Windows":
            os.startfile(abs_path)
        else:  # Linux
            subprocess.run(["xdg-open", abs_path])

        return {"success": True}
    except Exception as e:
        return {"error": str(e)}


@eel.expose
def load_settings():
    """Load settings from .env file"""
    try:
        project_root = Path(__file__).parent.parent.parent.parent
        env_file = project_root / ".env"

        settings = {
            "api_base_url": "",
            "api_key": "",
            "api_model": "",
            "tavily_api_key": "",
            "max_steps": "20",
            "max_tokens": "30000",
            "max_web_searches": "3",
            "compress_at": "25000",
        }

        if env_file.exists():
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if key == "API_BASE_URL":
                            settings["api_base_url"] = value
                        elif key == "API_KEY":
                            settings["api_key"] = value
                        elif key == "API_MODEL":
                            settings["api_model"] = value
                        elif key == "TAVILY_API_KEY":
                            settings["tavily_api_key"] = value
                        elif key == "MAX_STEPS":
                            settings["max_steps"] = value
                        elif key == "MAX_TOKENS":
                            settings["max_tokens"] = value
                        elif key == "MAX_WEB_SEARCHES":
                            settings["max_web_searches"] = value
                        elif key == "COMPRESS_AT":
                            settings["compress_at"] = value

        return settings
    except Exception as e:
        print(f"Error loading settings: {e}")
        return {
            "api_base_url": "",
            "api_key": "",
            "api_model": "",
            "tavily_api_key": "",
            "max_steps": "20",
            "max_tokens": "30000",
            "max_web_searches": "3",
            "compress_at": "25000",
        }


@eel.expose
def save_settings(settings: dict):
    """Save settings to .env file, preserving other existing settings"""
    try:
        project_root = Path(__file__).parent.parent.parent.parent
        env_file = project_root / ".env"

        # 读取现有配置，保留其他字段
        existing_settings = {}
        if env_file.exists():
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        existing_settings[key.strip()] = value.strip()

        # 更新需要修改的字段
        existing_settings["API_BASE_URL"] = settings.get("api_base_url", "")
        existing_settings["API_KEY"] = settings.get("api_key", "")
        existing_settings["API_MODEL"] = settings.get("api_model", "")
        existing_settings["MAX_STEPS"] = settings.get("max_steps", "20")
        existing_settings["MAX_TOKENS"] = settings.get("max_tokens", "30000")
        existing_settings["MAX_WEB_SEARCHES"] = settings.get("max_web_searches", "3")
        existing_settings["COMPRESS_AT"] = settings.get("compress_at", "25000")
        existing_settings["TAVILY_API_KEY"] = settings.get("tavily_api_key", "")

        # 写回文件
        with open(env_file, "w", encoding="utf-8") as f:
            for key, value in existing_settings.items():
                f.write(f"{key}={value}\n")

        # 重新加载环境变量
        load_dotenv(env_file, override=True)

        # 更新运行时配置
        minibot.max_steps = int(os.getenv("MAX_STEPS", "20"))
        minibot.max_tokens = int(os.getenv("MAX_TOKENS", "30000"))
        minibot.max_web_searches = int(os.getenv("MAX_WEB_SEARCHES", "3"))
        minibot.compress_at = int(os.getenv("COMPRESS_AT", "25000"))

        # 更新 AI Engine 的配置
        if minibot.ai_engine:
            minibot.ai_engine.api_key = os.getenv("API_KEY", "")
            minibot.ai_engine.api_base_url = os.getenv(
                "API_BASE_URL", "https://yunwu.ai"
            )
            minibot.ai_engine.model = os.getenv("API_MODEL", "gpt-4")
            minibot.ai_engine.max_tokens = int(os.getenv("MAX_TOKENS", "30000"))

        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


@eel.expose
def get_token_count():
    """获取当前token数量"""
    try:
        tokens = minibot.get_current_tokens()
        return {
            "tokens": tokens,
            "max_tokens": minibot.compress_at,
            "response_max_tokens": minibot.max_tokens,
        }
    except Exception as e:
        return {"tokens": 0, "max_tokens": 25000, "response_max_tokens": 30000}


@eel.expose
def list_skills():
    """列出所有skills，标记是否为内置"""
    try:
        project_root = Path(__file__).parent.parent.parent.parent
        workspace_path = project_root / "workspace"

        skills = []

        # 内置skills
        builtin_skills_path = project_root / "agent" / "skills"
        if builtin_skills_path.exists():
            for skill_dir in builtin_skills_path.iterdir():
                if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                    skills.append(
                        {"name": skill_dir.name, "description": "", "builtin": True}
                    )

        # 用户skills
        user_skills_path = workspace_path / "skills"
        if user_skills_path.exists():
            for skill_dir in user_skills_path.iterdir():
                if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                    skills.append(
                        {"name": skill_dir.name, "description": "", "builtin": False}
                    )

        return skills
    except Exception as e:
        print(f"Error listing skills: {e}")
        return []


@eel.expose
def read_skill_file(skill_name: str):
    """读取skill的SKILL.md文件"""
    try:
        project_root = Path(__file__).parent.parent.parent.parent
        workspace_path = project_root / "workspace"

        # 先检查workspace/skills
        skill_path = workspace_path / "skills" / skill_name / "SKILL.md"
        if not skill_path.exists():
            # 再检查agent/skills
            skill_path = project_root / "agent" / "skills" / skill_name / "SKILL.md"

        if not skill_path.exists():
            return {"error": "Skill not found"}

        with open(skill_path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"content": content}
    except Exception as e:
        return {"error": str(e)}


@eel.expose
def open_skill_folder(skill_name: str):
    """打开skill文件夹"""
    try:
        import subprocess
        import platform

        project_root = Path(__file__).parent.parent.parent.parent

        # 先检查workspace/skills
        skill_path = project_root / "workspace" / "skills" / skill_name
        if not skill_path.exists():
            # 再检查agent/skills
            skill_path = project_root / "agent" / "skills" / skill_name

        if not skill_path.exists():
            return {"success": False, "error": "Skill not found"}

        abs_path = str(skill_path.resolve())

        if platform.system() == "Darwin":  # macOS
            subprocess.run(["open", abs_path])
        elif platform.system() == "Windows":
            os.startfile(abs_path)
        else:  # Linux
            subprocess.run(["xdg-open", abs_path])

        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


@eel.expose
def select_skill_folder():
    """打开文件夹选择对话框"""
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.wm_attributes("-topmost", 1)

        folder_path = filedialog.askdirectory(title="Select Skill Folder")

        if not folder_path:
            return {"cancelled": True}

        import shutil

        source_path = Path(folder_path)
        skill_file = source_path / "SKILL.md"

        if not skill_file.exists():
            return {
                "success": False,
                "error": "SKILL.md not found in selected folder",
                "cancelled": False,
            }

        project_root = Path(__file__).parent.parent.parent.parent
        skills_dir = project_root / "workspace" / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)

        skill_name = source_path.name
        dest_path = skills_dir / skill_name

        if dest_path.exists():
            return {
                "success": False,
                "error": f"Skill '{skill_name}' already exists",
                "cancelled": False,
            }

        shutil.copytree(source_path, dest_path)
        return {"success": True, "name": skill_name, "cancelled": False}
    except Exception as e:
        return {"success": False, "error": str(e), "cancelled": False}


@eel.expose
def delete_skill(skill_name: str):
    """删除skill（只能删除用户skill）"""
    try:
        import shutil

        project_root = Path(__file__).parent.parent.parent.parent

        # 检查是否为内置skill
        builtin_path = project_root / "agent" / "skills" / skill_name
        if builtin_path.exists():
            return {"success": False, "error": "Cannot delete built-in skill"}

        # 检查用户skill
        skill_path = project_root / "workspace" / "skills" / skill_name

        if not skill_path.exists():
            return {"success": False, "error": "Skill not found"}

        shutil.rmtree(skill_path)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


@eel.expose
def open_workspace_subfolder(folder: str, subfolder: str):
    """打开workspace子文件夹"""
    try:
        import subprocess
        import platform

        project_root = Path(__file__).parent.parent.parent.parent
        folder_path = project_root / "workspace" / folder / subfolder

        if not folder_path.exists():
            return {"success": False, "error": "Folder not found"}

        abs_path = str(folder_path.resolve())

        if platform.system() == "Darwin":  # macOS
            subprocess.run(["open", abs_path])
        elif platform.system() == "Windows":
            os.startfile(abs_path)
        else:  # Linux
            subprocess.run(["xdg-open", abs_path])

        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def main():
    import socket

    ui_dir = Path(__file__).parent
    eel.init(str(ui_dir))

    def find_available_port(start_port=8000):
        for port in range(start_port, start_port + 100):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(("localhost", port))
                    return port
            except OSError:
                continue
        return 8000

    port = find_available_port()
    print(f"Starting Minibot Desktop on port {port}...")

    eel.start(
        "index.html",
        mode="chrome",
        cmdline_args=["--disable-fence"],
        size=(1200, 800),
        port=port,
    )


if __name__ == "__main__":
    main()
