"""Core regressions for bounded multi-agent collaboration."""

from __future__ import annotations

import json
import queue
import threading
import time

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessageChunk, HumanMessage
from langchain_core.outputs import ChatGenerationChunk
from pydantic import Field

from agent.core.conversation_store import ConversationStore
from agent.core.extended_tool_executor import ExtendedToolExecutor
from agent.core.langgraph_runner import LangGraphRunner
from agent.core.multi_agent import MULTI_AGENT_TOOL_NAMES, MultiAgentTeam


def _tool(name: str) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": f"Test {name}",
            "parameters": {"type": "object", "properties": {}},
        },
    }


def _tool_chunk(name: str, call_id: str) -> AIMessageChunk:
    return AIMessageChunk(
        content="",
        tool_call_chunks=[
            {
                "name": name,
                "args": "{}",
                "id": call_id,
                "index": 0,
                "type": "tool_call_chunk",
            }
        ],
    )


def _tool_chunk_with_args(name: str, call_id: str, args: dict) -> AIMessageChunk:
    return AIMessageChunk(
        content="",
        tool_call_chunks=[
            {
                "name": name,
                "args": json.dumps(args),
                "id": call_id,
                "index": 0,
                "type": "tool_call_chunk",
            }
        ],
    )


class _RecordingModel(BaseChatModel):
    scripts: list[list[AIMessageChunk]]
    turn: int = 0
    bound_tool_sets: list[list[str]] = Field(default_factory=list)
    seen_messages: list[list] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "multi-agent-recording-model"

    def bind_tools(self, tools, **_kwargs):
        self.bound_tool_sets.append([tool.name for tool in tools])
        return self

    def _generate(self, messages, **kwargs):
        raise NotImplementedError

    def _stream(self, messages, **_kwargs):
        self.seen_messages.append(list(messages))
        chunks = self.scripts[self.turn]
        self.turn += 1
        for chunk in chunks:
            yield ChatGenerationChunk(message=chunk)


def _wait_for_status(
    team: MultiAgentTeam, agent_id: str, status: str, timeout: float = 2
) -> dict:
    deadline = time.monotonic() + timeout
    snapshot = team.get_agent(agent_id)
    while snapshot["status"] != status and time.monotonic() < deadline:
        time.sleep(0.005)
        snapshot = team.get_agent(agent_id)
    return snapshot


def test_team_is_bounded_and_publishes_versioned_full_snapshots() -> None:
    release = threading.Event()
    updates: list[dict] = []

    def worker(agent, cancel_event, activity):
        for index in range(6):
            activity(f"{agent['name']} activity {index}", "progress", {"index": index})
        while not release.wait(0.005):
            if cancel_event.is_set():
                return None
        return {"report": agent["task"]}

    team = MultiAgentTeam(
        worker,
        on_update=updates.append,
        max_agents=4,
        max_activities=3,
    )
    agents = [
        team.spawn(f"Agent {index}", "researcher", f"task {index}")
        for index in range(4)
    ]

    with pytest.raises(RuntimeError, match="maximum of 4"):
        team.spawn("Agent 5", "researcher", "overflow")

    release.set()
    waited = team.wait_agents(timeout=2)

    assert waited["wait"]["completed"] is True
    assert waited["agent_count"] == 4
    assert waited["active_count"] == 0
    assert all(agent["status"] == "completed" for agent in waited["agents"])
    assert all(len(agent["activities"]) <= 3 for agent in waited["agents"])
    assert {agent["agent_id"] for agent in waited["agents"]} == {
        agent["agent_id"] for agent in agents
    }
    versions = [snapshot["version"] for snapshot in updates]
    assert versions == sorted(versions)
    assert len(versions) == len(set(versions))
    assert updates[-1]["version"] == waited["version"]
    assert all("agents" in snapshot for snapshot in updates)


def test_messages_reach_worker_inbox_and_cancellation_is_cooperative() -> None:
    received: list[str] = []

    def worker(_agent, cancel_event, activity, inbox: queue.Queue[str]):
        while not cancel_event.is_set():
            try:
                message = inbox.get(timeout=0.01)
            except queue.Empty:
                continue
            received.append(message)
            activity(f"received: {message}", "message")
        return "late result must be discarded"

    team = MultiAgentTeam(worker)
    spawned = team.spawn("Reader", "reviewer", "inspect")
    agent_id = spawned["agent_id"]
    team.send_message(agent_id, "focus on cancellation")

    deadline = time.monotonic() + 2
    while not received and time.monotonic() < deadline:
        time.sleep(0.005)
    cancelled = team.cancel_agent(agent_id)
    waited = team.wait_agents([agent_id], timeout=2)
    agent = next(item for item in waited["agents"] if item["agent_id"] == agent_id)

    assert received == ["focus on cancellation"]
    assert cancelled["status"] in {"cancelling", "cancelled"}
    assert agent["status"] == "cancelled"
    assert agent["result"] is None
    assert agent["messages"][0]["content"] == "focus on cancellation"


