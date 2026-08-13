"""AI Agent Core Engine - Native function calling support"""

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

from agent.core.env_utils import env_float, env_int

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=True)


@dataclass
class ToolCall:
    """Represents a tool call from the LLM"""

    id: str
    name: str
    arguments: dict[str, Any]
    index: int = 0


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

    def __init__(self, config_name: str | None = None):
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

        if not self.api_key and not self.is_local_base_url(self.api_base_url):
            raise ValueError("API_KEY not found in environment variables")

        self.conversation_history: list[dict[str, Any]] = []

    def _apply_reasoning_params(self, payload: dict[str, Any]) -> None:
        """DeepSeek 系列模型：按配置注入推理强度参数（其余模型不注入）。"""
        effort = (self.reasoning_effort or "").strip()
        model = (self.model or "").lower()
        if not effort or "deepseek" not in model:
            return
        payload["reasoning_effort"] = effort
        payload["thinking"] = {"type": "enabled"}

    def _post_chat_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> dict[str, Any]:
        """Send a chat-completions request using the current model settings."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload: dict[str, Any] = {
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
                        f"[API] 请求失败，{retry_delay}秒后重试 ({attempt + 1}/{retries}): {e!s}"
                    )
                    import time

                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    return {
                        "content": f"API Error: {e!s}",
                        "tool_calls": [],
                        "finish_reason": "error",
                    }

        # Unreachable: every retry attempt returns above.
        return {
            "content": "API Error: request failed",
            "tool_calls": [],
            "finish_reason": "error",
        }

    def _post_chat_completion_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        on_content: Callable[[str], bool | None] | None = None,
        on_tool_delta: Callable[[dict[str, Any]], bool | None] | None = None,
    ) -> dict[str, Any]:
        """Send a streaming chat request and assemble the final message."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload: dict[str, Any] = {
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
            content_parts: list[str] = []
            streamed_tools: dict[int, dict[str, str]] = {}
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
                    arguments: dict[str, Any] = {}
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
                        "content": f"API Error: {exc!s}",
                        "tool_calls": [],
                        "finish_reason": "error",
                    }
                import time

                time.sleep(retry_delay)
                retry_delay *= 2

        # Unreachable: every retry attempt returns above.
        return {
            "content": "API Error: stream failed",
            "tool_calls": [],
            "finish_reason": "error",
        }

    def call_messages(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> dict[str, Any]:
        """Call the chat API without mutating the conversation history."""
        request_messages = list(messages)
        if system_prompt:
            request_messages = [
                {"role": "system", "content": system_prompt},
                *request_messages,
            ]
        return self._post_chat_completion(
            request_messages,
            tools=tools,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
            max_retries=max_retries,
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

    def get_history(self) -> list[dict[str, Any]]:
        """Get conversation history in API format"""
        return self.conversation_history

