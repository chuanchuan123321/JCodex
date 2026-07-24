"""Regressions for task-scoped image attachment viewing."""

from __future__ import annotations

import base64
import json
import re
import time
from pathlib import Path

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessageChunk, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGenerationChunk
from pydantic import Field

from agent.core.conversation_store import ConversationStore
from agent.core.extended_tool_executor import ExtendedToolExecutor
from agent.core.langgraph_runner import LangGraphRunner
from agent.core.memory_manager import MemoryManager
from agent.core.tool_result import ToolExecutionResult
from agent.ui.desktop import main as desktop


PNG_BYTES = b"\x89PNG\r\n\x1a\nimage-data"


def _image_data_url() -> str:
    return "data:image/png;base64," + base64.b64encode(PNG_BYTES).decode("ascii")


def _tool_definition(name: str) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": name,
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    }


class _ImageToolModel(BaseChatModel):
    turn: int = 0
    seen_messages: list[list] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "task-image-test"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, **kwargs):
        raise NotImplementedError

    def _stream(self, messages, **kwargs):
        self.seen_messages.append(list(messages))
        if self.turn == 0:
            self.turn += 1
            yield ChatGenerationChunk(
                message=AIMessageChunk(
                    content="",
                    tool_call_chunks=[
                        {
                            "name": "view_image",
                            "args": '{"path":"/task/current.png"}',
                            "id": "image-1",
                            "index": 0,
                            "type": "tool_call_chunk",
                        }
                    ],
                )
            )
            return
        self.turn += 1
        yield ChatGenerationChunk(message=AIMessageChunk(content="图片已查看"))


class _ManifestImageModel(BaseChatModel):
    turn: int = 0
    seen_messages: list[list] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "desktop-task-image-test"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, **kwargs):
        raise NotImplementedError

    def _stream(self, messages, **kwargs):
        self.seen_messages.append(list(messages))
        if self.turn == 0:
            self.turn += 1
            user_text = "\n".join(
                str(message.content)
                for message in messages
                if isinstance(message, HumanMessage)
            )
            path_match = re.search(r"^- (/.+\.png)$", user_text, flags=re.M)
            assert path_match is not None
            yield ChatGenerationChunk(
                message=AIMessageChunk(
                    content="",
                    tool_call_chunks=[
                        {
                            "name": "view_image",
                            "args": json.dumps({"path": path_match.group(1)}),
                            "id": "desktop-image-1",
                            "index": 0,
                            "type": "tool_call_chunk",
                        }
                    ],
                )
            )
            return
        self.turn += 1
        yield ChatGenerationChunk(message=AIMessageChunk(content="已基于图片完成"))


class _RepeatedManifestImageModel(_ManifestImageModel):
    """Request the same task image twice before producing a final answer."""

    def _stream(self, messages, **kwargs):
        self.seen_messages.append(list(messages))
        if self.turn < 2:
            self.turn += 1
            user_text = "\n".join(
                str(message.content)
                for message in messages
                if isinstance(message, HumanMessage)
            )
            path_match = re.search(r"^- (/.+\.png)$", user_text, flags=re.M)
            assert path_match is not None
            yield ChatGenerationChunk(
                message=AIMessageChunk(
                    content="",
                    tool_call_chunks=[
                        {
                            "name": "view_image",
                            "args": json.dumps({"path": path_match.group(1)}),
                            "id": f"desktop-image-{self.turn}",
                            "index": 0,
                            "type": "tool_call_chunk",
                        }
                    ],
                )
            )
            return
        self.turn += 1
        yield ChatGenerationChunk(message=AIMessageChunk(content="已重复查看图片"))


class _FollowUpImageModel(_ManifestImageModel):
    """View a conversation image once per submitted task."""

    def _stream(self, messages, **kwargs):
        self.seen_messages.append(list(messages))
        if self.turn % 2 == 0:
            self.turn += 1
            user_text = "\n".join(
                str(message.content)
                for message in messages
                if isinstance(message, HumanMessage)
            )
            path_match = re.search(r"^- (/.+\.png)$", user_text, flags=re.M)
            assert path_match is not None
            yield ChatGenerationChunk(
                message=AIMessageChunk(
                    content="",
                    tool_call_chunks=[
                        {
                            "name": "view_image",
                            "args": json.dumps({"path": path_match.group(1)}),
                            "id": f"follow-up-image-{self.turn}",
                            "index": 0,
                            "type": "tool_call_chunk",
                        }
                    ],
                )
            )
            return
        self.turn += 1
        yield ChatGenerationChunk(message=AIMessageChunk(content="图片已查看"))


