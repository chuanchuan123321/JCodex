"""Persistence tests for desktop conversation metadata."""

import json

import pytest

from agent.core.conversation_store import ConversationStore


def _listed(store: ConversationStore, conversation_id: str) -> dict:
    return next(
        item
        for item in store.list()["conversations"]
        if item["id"] == conversation_id
    )


def test_completion_state_persists_and_can_be_marked_read(tmp_path) -> None:
    root = tmp_path / "conversations"
    store = ConversationStore(root)
    conversation = store.create("background task")

    completed = store.mark_completed(conversation["id"], 1234)

    assert completed["unread_completion"] is True
    assert completed["last_completed_message_id"] == 1234
    assert completed["last_read_message_id"] == 0
    assert _listed(store, conversation["id"])["unread_completion"] is True

    reloaded = ConversationStore(root)
    assert reloaded.load(conversation["id"])["unread_completion"] is True

    read = reloaded.mark_read(conversation["id"])
    assert read["unread_completion"] is False
    assert read["last_read_message_id"] == 1234
    assert _listed(reloaded, conversation["id"])["unread_completion"] is False


def test_visible_completion_and_clear_reset_completion_state(tmp_path) -> None:
    store = ConversationStore(tmp_path / "conversations")
    conversation = store.create("visible task")

    completed = store.mark_completed(conversation["id"], 200, unread=False)
    assert completed["unread_completion"] is False
    assert completed["last_completed_message_id"] == 200
    assert completed["last_read_message_id"] == 0

    store.mark_completed(conversation["id"], 201)
    cleared = store.clear(conversation["id"])
    assert cleared["unread_completion"] is False
    assert cleared["last_completed_message_id"] == 0
    assert cleared["last_read_message_id"] == 0


def test_rename_and_append_preserve_unread_completion(tmp_path) -> None:
    store = ConversationStore(tmp_path / "conversations")
    conversation = store.create("original")
    store.mark_completed(conversation["id"], 300)

    store.rename(conversation["id"], "renamed")
    store.append_message(
        conversation["id"],
        {"type": "assistant", "content": "done", "message_id": 300},
    )

    loaded = store.load(conversation["id"])
    assert loaded["title"] == "renamed"
    assert loaded["unread_completion"] is True
    assert loaded["last_completed_message_id"] == 300
    assert _listed(store, conversation["id"])["unread_completion"] is True


def test_stale_completion_cannot_clear_a_newer_unread_result(tmp_path) -> None:
    store = ConversationStore(tmp_path / "conversations")
    conversation = store.create("overlapping completions")
    store.mark_completed(conversation["id"], 500)

    stale = store.mark_completed(conversation["id"], 400, unread=False)

    assert stale["unread_completion"] is True
    assert stale["last_completed_message_id"] == 500
    assert stale["last_read_message_id"] == 0


def test_mark_completed_can_use_the_active_task_atomically(tmp_path) -> None:
    store = ConversationStore(tmp_path / "conversations")
    first = store.create("first")
    second = store.create("second")

    store.set_active(first["id"])
    store.mark_completed(first["id"], 10, unread=None)
    store.mark_completed(second["id"], 20, unread=None)

    assert store.load(first["id"])["unread_completion"] is False
    assert store.load(second["id"])["unread_completion"] is True


def test_split_tasks_keep_messages_separate_and_fork_short_term_memory(
    tmp_path,
) -> None:
    store = ConversationStore(tmp_path / "conversations")
    parent = store.create("parent task")
    store.append_message(parent["id"], {"type": "user", "content": "parent only"})
    parent_memory = store.memory_dir(parent["id"])
    (parent_memory / "accumulated_compression.md").write_text(
        "shared short context", encoding="utf-8"
    )

    child = store.create_split(parent["id"])

    assert child["id"] != parent["id"]
    assert child["messages"] == []
    reloaded_parent = store.load(parent["id"])
    reloaded_child = store.load(child["id"])
    assert reloaded_parent["messages"][0]["content"] == "parent only"
    assert reloaded_parent["memory_scope_id"] is None
    assert reloaded_child["memory_scope_id"] is None
    assert reloaded_parent["is_split_task"] is False
    assert reloaded_child["is_split_task"] is True
    assert reloaded_child["parent_conversation_id"] == parent["id"]
    assert reloaded_parent["short_term_memory_id"] is None
    assert reloaded_child["short_term_memory_id"] == child["id"]
    assert store.short_term_memory_dir(parent["id"]) == parent_memory
    assert store.short_term_memory_dir(child["id"]) == store.memory_dir(child["id"])
    assert store.short_term_memory_dir(child["id"]) != parent_memory
    assert (
        store.short_term_memory_dir(child["id"])
        / "accumulated_compression.md"
    ).read_text(encoding="utf-8") == "shared short context"
    (store.short_term_memory_dir(child["id"]) / "accumulated_compression.md").write_text(
        "child branch", encoding="utf-8"
    )
    assert (
        store.short_term_memory_dir(parent["id"])
        / "accumulated_compression.md"
    ).read_text(encoding="utf-8") == "shared short context"
    assert reloaded_parent["split_conversation_id"] == child["id"]
    assert reloaded_parent["split_open"] is True


