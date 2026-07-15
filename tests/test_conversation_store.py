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