class _DataIntegrator:
    def start_task(self, _request: str) -> str:
        return "test-task"

    def end_task(self, _status: str) -> None:
        return None

    def ingest_tool_result(self, **_kwargs) -> None:
        return None


def test_image_attachment_is_saved_and_represented_by_a_path(monkeypatch, tmp_path) -> None:
    store = ConversationStore(tmp_path / "conversations")
    conversation = store.create("images")
    monkeypatch.setattr(desktop, "conversation_store", store)

    context, metadata, reads, task_images = desktop._prepare_attachments(
        [
            {
                "name": "screen.png",
                "type": "image/png",
                "data": _image_data_url(),
            }
        ],
        101,
        conversation["id"],
        lambda *_args: "unexpected read",
    )

    assert context == ""
    assert reads == []
    assert len(metadata) == len(task_images) == 1
    record = metadata[0]
    assert record["parse_mode"] == "image_view"
    assert Path(record["path"]).is_file()
    assert Path(record["path"]).read_bytes() == PNG_BYTES
    assert record["path"] == str(
        store.attachment_path(conversation["id"], record["asset_id"])
    )
    assert "data:image" not in json.dumps(metadata)


def test_directory_reference_is_validated_without_copying_contents(
    monkeypatch, tmp_path
) -> None:
    store = ConversationStore(tmp_path / "conversations")
    conversation = store.create("folder reference")
    reference = tmp_path / "reference-project"
    reference.mkdir()
    (reference / "README.md").write_text("reference", encoding="utf-8")
    monkeypatch.setattr(desktop, "conversation_store", store)

    context, metadata, reads, task_images = desktop._prepare_attachments(
        [
            {
                "name": reference.name,
                "path": str(reference),
                "kind": "directory_reference",
            }
        ],
        102,
        conversation["id"],
        lambda *_args: "unexpected read",
    )

    assert context == ""
    assert reads == []
    assert task_images == []
    assert metadata == [
        {
            "name": reference.name,
            "size": 0,
            "type": "inode/directory",
            "path": str(reference),
            "success": True,
            "error": "",
            "parse_mode": "directory_reference",
            "kind": "directory_reference",
        }
    ]


def test_task_reference_folder_allows_normal_local_tool_permissions(tmp_path) -> None:
    project_root = tmp_path / "primary"
    reference = tmp_path / "reference"
    project_root.mkdir()
    reference.mkdir()
    nested = reference / "src"
    nested.mkdir()
    target = nested / "sample.py"
    target.write_text("REFERENCE_TOKEN = 1\n", encoding="utf-8")
    executor = ExtendedToolExecutor(
        project_root=str(project_root),
        workspace_root=str(project_root / "workspace"),
        preview_manager=object(),
        restrict_reads_to_project=True,
    )
    executor.register_task_reference_roots("conversation-a", 103, [str(reference)])

    read_result = executor.execute(
        {"tool": "read", "params": {"path": str(target)}},
        conversation_id="conversation-a",
        message_id=103,
    )
    grep_result = executor.execute(
        {
            "tool": "grep",
            "params": {"pattern": "REFERENCE_TOKEN", "path": str(reference)},
        },
        conversation_id="conversation-a",
        message_id=103,
    )
    glob_result = executor.execute(
        {
            "tool": "glob",
            "params": {"pattern": "**/*.py", "path": str(reference)},
        },
        conversation_id="conversation-a",
        message_id=103,
    )
    write_result = executor.execute(
        {
            "tool": "write",
            "params": {"path": str(reference / "editable.txt"), "content": "before"},
        },
        conversation_id="conversation-a",
        message_id=103,
    )
    edit_result = executor.execute(
        {
            "tool": "edit",
            "params": {
                "filePath": str(reference / "editable.txt"),
                "oldString": "before",
                "newString": "after",
            },
        },
        conversation_id="conversation-a",
        message_id=103,
    )
    shell_result = executor.execute(
        {
            "tool": "bash",
            "params": {"command": "pwd", "workdir": str(reference)},
        },
        conversation_id="conversation-a",
        message_id=103,
    )

    assert "REFERENCE_TOKEN" in read_result
    assert "sample.py" in grep_result
    assert glob_result == "src/sample.py"
    assert write_result.startswith("File written")
    assert "Edit applied successfully" in edit_result
    assert (reference / "editable.txt").read_text(encoding="utf-8") == "after"
    assert str(reference) in shell_result
    executor.clear_task_reference_roots("conversation-a", 103)
    assert executor._task_reference_root_for_path(
        target, "conversation-a", 103
    ) is None