def test_peer_handoffs_artifacts_dependencies_and_file_claims_are_bounded() -> None:
    release = threading.Event()
    started: list[str] = []

    def worker(agent, cancel_event, _activity):
        started.append(agent["agent_id"])
        while not cancel_event.is_set() and not release.wait(0.005):
            pass
        return agent["task"]

    team = MultiAgentTeam(worker)
    author = team.spawn(
        "API", "contract owner", "define API", write_access=True,
        write_paths=["src/api.py"], workdir="/tmp/example-project",
    )
    dependent = team.spawn(
        "UI", "consumer", "use API", depends_on=[author["agent_id"]],
        write_access=True, write_paths=["src/ui.py"],
    )

    with pytest.raises(ValueError, match="already claimed"):
        team.spawn(
            "Conflict", "writer", "overwrite API", write_access=True,
            write_paths=["src/api.py"],
        )

    waiting = _wait_for_status(team, dependent["agent_id"], "waiting")
    assert waiting["depends_on"] == [author["agent_id"]]
    team.send_message(
        dependent["agent_id"], "Use v2 response fields", sender_agent_id=author["agent_id"],
        kind="handoff", references=["src/api.py"],
    )
    artifact = team.publish_artifact(
        author["agent_id"], "API contract", "Expose id and display_name",
        ["src/api.py"], [dependent["agent_id"]],
    )
    inbox = team.take_inbox(dependent["agent_id"])
    snapshot = team.list_agents()

    assert "[协作消息/handoff]" in inbox[0]
    assert artifact["title"] == "API contract"
    assert author["workdir"] == "/tmp/example-project"
    author_claim = next(
        claim for claim in snapshot["file_claims"]
        if claim["agent_id"] == author["agent_id"]
    )
    assert author_claim["workdir"] == "/tmp/example-project"
    assert snapshot["artifacts"][0]["recipient_agent_ids"] == [dependent["agent_id"]]
    assert {event["type"] for event in snapshot["collaboration_events"]} == {
        "message", "artifact"
    }
    assert len(snapshot["file_claims"]) == 2
    scoped = team.collaboration_snapshot(dependent["agent_id"])
    assert scoped["artifacts"][0]["title"] == "API contract"
    assert len(scoped["file_claims"]) == 2

    public_contract = team.publish_artifact(
        "primary", "Project contract v1", "Use config.py as the single source of truth"
    )
    scoped_after_contract = team.collaboration_snapshot(dependent["agent_id"])
    assert public_contract["id"] in {
        artifact["id"] for artifact in scoped_after_contract["artifacts"]
    }

    release.set()
    waited = team.wait_agents(timeout=2)
    assert waited["wait"]["completed"] is True
    assert dependent["agent_id"] in started


def test_extended_executor_exposes_and_runtime_dispatches_collaboration_tools() -> None:
    names = {
        item["function"]["name"]
        for item in ExtendedToolExecutor._multi_agent_tool_definitions()
    }
    assert names == MULTI_AGENT_TOOL_NAMES

    executor = object.__new__(ExtendedToolExecutor)
    executor.tools = {}
    unavailable = executor.execute(
        {"tool": "list_agents", "params": {}}, runtime={}
    )
    assert "Multi-Agent Mode is not active" in unavailable

    calls = []

    def dispatch(name, params):
        calls.append((name, params))
        return {"success": True, "name": name}

    result = executor.execute(
        {
            "tool": "spawn_agent",
            "params": {"name": "A", "role": "R", "task": "T"},
        },
        runtime={"multi_agent_dispatch": dispatch},
    )

    assert json.loads(result) == {"success": True, "name": "spawn_agent"}
    assert calls == [
        ("spawn_agent", {"name": "A", "role": "R", "task": "T"})
    ]


def test_runner_removes_multi_agent_tools_from_actual_binding_when_disabled() -> None:
    model = _RecordingModel(scripts=[[AIMessageChunk(content="done")]])
    tools = [_tool("read"), *[_tool(name) for name in sorted(MULTI_AGENT_TOOL_NAMES)]]
    runner = LangGraphRunner(model, tools, lambda *_args: "unused")

    result = runner.run(
        "multi-disabled-binding",
        "start",
        runtime={"multi_agent_enabled": False},
    )

    assert result.status == "complete"
    assert set(model.bound_tool_sets[0]) == {tool["function"]["name"] for tool in tools}
    assert model.bound_tool_sets[-1] == ["read"]


def test_runner_rejects_stale_multi_agent_call_when_mode_is_disabled() -> None:
    model = _RecordingModel(
        scripts=[
            [_tool_chunk("spawn_agent", "spawn-stale")],
            [AIMessageChunk(content="recovered")],
        ]
    )
    executed = []
    events = []
    runner = LangGraphRunner(
        model,
        [_tool("spawn_agent")],
        lambda *args: executed.append(args) or "must not run",
    )

    result = runner.run(
        "multi-disabled-stale",
        "start",
        runtime={"multi_agent_enabled": False},
        emit=events.append,
    )

    assert result.content == "recovered"
    assert executed == []
    disabled = [
        event
        for event in events
        if event["type"] == "tool_end" and event.get("tool") == "spawn_agent"
    ]
    assert len(disabled) == 1
    assert disabled[0]["disabled"] is True
    assert "Multi-Agent Mode is off" in disabled[0]["result"]


