"""JC-Chat mode: simple tool-free chat turns."""

from __future__ import annotations

import base64
import os
import time

from agent.core.conversation_store import ConversationStore
from agent.core.extended_tool_executor import ExtendedToolExecutor
from agent.core.memory_manager import MemoryManager
from agent.ui.desktop import main as desktop

PNG_BYTES = b"\x89PNG\r\n\x1a\nimage-data"


def _image_data_url() -> str:
    return "data:image/png;base64," + base64.b64encode(PNG_BYTES).decode("ascii")


class _DataIntegrator:
    def start_task(self, _request: str) -> str:
        return "test-task"

    def end_task(self, _status: str) -> None:
        return None

    def ingest_tool_result(self, **_kwargs) -> None:
        return None


class _FakeAIEngine:
    """Stands in for AIEngine with a scripted streaming completion."""

    def __init__(self) -> None:
        self.messages: list[dict] = []
        self.tools = "unset"
        self.final_content = "你好，我是 JC-Chat。"

    def clear_history(self) -> None:
        return None

    def _post_chat_completion_stream(
        self, messages, tools=None, on_content=None, **_kwargs
    ):
        self.messages = list(messages)
        self.tools = tools
        for chunk in ("你好", "，", "我是 JC-Chat。"):
            if on_content and on_content(chunk) is False:
                return {
                    "content": "".join(("你好", "，", "我是 JC-Chat。")),
                    "tool_calls": [],
                    "finish_reason": "cancelled",
                }
        return {
            "content": self.final_content,
            "tool_calls": [],
            "finish_reason": "stop",
        }


def _install(monkeypatch, tmp_path, name: str = "jcchat"):
    # 自定义系统提示词来自环境变量，测试不应依赖开发者本机的 .env 残留值
    monkeypatch.delenv("CUSTOM_SYSTEM_PROMPT", raising=False)
    store = ConversationStore(tmp_path / "conversations")
    conversation = store.create(name)
    executor = desktop.DesktopTaskExecutor()
    executor.conversation_id = conversation["id"]
    executor.memory_manager = MemoryManager(str(store.memory_dir(conversation["id"])))
    executor.data_integrator = _DataIntegrator()
    executor.ai_engine = _FakeAIEngine()
    executor.tool_executor = ExtendedToolExecutor(preview_manager=object())
    executor.compress_at = 999999
    monkeypatch.setattr(desktop.runtime, "conversation_store", store)
    desktop.runtime.conversation_runs.clear()
    desktop.runtime.conversation_executors.clear()
    desktop.runtime.conversation_generations.clear()
    desktop.runtime.conversation_executors[conversation["id"]] = executor
    return store, conversation, executor


def _wait_for_finish(conversation_id: str, message_id: int) -> None:
    for _ in range(300):
        if not desktop.get_execution_status(conversation_id, message_id)["running"]:
            return
        time.sleep(0.01)
    raise AssertionError("JC-Chat turn did not finish")


def test_jcchat_runs_tool_free_chat_turn(monkeypatch, tmp_path) -> None:
    store, conversation, executor = _install(monkeypatch, tmp_path)
    message_id = 401

    result = desktop.send_message(
        "你好",
        message_id=message_id,
        conversation_id=conversation["id"],
        mode="jcchat",
    )

    assert result == {"status": "processing"}
    assert desktop.runtime.conversation_runs[conversation["id"]].mode == "jcchat"
    _wait_for_finish(conversation["id"], message_id)

    engine = executor.ai_engine
    assert engine.tools is None
    assert engine.messages[0]["role"] == "system"
    assert "JC-Chat" in engine.messages[0]["content"]
    assert engine.messages[-1] == {"role": "user", "content": "你好"}
    assert "联网搜索" not in engine.messages[0]["content"]
    assert "调用" not in engine.messages[0]["content"]

    persisted = store.load(conversation["id"])["messages"]
    assistant = [message for message in persisted if message.get("type") == "assistant"]
    assert assistant and assistant[-1]["content"] == "你好，我是 JC-Chat。"


def test_jcchat_mode_is_isolated_from_jcodex_mode(monkeypatch, tmp_path) -> None:
    store, conversation, executor = _install(monkeypatch, tmp_path, "jcodex default")
    message_id = 402

    result = desktop.send_message(
        "普通任务",
        message_id=message_id,
        conversation_id=conversation["id"],
    )

    assert result == {"status": "processing"}
    assert desktop.runtime.conversation_runs[conversation["id"]].mode == "jcodex"
    _wait_for_finish(conversation["id"], message_id)

    engine = executor.ai_engine
    assert engine.messages == []  # jcodex path never touched the fake chat engine
    assert store.load(conversation["id"])["messages"]


def test_jcchat_token_count_reports_system_and_message_tokens(
    monkeypatch, tmp_path
) -> None:
    _store, conversation, _executor = _install(monkeypatch, tmp_path)
    message_id = 403

    result = desktop.send_message(
        "你好",
        message_id=message_id,
        conversation_id=conversation["id"],
        mode="jcchat",
    )
    assert result == {"status": "processing"}
    _wait_for_finish(conversation["id"], message_id)

    usage = desktop.get_token_count(conversation["id"])
    assert usage["source"] == "jcchat"
    assert usage["system_tokens"] > 0
    assert usage["message_tokens"] > 0
    assert usage["tool_tokens"] == 0
    assert usage["tokens"] == usage["system_tokens"] + usage["message_tokens"]
    assert usage["compress_at"] > 0
    assert usage["max_tokens"] > 0