def test_view_image_only_allows_the_current_task_attachment(tmp_path) -> None:
    image_path = tmp_path / "image.png"
    image_path.write_bytes(PNG_BYTES)
    executor = ExtendedToolExecutor(preview_manager=object())
    executor.register_task_images(
        "conversation-a",
        201,
        [
            {
                "name": "image.png",
                "path": str(image_path),
                "size": len(PNG_BYTES),
                "type": "image/png",
            }
        ],
    )

    result = executor.execute(
        {"tool": "view_image", "params": {"path": str(image_path)}},
        conversation_id="conversation-a",
        message_id=201,
    )

    assert isinstance(result, ToolExecutionResult)
    assert str(image_path) in result.content
    assert "data:image" not in result.content
    assert result.model_inputs[0]["image_url"]["url"] == _image_data_url()
    image_tool = next(
        tool["function"]
        for tool in executor.get_available_tools()
        if tool.get("function", {}).get("name") == "view_image"
    )
    assert image_tool["parameters"]["required"] == ["path"]
    assert executor.execute(
        {"tool": "view_image", "params": {"path": str(image_path)}},
        conversation_id="conversation-a",
        message_id=202,
    ).startswith("Error:")
    assert executor.execute(
        {"tool": "view_image", "params": {"path": str(tmp_path / 'other.png')}},
        conversation_id="conversation-a",
        message_id=201,
    ).startswith("Error:")

    executor.clear_task_images("conversation-a", 201)
    assert executor.execute(
        {"tool": "view_image", "params": {"path": str(image_path)}},
        conversation_id="conversation-a",
        message_id=201,
    ).startswith("Error:")


def test_view_image_allows_supported_images_inside_workspace_temp_and_output(
    tmp_path,
) -> None:
    project_root = tmp_path / "project"
    temp_image = project_root / "workspace" / "temp" / "render" / "chart.png"
    temp_image.parent.mkdir(parents=True)
    temp_image.write_bytes(PNG_BYTES)
    output_image = project_root / "workspace" / "output" / "render" / "chart.png"
    output_image.parent.mkdir(parents=True)
    output_image.write_bytes(PNG_BYTES)
    outside_image = project_root / "workspace" / "private" / "chart.png"
    outside_image.parent.mkdir(parents=True)
    outside_image.write_bytes(PNG_BYTES)

    executor = ExtendedToolExecutor(
        preview_manager=object(), project_root=project_root
    )
    result = executor.execute(
        {"tool": "view_image", "params": {"path": str(temp_image)}},
        conversation_id="conversation-a",
        message_id=201,
    )

    assert isinstance(result, ToolExecutionResult)
    assert str(temp_image) in result.content
    assert "workspace temp image" in result.content
    assert result.model_inputs[0]["image_url"]["url"] == _image_data_url()
    output_result = executor.execute(
        {"tool": "view_image", "params": {"path": str(output_image)}},
        conversation_id="conversation-a",
        message_id=201,
    )
    assert isinstance(output_result, ToolExecutionResult)
    assert str(output_image) in output_result.content
    assert "workspace output image" in output_result.content
    assert output_result.model_inputs[0]["image_url"]["url"] == _image_data_url()
    assert executor.execute(
        {"tool": "view_image", "params": {"path": str(outside_image)}},
        conversation_id="conversation-a",
        message_id=201,
    ).startswith("Error:")


def test_image_tool_input_is_transient_not_checkpointed() -> None:
    data_url = _image_data_url()
    model = _ImageToolModel()
    events = []
    runner = LangGraphRunner(
        model,
        [_tool_definition("view_image")],
        lambda *_args: ToolExecutionResult(
            content="Loaded current-task image attachment: /task/current.png.",
            model_inputs=[{"type": "image_url", "image_url": {"url": data_url}}],
        ),
    )

    result = runner.run("image-task", "inspect image", emit=events.append)
    snapshot = runner.graph.get_state(
        {"configurable": {"thread_id": "image-task"}}
    )

    assert result.status == "complete"
    second_turn = model.seen_messages[1]
    transient_message = next(
        message
        for message in second_turn
        if isinstance(message, HumanMessage) and isinstance(message.content, list)
    )
    assert transient_message.content[-1]["image_url"]["url"] == data_url
    assert any(
        isinstance(message, ToolMessage)
        and message.content == "Loaded current-task image attachment: /task/current.png."
        for message in snapshot.values["messages"]
    )
    assert data_url not in str(snapshot.values["messages"])
    assert data_url not in str(events)