def test_split_state_reuses_child_and_persists_visibility_and_width(tmp_path) -> None:
    store = ConversationStore(tmp_path / "conversations")
    parent = store.create("parent")

    first_child = store.create_split(parent["id"])
    child_memory = store.short_term_memory_dir(first_child["id"])
    (child_memory / "execution_history.md").write_text(
        "child-only\n", encoding="utf-8"
    )
    (store.short_term_memory_dir(parent["id"]) / "execution_history.md").write_text(
        "new-parent-state\n", encoding="utf-8"
    )
    store.set_split_state(parent["id"], is_open=False, width=640)
    closed = store.get_split_state(parent["id"])
    reopened_child = store.create_split(parent["id"])
    reopened = store.get_split_state(parent["id"])

    assert closed == {
        "parent_conversation_id": parent["id"],
        "conversation_id": first_child["id"],
        "open": False,
        "width": 640,
    }
    assert reopened_child["id"] == first_child["id"]
    assert (child_memory / "execution_history.md").read_text(encoding="utf-8") == "child-only\n"
    assert reopened["open"] is True
    assert reopened["width"] == 640


def test_deleting_split_then_creating_again_forks_latest_parent_memory(tmp_path) -> None:
    store = ConversationStore(tmp_path / "conversations")
    parent = store.create("parent")
    parent_history = store.short_term_memory_dir(parent["id"]) / "execution_history.md"
    parent_history.write_text("first snapshot\n", encoding="utf-8")
    first_child = store.create_split(parent["id"])

    result = store.delete(first_child["id"])
    parent_history.write_text("latest parent snapshot\n", encoding="utf-8")
    second_child = store.create_split(parent["id"])

    assert result["deleted_conversation_ids"] == [first_child["id"]]
    assert not store.memory_dir(first_child["id"]).exists()
    assert second_child["id"] != first_child["id"]
    assert (
        store.short_term_memory_dir(second_child["id"])
        / "execution_history.md"
    ).read_text(encoding="utf-8") == "latest parent snapshot\n"


def test_deleting_primary_task_also_deletes_its_internal_split(tmp_path) -> None:
    store = ConversationStore(tmp_path / "conversations")
    parent = store.create("parent")
    child = store.create_split(parent["id"])

    result = store.delete(parent["id"])

    with pytest.raises(ValueError, match="Conversation not found"):
        store.load(child["id"])
    assert result["deleted_conversation_ids"] == sorted(
        [parent["id"], child["id"]]
    )


def test_legacy_split_task_is_migrated_and_cannot_remain_globally_active(
    tmp_path,
) -> None:
    root = tmp_path / "conversations"
    store = ConversationStore(root)
    parent = store.create("parent")
    child = store.create_split(parent["id"])
    child_file = root / child["id"] / "conversation.json"
    legacy_child = json.loads(child_file.read_text(encoding="utf-8"))
    legacy_child["short_term_memory_id"] = parent["id"]
    legacy_child.pop("is_split_task", None)
    legacy_child.pop("parent_conversation_id", None)
    child_file.write_text(json.dumps(legacy_child), encoding="utf-8")
    index = json.loads((root / "index.json").read_text(encoding="utf-8"))
    index["active_id"] = child["id"]
    for item in index["conversations"]:
        if item["id"] == child["id"]:
            item["short_term_memory_id"] = parent["id"]
        item.pop("is_split_task", None)
        item.pop("parent_conversation_id", None)
    (root / "index.json").write_text(json.dumps(index), encoding="utf-8")

    migrated = ConversationStore(root)

    assert migrated.active_id() == parent["id"]
    migrated_child = migrated.load(child["id"])
    assert migrated_child["is_split_task"] is True
    assert migrated_child["short_term_memory_id"] == child["id"]
    assert migrated.short_term_memory_dir(child["id"]) != migrated.short_term_memory_dir(
        parent["id"]
    )


def test_visible_completion_becomes_unread_after_switch_before_opening(
    tmp_path,
) -> None:
    store = ConversationStore(tmp_path / "conversations")
    first = store.create("first")
    second = store.create("second")

    store.set_active(first["id"])
    store.mark_completed(first["id"], 10, unread=None)
    store.set_active(second["id"])
    store.mark_completed(first["id"], 11, unread=None)

    assert store.load(first["id"])["unread_completion"] is True


