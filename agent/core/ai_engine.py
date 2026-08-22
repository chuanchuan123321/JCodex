"""AI Agent Core Engine - Native function calling support"""

import os
import json
import requests
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable, Union
from dataclasses import dataclass, field
from dotenv import load_dotenv
from urllib.parse import urlparse

from agent.core.env_utils import env_float, env_int

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=True)


@dataclass
class Message:
    """Message data structure"""

    role: str  # "user" or "assistant"
    content: Any


@dataclass
class ToolCall:
    """Represents a tool call from the LLM"""

    id: str
    name: str
    arguments: Dict[str, Any]
    index: int = 0


@dataclass
class AssistantMessage:
    """Assistant message with optional tool calls"""

    role: str = "assistant"
    content: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)


class AIEngine:
    """Core AI Engine for handling API calls with native function calling"""

    @staticmethod
    def is_local_base_url(api_base_url: str) -> bool:
        """Whether the base URL points to a loopback model server."""
        host = (urlparse(api_base_url or "").hostname or "").lower()
        return host in {"127.0.0.1", "localhost", "::1", "0.0.0.0"}

    @staticmethod
    def normalize_api_base_url(api_base_url: str) -> str:
        """Strip trailing chat-completion path fragments from a base URL."""
        api_base = (api_base_url or "").rstrip("/")
        for old_path in ["/v4/chat/completions", "/v1/chat/completions", "/v4", "/v1"]:
            if api_base.endswith(old_path):
                api_base = api_base[:-len(old_path)]
                break
        return api_base.rstrip("/")

    @staticmethod
    def get_api_path_for_base_url(api_base_url: str) -> str:
        """Pick the chat-completions path for the current provider."""
        return "/v4/chat/completions" if "bigmodel.cn" in api_base_url else "/v1/chat/completions"

    def __init__(self, config_name: Optional[str] = None):
        # 尝试从配置管理器加载配置
        try:
            from agent.core.config_manager import ConfigManager
            config_manager = ConfigManager()

            if config_name:
                # 如果指定了配置名称，使用该配置
                config = config_manager.get_config(config_name)
                if not config:
                    raise ValueError(f"Configuration '{config_name}' not found")
                config_manager.set_active_config(config_name)
                config_manager.export_to_env()
                config_manager.export_search_keys_to_env()
            elif not os.getenv("API_BASE_URL"):
                # 如果环境中没有配置，尝试使用活跃配置
                config = config_manager.get_active_config()
                if config:
                    config_manager.export_to_env()
                    config_manager.export_search_keys_to_env()
        except ImportError:
            pass  # 配置管理器不可用，使用环境变量

        self.api_base_url = os.getenv("API_BASE_URL", "https://api.deepseek.com")
        self.api_key = os.getenv("API_KEY")
        self.model = os.getenv("API_MODEL", "deepseek-v4-pro")
        self.max_tokens = env_int("MAX_TOKENS", 50000)
        self.temperature = env_float("TEMPERATURE", 0.7)
        self.reasoning_effort = os.getenv("REASONING_EFFORT", "").strip()

        self.api_base_url = self.normalize_api_base_url(self.api_base_url)
        self.api_path = self.get_api_path_for_base_url(self.api_base_url)

        # 允许空 API key 构造（新用户首次启动未配置时初始化不能失败）；
        # 真正发起请求时才在 _post_chat_completion* 里给出“请先配置”提示。

        self.conversation_history: List[Dict[str, Any]] = []

    def _apply_reasoning_params(self, payload: Dict[str, Any]) -> None:
        """DeepSeek 系列模型：按配置注入推理强度参数（其余模型不注入）。"""
        effort = (self.reasoning_effort or "").strip()
        model = (self.model or "").lower()
        if not effort or "deepseek" not in model:
            return
        payload["reasoning_effort"] = effort
        payload["thinking"] = {"type": "enabled"}

    def _post_chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Send a chat-completions request using the current model settings."""
        if not self.api_key and not self.is_local_base_url(self.api_base_url):
            return {
                "content": "请先在设置中配置 API Key（API_BASE_URL / API_KEY / API_MODEL）",
                "tool_calls": [],
                "finish_reason": "error",
            }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens if max_tokens is not None else self.max_tokens,
            "temperature": temperature if temperature is not None else self.temperature,
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        self._apply_reasoning_params(payload)

        request_timeout = max(1.0, float(timeout if timeout is not None else 120))
        retries = max(1, int(max_retries if max_retries is not None else 3))
        retry_delay = 5

        for attempt in range(retries):
            try:
                response = requests.post(
                    f"{self.api_base_url}{self.api_path}",
                    headers=headers,
                    json=payload,
                    timeout=request_timeout,
                )

                response.raise_for_status()
                result = response.json()
                message = result["choices"][0]["message"]

                content = message.get("content", "") or ""
                finish_reason = message.get("finish_reason", "stop")

                tool_calls = []
                if message.get("tool_calls"):
                    for tc in message["tool_calls"]:
                        func = tc.get("function", {})
                        args = {}
                        if func.get("arguments"):
                            if isinstance(func["arguments"], str):
                                try:
                                    args = json.loads(func["arguments"])
                                except json.JSONDecodeError:
                                    args = {"_raw": func["arguments"]}
                            elif isinstance(func["arguments"], dict):
                                args = func["arguments"]

                        tool_calls.append(
                            ToolCall(
                                id=tc.get("id", ""),
                                name=func.get("name", ""),
                                arguments=args,
                                index=len(tool_calls),
                            )
                        )

                return {
                    "content": content,
                    "tool_calls": tool_calls,
                    "finish_reason": finish_reason,
                }

            except requests.exceptions.RequestException as e:
                if attempt < retries - 1:
                    print(
                        f"[API] 请求失败，{retry_delay}秒后重试 ({attempt + 1}/{retries}): {str(e)}"
                    )
                    import time

                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    return {
                        "content": f"API Error: {str(e)}",
                        "tool_calls": [],
                        "finish_reason": "error",
                    }

    def _post_chat_completion_stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        on_content: Optional[Callable[[str], Optional[bool]]] = None,
        on_tool_delta: Optional[Callable[[Dict[str, Any]], Optional[bool]]] = None,
    ) -> Dict[str, Any]:
        """Send a streaming chat request and assemble the final message."""
        if not self.api_key and not self.is_local_base_url(self.api_base_url):
            return {
                "content": "请先在设置中配置 API Key（API_BASE_URL / API_KEY / API_MODEL）",
                "tool_calls": [],
                "finish_reason": "error",
            }
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens if max_tokens is not None else self.max_tokens,
            "temperature": temperature if temperature is not None else self.temperature,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        self._apply_reasoning_params(payload)

        max_retries = 3
        retry_delay = 5
        for attempt in range(max_retries):
            emitted_content = False
            content_parts: List[str] = []
            streamed_tools: Dict[int, Dict[str, str]] = {}
            finish_reason = "stop"
            reasoning_open = False
            try:
                with requests.post(
                    f"{self.api_base_url}{self.api_path}",
                    headers=headers,
                    json=payload,
                    timeout=(15, 180),
                    stream=True,
                ) as response:
                    response.raise_for_status()
                    if "text/event-stream" not in response.headers.get(
                        "Content-Type", ""
                    ).lower():
                        result = response.json()
                        message = result["choices"][0]["message"]
                        content = message.get("content", "") or ""
                        if content and on_content and on_content(content) is False:
                            return {
                                "content": content,
                                "tool_calls": [],
                                "finish_reason": "cancelled",
                            }
                        tool_calls = []
                        for index, tool_call in enumerate(
                            message.get("tool_calls") or []
                        ):
                            function = tool_call.get("function") or {}
                            raw_arguments = function.get("arguments") or ""
                            try:
                                arguments = (
                                    json.loads(raw_arguments)
                                    if isinstance(raw_arguments, str)
                                    else raw_arguments
                                )
                            except json.JSONDecodeError:
                                arguments = {"_raw": raw_arguments}
                            tool_calls.append(
                                ToolCall(
                                    id=tool_call.get("id", ""),
                                    name=function.get("name", ""),
                                    arguments=arguments or {},
                                    index=index,
                                )
                            )
                            if on_tool_delta:
                                should_continue = on_tool_delta(
                                    {
                                        "index": index,
                                        "id": tool_call.get("id", ""),
                                        "name": function.get("name", ""),
                                        "arguments_length": len(
                                            raw_arguments
                                            if isinstance(raw_arguments, str)
                                            else json.dumps(
                                                raw_arguments, ensure_ascii=False
                                            )
                                        ),
                                    }
                                )
                                if should_continue is False:
                                    return {
                                        "content": content,
                                        "tool_calls": [],
                                        "finish_reason": "cancelled",
                                    }
                        return {
                            "content": content,
                            "tool_calls": tool_calls,
                            "finish_reason": result["choices"][0].get(
                                "finish_reason", "stop"
                            ),
                        }

                    for raw_line in response.iter_lines(
                        chunk_size=1, decode_unicode=False
                    ):
                        if not raw_line:
                            continue
                        # SSE is UTF-8 by specification. Do not trust Requests'
                        # ISO-8859-1 fallback when the provider omits charset.
                        line = (
                            raw_line.decode("utf-8-sig")
                            if isinstance(raw_line, bytes)
                            else str(raw_line)
                        ).strip()
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            event = json.loads(data)
                        except json.JSONDecodeError:
                            continue

                        choices = event.get("choices") or []
                        if not choices:
                            continue
                        choice = choices[0]
                        delta = choice.get("delta") or {}
                        reasoning_chunk = delta.get("reasoning_content") or ""
                        if reasoning_chunk:
                            emitted_content = True
                            if not reasoning_open:
                                reasoning_open = True
                                content_parts.append("<think>")
                                if on_content and on_content("<think>") is False:
                                    return {
                                        "content": "".join(content_parts),
                                        "tool_calls": [],
                                        "finish_reason": "cancelled",
                                    }
                            content_parts.append(reasoning_chunk)
                            if on_content and on_content(reasoning_chunk) is False:
                                return {
                                    "content": "".join(content_parts),
                                    "tool_calls": [],
                                    "finish_reason": "cancelled",
                                }

                        chunk = delta.get("content") or ""
                        if chunk:
                            if reasoning_open:
                                reasoning_open = False
                                content_parts.append("</think>\n")
                                if on_content and on_content("</think>\n") is False:
                                    return {
                                        "content": "".join(content_parts),
                                        "tool_calls": [],
                                        "finish_reason": "cancelled",
                                    }
                            emitted_content = True
                            content_parts.append(chunk)
                            if on_content and on_content(chunk) is False:
                                return {
                                    "content": "".join(content_parts),
                                    "tool_calls": [],
                                    "finish_reason": "cancelled",
                                }

                        for tool_delta in delta.get("tool_calls") or []:
                            index = int(tool_delta.get("index", 0))
                            current = streamed_tools.setdefault(
                                index, {"id": "", "name": "", "arguments": ""}
                            )
                            if tool_delta.get("id"):
                                current["id"] = tool_delta["id"]
                            function = tool_delta.get("function") or {}
                            current["name"] += function.get("name") or ""
                            current["arguments"] += function.get("arguments") or ""
                            if on_tool_delta:
                                should_continue = on_tool_delta(
                                    {
                                        "index": index,
                                        "id": current["id"],
                                        "name": current["name"],
                                        "arguments_length": len(current["arguments"]),
                                    }
                                )
                                if should_continue is False:
                                    return {
                                        "content": "".join(content_parts),
                                        "tool_calls": [],
                                        "finish_reason": "cancelled",
                                    }

                        if choice.get("finish_reason"):
                            finish_reason = choice["finish_reason"]

                if reasoning_open:
                    content_parts.append("</think>")
                    if on_content:
                        on_content("</think>")

                tool_calls = []
                for index in sorted(streamed_tools):
                    item = streamed_tools[index]
                    arguments: Dict[str, Any] = {}
                    if item["arguments"]:
                        try:
                            arguments = json.loads(item["arguments"])
                        except json.JSONDecodeError:
                            arguments = {"_raw": item["arguments"]}
                    tool_calls.append(
                        ToolCall(
                            id=item["id"],
                            name=item["name"],
                            arguments=arguments,
                            index=index,
                        )
                    )
                return {
                    "content": "".join(content_parts),
                    "tool_calls": tool_calls,
                    "finish_reason": finish_reason,
                }
            except requests.exceptions.RequestException as exc:
                if emitted_content or attempt >= max_retries - 1:
                    return {
                        "content": f"API Error: {str(exc)}",
                        "tool_calls": [],
                        "finish_reason": "error",
                    }
                import time

                time.sleep(retry_delay)
                retry_delay *= 2

    def call_messages(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Call the chat API without mutating the conversation history."""
        request_messages = list(messages)
        if system_prompt:
            request_messages = [{"role": "system", "content": system_prompt}] + request_messages
        return self._post_chat_completion(
            request_messages,
            tools=tools,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
            max_retries=max_retries,
        )

    def add_message(self, role: str, content: Any) -> None:
        """Add message to conversation history"""
        self.conversation_history.append({"role": role, "content": content})

    def add_tool_message(self, tool_call_id: str, content: str) -> None:
        """Add tool result message to conversation"""
        self.conversation_history.append(
            {"role": "tool", "tool_call_id": tool_call_id, "content": content}
        )

    def clear_history(self) -> None:
        """Clear conversation history"""
        self.conversation_history = []

    def truncate_web_results(self, max_length: int = 300) -> None:
        """Truncate web search and read_url results in conversation history to reduce token usage"""
        for msg in self.conversation_history:
            content = msg.get("content", "")
            if not isinstance(content, str):
                continue
            prefixes = ("执行 web_search:", "执行 websearch:", "执行 read_url:")
            prefix = next((p for p in prefixes if p in content), None)
            if prefix:
                idx = content.find(prefix)
                if idx >= 0:
                    before = content[:idx]
                    after = content[idx + len(prefix) :]
                    if len(after) > max_length:
                        after = after[:max_length] + "... [内容已截断以节省上下文]"
                    msg["content"] = before + prefix + after

    def get_history(self) -> List[Dict[str, Any]]:
        """Get conversation history in API format"""
        return self.conversation_history

    def call_api(
        self,
        user_message: Union[str, List[Dict[str, Any]]],
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Call AI API and get response with native tool support

        Returns:
            {
                "content": str,           # Text response
                "tool_calls": [],          # List of ToolCall objects
                "finish_reason": str,     # "stop", "tool_calls", or "length"
            }
        """
        # Add user message
        self.conversation_history.append({"role": "user", "content": user_message})
        messages = self.get_history()

        # Add system prompt if provided
        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}] + messages
        result = self._post_chat_completion(
            messages,
            tools=tools,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        if result["finish_reason"] == "error":
            error_msg = result["content"]
            self.conversation_history.append({"role": "assistant", "content": error_msg})
            return result

        content = result["content"]
        tool_calls = result["tool_calls"]
        finish_reason = result["finish_reason"]

        assistant_msg: Dict[str, Any] = {
            "role": "assistant",
            "content": content,
        }
        if tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                    },
                }
                for tc in tool_calls
            ]
        self.conversation_history.append(assistant_msg)

        return {
            "content": content,
            "tool_calls": tool_calls,
            "finish_reason": finish_reason,
        }

    def call_api_stream(
        self,
        user_message: Union[str, List[Dict[str, Any]]],
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        on_content: Optional[Callable[[str], Optional[bool]]] = None,
        on_tool_delta: Optional[Callable[[Dict[str, Any]], Optional[bool]]] = None,
    ) -> Dict[str, Any]:
        """Call the chat API while forwarding text deltas to a callback."""
        self.conversation_history.append({"role": "user", "content": user_message})
        messages = self.get_history()
        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}] + messages

        result = self._post_chat_completion_stream(
            messages,
            tools=tools,
            on_content=on_content,
            on_tool_delta=on_tool_delta,
        )
        if result["finish_reason"] == "cancelled":
            return result
        if result["finish_reason"] == "error":
            self.conversation_history.append(
                {"role": "assistant", "content": result["content"]}
            )
            return result

        assistant_msg: Dict[str, Any] = {
            "role": "assistant",
            "content": result["content"],
        }
        if result["tool_calls"]:
            assistant_msg["tool_calls"] = [
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.name,
                        "arguments": json.dumps(
                            tool_call.arguments, ensure_ascii=False
                        ),
                    },
                }
                for tool_call in result["tool_calls"]
            ]
        self.conversation_history.append(assistant_msg)
        return result

    def process_with_tools_stream(
        self,
        user_message: Union[str, List[Dict[str, Any]]],
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        on_content: Optional[Callable[[str], Optional[bool]]] = None,
        on_tool_delta: Optional[Callable[[Dict[str, Any]], Optional[bool]]] = None,
    ) -> Dict[str, Any]:
        """Process one model turn and expose text as it arrives."""
        result = self.call_api_stream(
            user_message,
            system_prompt=system_prompt,
            tools=tools,
            on_content=on_content,
            on_tool_delta=on_tool_delta,
        )
        return {
            "type": "tool_call" if result["tool_calls"] else "response",
            "content": result["content"],
            "tool_calls": result["tool_calls"],
            "finish_reason": result["finish_reason"],
        }

    def process_with_tools(
        self,
        user_message: Union[str, List[Dict[str, Any]]],
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Process message with tools - handles tool calls automatically

        Args:
            user_message: User input
            system_prompt: System prompt
            tools: Tool definitions in OpenAI format

        Returns:
            {
                "type": "response" | "tool_call",
                "content": str,           # Final text response
                "tool_calls": [],         # Tool calls to execute
                "tool_results": [],       # Tool execution results (if auto-execute)
            }
        """
        result = self.call_api(user_message, system_prompt, tools)

        # Check if there are tool calls
        if result["tool_calls"]:
            return {
                "type": "tool_call",
                "content": result["content"],
                "tool_calls": result["tool_calls"],
                "finish_reason": result["finish_reason"],
            }

        # No tool calls, return content
        return {
            "type": "response",
            "content": result["content"],
            "tool_calls": [],
            "finish_reason": result["finish_reason"],
        }