def test_jcchat_writes_chat_content_to_execution_history(
    monkeypatch, tmp_path
) -> None:
    _store, conversation, executor = _install(monkeypatch, tmp_path)
    message_id = 404

    result = desktop.send_message(
        "你好，请记住这句话",
        message_id=message_id,
        conversation_id=conversation["id"],
        mode="jcchat",
    )
    assert result == {"status": "processing"}
    _wait_for_finish(conversation["id"], message_id)

    history = executor.memory_manager.load_execution_history()
    assert any("【用户请求】你好，请记住这句话" in line for line in history)
    assert any("最终回应: 你好，我是 JC-Chat。" in line for line in history)


def test_jcchat_includes_compressed_summary_in_system_prompt(
    monkeypatch, tmp_path
) -> None:
    _store, conversation, executor = _install(monkeypatch, tmp_path)
    executor.accumulated_compression = "压缩摘要：用户之前问过天气。"
    message_id = 405

    result = desktop.send_message(
        "继续",
        message_id=message_id,
        conversation_id=conversation["id"],
        mode="jcchat",
    )
    assert result == {"status": "processing"}
    _wait_for_finish(conversation["id"], message_id)

    engine = executor.ai_engine
    assert "压缩摘要：用户之前问过天气。" in engine.messages[0]["content"]
    assert engine.messages[0]["content"].startswith(
        desktop.JC_CHAT_SYSTEM_PROMPT
    )


def test_jcchat_uses_custom_system_prompt(monkeypatch, tmp_path) -> None:
    _store, conversation, executor = _install(monkeypatch, tmp_path)
    message_id = 406
    previous = os.environ.get("CUSTOM_SYSTEM_PROMPT")
    try:
        os.environ["CUSTOM_SYSTEM_PROMPT"] = "你是翻译助手，只输出译文。"
        result = desktop.send_message(
            "hello",
            message_id=message_id,
            conversation_id=conversation["id"],
            mode="jcchat",
        )
        assert result == {"status": "processing"}
        _wait_for_finish(conversation["id"], message_id)
    finally:
        if previous is None:
            os.environ.pop("CUSTOM_SYSTEM_PROMPT", None)
        else:
            os.environ["CUSTOM_SYSTEM_PROMPT"] = previous

    engine = executor.ai_engine
    assert engine.messages[0]["content"] == "你是翻译助手，只输出译文。"


def test_jcchat_image_attachment_embeds_multimodal_content(
    monkeypatch, tmp_path
) -> None:
    _store, conversation, executor = _install(monkeypatch, tmp_path)
    message_id = 407
    previous = os.environ.get("MODEL_SUPPORTS_VISION")
    try:
        os.environ["MODEL_SUPPORTS_VISION"] = "true"
        result = desktop.send_message(
            "请描述这张图",
            message_id=message_id,
            conversation_id=conversation["id"],
            mode="jcchat",
            attachments=[
                {
                    "name": "desktop.png",
                    "type": "image/png",
                    "size": len(PNG_BYTES),
                    "data": _image_data_url(),
                }
            ],
        )
        assert result == {"status": "processing"}
        _wait_for_finish(conversation["id"], message_id)
    finally:
        if previous is None:
            os.environ.pop("MODEL_SUPPORTS_VISION", None)
        else:
            os.environ["MODEL_SUPPORTS_VISION"] = previous

    engine = executor.ai_engine
    assert engine.tools is None
    content = engine.messages[-1]["content"]
    assert isinstance(content, list)
    assert any(
        block.get("type") == "image_url"
        and str(block.get("image_url", {}).get("url", "")).startswith(
            "data:image/png;base64,"
        )
        for block in content
    )
    assert any(
        block.get("type") == "text"
        and "请描述这张图" in str(block.get("text", ""))
        for block in content
    )
    assert "必须调用 view_image" not in str(content)


def test_jcchat_image_attachment_with_vision_off_has_no_tools(
    monkeypatch, tmp_path
) -> None:
    _store, conversation, executor = _install(monkeypatch, tmp_path)
    message_id = 408
    previous = os.environ.get("MODEL_SUPPORTS_VISION")
    try:
        os.environ["MODEL_SUPPORTS_VISION"] = "false"
        result = desktop.send_message(
            "请描述这张图",
            message_id=message_id,
            conversation_id=conversation["id"],
            mode="jcchat",
            attachments=[
                {
                    "name": "desktop.png",
                    "type": "image/png",
                    "size": len(PNG_BYTES),
                    "data": _image_data_url(),
                }
            ],
        )
        assert result == {"status": "processing"}
        _wait_for_finish(conversation["id"], message_id)
    finally:
        if previous is None:
            os.environ.pop("MODEL_SUPPORTS_VISION", None)
        else:
            os.environ["MODEL_SUPPORTS_VISION"] = previous

    engine = executor.ai_engine
    assert engine.tools is None
    assert isinstance(engine.messages[-1]["content"], str)
    assert "必须调用 view_image" not in engine.messages[-1]["content"]


def test_jcchat_text_file_attachment_is_parsed_into_message(
    monkeypatch, tmp_path
) -> None:
    _store, conversation, executor = _install(monkeypatch, tmp_path)
    monkeypatch.setattr(desktop.constants, "DATA_ROOT", tmp_path)
    message_id = 409

    result = desktop.send_message(
        "请阅读这个文件",
        message_id=message_id,
        conversation_id=conversation["id"],
        mode="jcchat",
        attachments=[
            {
                "name": "notes.txt",
                "type": "text/plain",
                "size": len(b"hello jcchat"),
                "data": "data:text/plain;base64,"
                + base64.b64encode(b"hello jcchat").decode("ascii"),
            }
        ],
    )
    assert result == {"status": "processing"}
    _wait_for_finish(conversation["id"], message_id)

    engine = executor.ai_engine
    assert engine.tools is None
    assert "hello jcchat" in engine.messages[-1]["content"]
    assert "以下附件已通过 Read 工具解析" in engine.messages[-1]["content"]