def test_legacy_conversation_is_migrated_with_readable_defaults(tmp_path) -> None:
    root = tmp_path / "conversations"
    store = ConversationStore(root)
    conversation = store.create("legacy")
    conversation_file = root / conversation["id"] / "conversation.json"
    legacy = json.loads(conversation_file.read_text(encoding="utf-8"))
    legacy.pop("unread_completion")
    legacy.pop("last_completed_message_id")
    legacy.pop("last_read_message_id")
    conversation_file.write_text(json.dumps(legacy), encoding="utf-8")

    index = json.loads((root / "index.json").read_text(encoding="utf-8"))
    for item in index["conversations"]:
        if item["id"] == conversation["id"]:
            item.pop("unread_completion", None)
            item.pop("last_completed_message_id", None)
            item.pop("last_read_message_id", None)
    (root / "index.json").write_text(json.dumps(index), encoding="utf-8")

    migrated = ConversationStore(root)
    loaded = migrated.load(conversation["id"])
    metadata = _listed(migrated, conversation["id"])
    for value in (loaded, metadata):
        assert value["unread_completion"] is False
        assert value["last_completed_message_id"] == 0
        assert value["last_read_message_id"] == 0


def test_mark_completed_rejects_invalid_message_id(tmp_path) -> None:
    store = ConversationStore(tmp_path / "conversations")
    conversation = store.create("invalid")

    with pytest.raises(ValueError, match="positive integer"):
        store.mark_completed(conversation["id"], 0)


def test_plan_snapshot_rejects_an_older_version(tmp_path) -> None:
    store = ConversationStore(tmp_path / "conversations")
    conversation = store.create("versioned plan")
    conversation_id = conversation["id"]

    newest = store.upsert_plan_snapshot(
        conversation_id,
        {
            "message_id": 700,
            "version": 2,
            "plan": [{"step": "newest", "status": "in_progress"}],
        },
    )
    rejected = store.upsert_plan_snapshot(
        conversation_id,
        {
            "message_id": 700,
            "version": 1,
            "plan": [{"step": "stale", "status": "in_progress"}],
        },
    )

    persisted = [
        event
        for event in store.load(conversation_id)["messages"]
        if event.get("type") == "plan_update"
    ]
    assert rejected == newest
    assert len(persisted) == 1
    assert persisted[0]["version"] == 2
    assert persisted[0]["plan"][0]["step"] == "newest"


def test_plan_terminal_state_persists_without_rewriting_steps(tmp_path) -> None:
    root = tmp_path / "conversations"
    store = ConversationStore(root)
    conversation = store.create("terminal plan")
    conversation_id = conversation["id"]
    plan = [
        {"step": "implement", "status": "in_progress"},
        {"step": "verify", "status": "pending"},
    ]
    store.upsert_plan_snapshot(
        conversation_id,
        {"message_id": 701, "version": 3, "plan": plan},
    )

    terminal = store.mark_plan_terminal(
        conversation_id,
        701,
        "complete",
        "task finished",
    )

    assert terminal is not None
    reloaded = ConversationStore(root).load(conversation_id)
    persisted = next(
        event
        for event in reloaded["messages"]
        if event.get("type") == "plan_update"
    )
    assert persisted["plan"] == plan
    assert persisted["terminal_state"] == "complete"
    assert persisted["terminal_message"] == "task finished"
    assert persisted["terminal_at"]


def test_agent_team_snapshot_replaces_only_its_own_newer_version(tmp_path) -> None:
    store = ConversationStore(tmp_path / "conversations")
    conversation = store.create("multi agent")
    conversation_id = conversation["id"]

    newest = store.upsert_agent_team_snapshot(
        conversation_id,
        {
            "message_id": 800,
            "team_id": "team-a",
            "version": 3,
            "status": "running",
            "agents": [{"id": "research", "status": "running"}],
        },
    )
    stale = store.upsert_agent_team_snapshot(
        conversation_id,
        {
            "message_id": 800,
            "team_id": "team-a",
            "version": 2,
            "status": "complete",
            "agents": [{"id": "research", "status": "completed"}],
        },
    )
    store.upsert_agent_team_snapshot(
        conversation_id,
        {
            "message_id": 800,
            "team_id": "team-b",
            "version": 1,
            "status": "complete",
            "agents": [],
        },
    )

    persisted = [
        event
        for event in store.load(conversation_id)["messages"]
        if event.get("type") == "agent_team"
    ]
    assert stale == newest
    assert len(persisted) == 2
    team_a = next(event for event in persisted if event["team_id"] == "team-a")
    assert team_a["version"] == 3
    assert team_a["agents"][0]["status"] == "running"