def test_runner_injects_collaboration_messages_only_at_safe_boundaries() -> None:
    model = _RecordingModel(scripts=[[AIMessageChunk(content="received handoff")]])
    runner = LangGraphRunner(model, [], lambda *_args: "unused")
    delivered = [["[协作消息/handoff] 来自 API\nUse the published contract"]]

    result = runner.run(
        "collaboration-safe-boundary",
        "start",
        runtime={
            "collaboration_messages": lambda _state: delivered.pop(0) if delivered else [],
        },
    )

    assert result.status == "complete"
    injected = [
        message.content
        for message in model.seen_messages[0]
        if isinstance(message, HumanMessage)
        and "New Collaboration Messages" in str(message.content)
    ]
    assert len(injected) == 1
    assert "Use the published contract" in injected[0]


def test_finish_guard_turns_early_final_into_a_continuation() -> None:
    model = _RecordingModel(
        scripts=[
            [AIMessageChunk(content="premature answer")],
            [AIMessageChunk(content="answer with agent evidence")],
        ]
    )
    decisions = iter(
        [
            {"active_count": 1, "message": "Wait for the reviewer."},
            {"active_count": 0},
        ]
    )
    events = []
    runner = LangGraphRunner(model, [], lambda *_args: "unused")

    result = runner.run(
        "multi-finish-guard",
        "start",
        runtime={"finish_guard": lambda: next(decisions)},
        emit=events.append,
    )

    assert result.status == "complete"
    assert result.content == "answer with agent evidence"
    assert any(event["type"] == "finish_blocked" for event in events)
    first_end = next(event for event in events if event["type"] == "model_end")
    assert first_end["finish_blocked"] is True
    assert first_end["tool_calls"][0]["name"] == "__finish_guard__"
    assert any(
        isinstance(message, HumanMessage)
        and message.content == "Wait for the reviewer."
        for message in model.seen_messages[1]
    )


def test_writable_child_respects_auto_allow_setting() -> None:
    args = {
        "name": "Implementer",
        "role": "Scoped editor",
        "task": "Update one file",
        "write_access": True,
        "write_paths": ["src/app.py"],
    }
    model = _RecordingModel(
        scripts=[
            [_tool_chunk_with_args("spawn_agent", "spawn-write", args)],
            [AIMessageChunk(content="delegated")],
        ]
    )
    executed = []
    runner = LangGraphRunner(
        model,
        [_tool("spawn_agent")],
        lambda *call: executed.append(call) or "must not execute before approval",
        requires_approval=lambda name, params: (
            name == "spawn_agent" and params.get("write_access") is True
        ),
    )
    events = []

    result = runner.run(
        "multi-write-approval",
        "start",
        runtime={
            "allow_all": True,
            "multi_agent_enabled": True,
        },
        emit=events.append,
    )

    assert result.status == "complete"
    assert result.content == "delegated"
    assert len(executed) == 1
    assert executed[0][0] == "spawn_agent"
    assert executed[0][1] == args
    assert not any(event["type"] == "interrupt" for event in events)


def test_agent_team_snapshot_rejects_stale_versions_and_keeps_one_latest_event(
    tmp_path,
) -> None:
    store = ConversationStore(tmp_path / "conversations")
    conversation = store.create("multi-agent snapshots")
    conversation_id = conversation["id"]
    team_id = "team-versioned"

    newest = store.upsert_agent_team_snapshot(
        conversation_id,
        {
            "message_id": 901,
            "team_id": team_id,
            "version": 4,
            "status": "running",
            "agents": [{"id": "reviewer", "status": "running"}],
        },
    )
    stale = store.upsert_agent_team_snapshot(
        conversation_id,
        {
            "message_id": 901,
            "team_id": team_id,
            "version": 3,
            "status": "complete",
            "agents": [{"id": "stale", "status": "completed"}],
        },
    )
    completed = store.upsert_agent_team_snapshot(
        conversation_id,
        {
            "message_id": 901,
            "team_id": team_id,
            "version": 5,
            "status": "complete",
            "agents": [{"id": "reviewer", "status": "completed"}],
        },
    )

    persisted = [
        event
        for event in store.load(conversation_id)["messages"]
        if event.get("type") == "agent_team"
        and event.get("message_id") == 901
        and event.get("team_id") == team_id
    ]
    assert newest["version"] == 4
    assert stale["version"] == 4
    assert stale["agents"][0]["id"] == "reviewer"
    assert completed["version"] == 5
    assert len(persisted) == 1
    assert persisted[0]["id"] == newest["id"]
    assert persisted[0]["version"] == 5
    assert persisted[0]["agents"] == [
        {"id": "reviewer", "status": "completed"}
    ]