def test_desktop_image_submission_passes_path_then_viewed_image(
    monkeypatch, tmp_path
) -> None:
    store = ConversationStore(tmp_path / "conversations")
    conversation = store.create("desktop images")
    model = _ManifestImageModel()
    executor = desktop.DesktopTaskExecutor()
    executor.conversation_id = conversation["id"]
    executor.memory_manager = MemoryManager(str(store.memory_dir(conversation["id"])))
    executor.data_integrator = _DataIntegrator()
    executor.show_knowledge_appendix = False
    executor.compress_at = 999999
    executor.tool_executor = ExtendedToolExecutor(preview_manager=object())
    executor.langgraph_runner = LangGraphRunner(
        model,
        [_tool_definition("view_image")],
        executor.execute_graph_tool,
    )
    executor._langgraph_max_steps = executor.max_steps
    executor.build_system_prompt = (
        lambda request, _context, **_kwargs: ("system", request)
    )

    monkeypatch.setattr(desktop, "conversation_store", store)
    desktop.conversation_runs.clear()
    desktop.conversation_executors.clear()
    desktop.conversation_generations.clear()
    desktop.conversation_executors[conversation["id"]] = executor
    message_id = 301

    result = desktop.send_message(
        "请描述这张图",
        message_id=message_id,
        conversation_id=conversation["id"],
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

    for _ in range(100):
        if not desktop.get_execution_status(conversation["id"], message_id)["running"]:
            break
        time.sleep(0.01)

    assert desktop.get_execution_status(conversation["id"], message_id)["running"] is False
    persisted_user = next(
        event
        for event in store.load(conversation["id"])["messages"]
        if event.get("type") == "user"
    )
    image_path = persisted_user["attachments"][0]["path"]
    assert Path(image_path).is_file()
    assert _image_data_url() not in str(persisted_user)

    first_turn = "\n".join(str(message.content) for message in model.seen_messages[0])
    assert image_path in first_turn
    assert _image_data_url() not in first_turn
    second_turn = model.seen_messages[1]
    assert any(
        isinstance(message, HumanMessage)
        and isinstance(message.content, list)
        and message.content[-1]["image_url"]["url"] == _image_data_url()
        for message in second_turn
    )

    memory = "\n".join(executor.memory_manager.load_execution_history())
    assert image_path in memory
    assert _image_data_url() not in memory
    assert executor.tool_executor.execute(
        {"tool": "view_image", "params": {"path": image_path}},
        conversation_id=conversation["id"],
        message_id=message_id,
    ).startswith("Error:")


def test_desktop_task_can_view_the_same_image_more_than_once(
    monkeypatch, tmp_path
) -> None:
    store = ConversationStore(tmp_path / "conversations")
    conversation = store.create("repeat desktop image")
    model = _RepeatedManifestImageModel()
    executor = desktop.DesktopTaskExecutor()
    executor.conversation_id = conversation["id"]
    executor.memory_manager = MemoryManager(str(store.memory_dir(conversation["id"])))
    executor.data_integrator = _DataIntegrator()
    executor.show_knowledge_appendix = False
    executor.compress_at = 999999
    executor.tool_executor = ExtendedToolExecutor(preview_manager=object())
    executor.langgraph_runner = LangGraphRunner(
        model,
        [_tool_definition("view_image")],
        executor.execute_graph_tool,
    )
    executor._langgraph_max_steps = executor.max_steps
    executor.build_system_prompt = (
        lambda request, _context, **_kwargs: ("system", request)
    )

    monkeypatch.setattr(desktop, "conversation_store", store)
    desktop.conversation_runs.clear()
    desktop.conversation_executors.clear()
    desktop.conversation_generations.clear()
    desktop.conversation_executors[conversation["id"]] = executor
    message_id = 302

    assert desktop.send_message(
        "请描述这张图",
        message_id=message_id,
        conversation_id=conversation["id"],
        attachments=[
            {
                "name": "desktop.png",
                "type": "image/png",
                "size": len(PNG_BYTES),
                "data": _image_data_url(),
            }
        ],
    ) == {"status": "processing"}

    for _ in range(100):
        if not desktop.get_execution_status(conversation["id"], message_id)["running"]:
            break
        time.sleep(0.01)

    assert desktop.get_execution_status(conversation["id"], message_id)["running"] is False
    assert len(model.seen_messages) == 3
    for turn in model.seen_messages[1:]:
        assert any(
            isinstance(message, HumanMessage)
            and isinstance(message.content, list)
            and message.content[-1]["image_url"]["url"] == _image_data_url()
            for message in turn
        )


def test_follow_up_task_rehydrates_images_from_its_conversation(
    monkeypatch, tmp_path
) -> None:
    store = ConversationStore(tmp_path / "conversations")
    conversation = store.create("follow-up desktop image")
    model = _FollowUpImageModel()
    executor = desktop.DesktopTaskExecutor()
    executor.conversation_id = conversation["id"]
    executor.memory_manager = MemoryManager(str(store.memory_dir(conversation["id"])))
    executor.data_integrator = _DataIntegrator()
    executor.show_knowledge_appendix = False
    executor.compress_at = 999999
    executor.tool_executor = ExtendedToolExecutor(preview_manager=object())
    executor.langgraph_runner = LangGraphRunner(
        model,
        [_tool_definition("view_image")],
        executor.execute_graph_tool,
    )
    executor._langgraph_max_steps = executor.max_steps
    executor.build_system_prompt = (
        lambda request, _context, **_kwargs: ("system", request)
    )

    monkeypatch.setattr(desktop, "conversation_store", store)
    desktop.conversation_runs.clear()
    desktop.conversation_executors.clear()
    desktop.conversation_generations.clear()
    desktop.conversation_executors[conversation["id"]] = executor

    first_message_id = 303
    assert desktop.send_message(
        "这是什么？",
        message_id=first_message_id,
        conversation_id=conversation["id"],
        attachments=[
            {
                "name": "desktop.png",
                "type": "image/png",
                "size": len(PNG_BYTES),
                "data": _image_data_url(),
            }
        ],
    ) == {"status": "processing"}
    for _ in range(100):
        if not desktop.get_execution_status(
            conversation["id"], first_message_id
        )["running"]:
            break
        time.sleep(0.01)
    assert desktop.get_execution_status(conversation["id"], first_message_id)[
        "running"
    ] is False

    saved_image = store.load(conversation["id"])["messages"][0]["attachments"][0]
    image_path = saved_image["path"]
    assert executor.tool_executor.execute(
        {"tool": "view_image", "params": {"path": image_path}},
        conversation_id=conversation["id"],
        message_id=first_message_id,
    ).startswith("Error:")

    second_message_id = 304
    assert desktop.send_message(
        "左边有什么？",
        message_id=second_message_id,
        conversation_id=conversation["id"],
    ) == {"status": "processing"}
    for _ in range(100):
        if not desktop.get_execution_status(
            conversation["id"], second_message_id
        )["running"]:
            break
        time.sleep(0.01)
    assert desktop.get_execution_status(conversation["id"], second_message_id)[
        "running"
    ] is False

    assert len(model.seen_messages) == 4
    follow_up_first_turn = "\n".join(
        str(message.content) for message in model.seen_messages[2]
    )
    assert image_path in follow_up_first_turn
    assert any(
        isinstance(message, HumanMessage)
        and isinstance(message.content, list)
        and message.content[-1]["image_url"]["url"] == _image_data_url()
        for message in model.seen_messages[3]
    )


def test_conversation_image_list_uses_the_stored_asset_id(tmp_path) -> None:
    store = ConversationStore(tmp_path / "conversations")
    conversation = store.create("canonical images")
    asset_id = store.save_attachment(
        conversation["id"], 401, "image/png", PNG_BYTES
    )
    store.append_message(
        conversation["id"],
        {
            "type": "user",
            "message_id": 401,
            "attachments": [
                {
                    "name": "screen.png",
                    "asset_id": asset_id,
                    "type": "image/png",
                    "size": len(PNG_BYTES),
                    "path": str(tmp_path / "not-trusted.png"),
                    "success": True,
                }
            ],
        },
    )

    records = store.list_image_attachments(conversation["id"])

    assert records == [
        {
            "asset_id": asset_id,
            "name": "screen.png",
            "path": str(store.attachment_path(conversation["id"], asset_id)),
            "type": "image/png",
            "size": len(PNG_BYTES),
            "source_message_id": 401,
        }
    ]
