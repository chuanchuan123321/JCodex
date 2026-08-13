"""LangChain chat model backed by the project's OpenAI-compatible AIEngine."""

from __future__ import annotations

import json
import queue
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager, suppress
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    convert_to_openai_messages,
)
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import ConfigDict, Field, PrivateAttr

from agent.core.ai_engine import AIEngine, ToolCall


class AIEngineChatModel(BaseChatModel):
    """Expose :class:`AIEngine` as a LangChain ``BaseChatModel``.

    This adapter deliberately delegates transport to ``AIEngine`` instead of
    replacing it with ``ChatOpenAI``. Several configured providers rely on the
    existing URL selection and SSE reasoning parsing behavior.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    model_name: str = ""
    max_tokens: int | None = None
    temperature: float | None = None
    streaming: bool = True
    bound_tools: list[dict[str, Any]] = Field(default_factory=list)
    tool_choice: Any = None
    parallel_tool_calls: bool | None = False

    _engine: AIEngine = PrivateAttr()
    _stream_local: threading.local = PrivateAttr()

    def __init__(self, engine: AIEngine | None = None, **data: Any) -> None:
        resolved_engine = engine or AIEngine()
        data.setdefault("model_name", resolved_engine.model)
        data.setdefault("max_tokens", resolved_engine.max_tokens)
        data.setdefault("temperature", resolved_engine.temperature)
        super().__init__(**data)
        self._engine = resolved_engine
        self._stream_local = threading.local()

    @contextmanager
    def cancellation_scope(self, checker):
        """Propagate a Runner cancellation predicate into the SSE callbacks."""
        previous = getattr(self._stream_local, "checker", None)
        self._stream_local.checker = checker
        try:
            yield
        finally:
            if previous is None:
                with suppress(AttributeError):
                    del self._stream_local.checker
            else:
                self._stream_local.checker = previous

    @property
    def _llm_type(self) -> str:
        return "os-agent-openai-compatible"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "api_base_url": self._engine.api_base_url,
        }

    @property
    def engine(self) -> AIEngine:
        """Return the transport engine used by this model."""
        return self._engine

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Any | BaseTool],
        *,
        tool_choice: dict[str, Any] | str | bool | None = None,
        strict: bool | None = None,
        parallel_tool_calls: bool | None = False,
        **kwargs: Any,
    ) -> Runnable[Any, AIMessage]:
        """Bind tools using the same OpenAI function schema AIEngine accepts."""
        formatted_tools = [convert_to_openai_tool(tool, strict=strict) for tool in tools]
        bind_kwargs: dict[str, Any] = {"tools": formatted_tools}
        if tool_choice is not None:
            bind_kwargs["tool_choice"] = tool_choice
        if parallel_tool_calls is not None:
            bind_kwargs["parallel_tool_calls"] = parallel_tool_calls
        bind_kwargs.update(kwargs)
        return self.bind(**bind_kwargs)

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        del run_manager
        result = self._engine.call_messages(
            self._to_provider_messages(messages),
            tools=self._resolve_tools(kwargs),
            max_tokens=self._resolve_max_tokens(kwargs),
            temperature=self._resolve_temperature(kwargs),
        )
        message = self._to_ai_message(result)
        return ChatResult(
            generations=[
                ChatGeneration(
                    message=message,
                    generation_info={
                        "finish_reason": result.get("finish_reason", "stop")
                    },
                )
            ],
            llm_output={"model_name": self.model_name},
        )

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        del run_manager
        in_reasoning = False
        pending_text = ""
        events: queue.Queue[tuple[str, Any]] = queue.Queue()
        stream_checker = getattr(self._stream_local, "checker", None)

        def stream_cancelled() -> bool:
            try:
                return bool(stream_checker and stream_checker())
            except Exception:
                return False

        def queue_text(text: str) -> None:
            if not text:
                return
            if in_reasoning:
                events.put((
                    "chunk",
                    ChatGenerationChunk(
                        message=AIMessageChunk(
                            content="",
                            additional_kwargs={"reasoning_content": text},
                        )
                    )
                ))
            else:
                events.put((
                    "chunk",
                    ChatGenerationChunk(message=AIMessageChunk(content=text))
                ))

        def marker_suffix_length(value: str, marker: str) -> int:
            max_length = min(len(value), len(marker) - 1)
            for length in range(max_length, 0, -1):
                if marker.startswith(value[-length:]):
                    return length
            return 0

        def emit_text(chunk: str) -> bool:
            nonlocal in_reasoning, pending_text
            if stream_cancelled():
                return False
            if not chunk:
                return True
            pending_text += chunk
            while pending_text:
                marker = "</think>" if in_reasoning else "<think>"
                marker_index = pending_text.find(marker)
                if marker_index >= 0:
                    queue_text(pending_text[:marker_index])
                    pending_text = pending_text[marker_index + len(marker) :]
                    in_reasoning = not in_reasoning
                    continue
                keep_length = marker_suffix_length(pending_text, marker)
                emit_length = len(pending_text) - keep_length
                if emit_length:
                    queue_text(pending_text[:emit_length])
                    pending_text = pending_text[emit_length:]
                break
            return True

        def emit_tool(delta: dict[str, Any]) -> bool:
            if stream_cancelled():
                return False
            index = int(delta.get("index", 0) or 0)
            tool_id = str(delta.get("id") or "")
            tool_name = str(delta.get("name") or "")
            argument_length = int(delta.get("arguments_length", 0) or 0)
            events.put((
                "chunk",
                ChatGenerationChunk(
                    message=AIMessageChunk(
                        content="",
                        additional_kwargs={
                            "tool_delta": {
                                "index": index,
                                "id": tool_id,
                                "name": tool_name,
                                "arguments_length": argument_length,
                            }
                        },
                    )
                )
            ))
            return True

        stream_request = self._engine._post_chat_completion_stream

        result_holder: dict[str, Any] = {}

        def produce() -> None:
            nonlocal pending_text
            try:
                result_holder["result"] = stream_request(
                    self._to_provider_messages(messages),
                    tools=self._resolve_tools(kwargs),
                    max_tokens=self._resolve_max_tokens(kwargs),
                    temperature=self._resolve_temperature(kwargs),
                    on_content=emit_text,
                    on_tool_delta=emit_tool,
                )
            except BaseException as exc:
                result_holder["error"] = exc
            finally:
                if pending_text and not stream_cancelled():
                    queue_text(pending_text)
                    pending_text = ""
                events.put(("done", None))

        producer = threading.Thread(target=produce, daemon=True)
        producer.start()
        emitted_any = False
        while True:
            if stream_cancelled():
                return
            try:
                event_type, value = events.get(timeout=0.05)
            except queue.Empty:
                continue
            if stream_cancelled():
                return
            if event_type == "done":
                break
            emitted_any = True
            yield value
        if "error" in result_holder:
            raise result_holder["error"]
        result = result_holder.get("result") or {}

        if stream_cancelled() or result.get("finish_reason") == "cancelled":
            return
        if result.get("finish_reason") == "error":
            raise RuntimeError(result.get("content") or "AI service returned an error")

        streamed_calls = list(result.get("tool_calls") or [])
        if streamed_calls:
            yield ChatGenerationChunk(
                message=AIMessageChunk(
                    content="",
                    tool_call_chunks=[
                        {
                            "name": call.name,
                            "args": json.dumps(call.arguments, ensure_ascii=False),
                            "id": call.id,
                            "index": call.index,
                            "type": "tool_call_chunk",
                        }
                        for call in streamed_calls
                    ],
                ),
                generation_info={
                    "finish_reason": result.get("finish_reason", "tool_calls")
                },
            )
        elif not emitted_any and result.get("content"):
            # Non-SSE providers may only produce a complete response.
            yield ChatGenerationChunk(
                message=AIMessageChunk(content=str(result["content"])),
                generation_info={"finish_reason": result.get("finish_reason", "stop")},
            )

    @staticmethod
    def _to_provider_messages(messages: list[BaseMessage]) -> list[dict[str, Any]]:
        converted = convert_to_openai_messages(
            messages, pass_through_unknown_blocks=True
        )
        return list(converted) if isinstance(converted, list) else [converted]

    def _resolve_tools(self, kwargs: dict[str, Any]) -> list[dict[str, Any]]:
        tools = kwargs.get("tools", kwargs.get("bound_tools", self.bound_tools))
        return list(tools or [])

    def _resolve_max_tokens(self, kwargs: dict[str, Any]) -> int | None:
        value = kwargs.get("max_tokens", kwargs.get("max_completion_tokens"))
        return self.max_tokens if value is None else int(value)

    def _resolve_temperature(self, kwargs: dict[str, Any]) -> float | None:
        value = kwargs.get("temperature")
        return self.temperature if value is None else float(value)

    @staticmethod
    def _to_ai_message(result: dict[str, Any]) -> AIMessage:
        content = str(result.get("content", "") or "")
        tool_calls = [
            {
                "name": call.name,
                "args": dict(call.arguments or {}),
                "id": call.id,
                "type": "tool_call",
            }
            for call in result.get("tool_calls") or []
            if isinstance(call, ToolCall)
        ]
        return AIMessage(
            content=content,
            tool_calls=tool_calls,
            response_metadata={
                "finish_reason": result.get("finish_reason", "stop")
            },
        )
