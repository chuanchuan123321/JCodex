"""Tests for the Grok-style long-term memory lifecycle."""

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from agent.core.embedding_provider import (
    DisabledEmbeddingProvider,
    MockEmbeddingProvider,
    create_embedding_provider,
)
from agent.core.memory_manager import MemoryManager
from agent.core.memory_store import (
    GREETING_FALLBACK_QUERY,
    MEMORY_CONTEXT_CLOSE_TAG,
    MEMORY_CONTEXT_OPEN_TAG,
    MemorySearchResult,
    MemoryStore,
)


def store(tmp_path: Path) -> MemoryStore:
    return MemoryStore(
        tmp_path / "memory",
        tmp_path / "project",
        embedding_provider=MockEmbeddingProvider(dimensions=64),
    )


def test_greeting_uses_grok_fallback_query():
    assert MemoryStore.normalize_query("hi") == GREETING_FALLBACK_QUERY
    assert MemoryStore.normalize_query("continue") == GREETING_FALLBACK_QUERY
    assert MemoryStore.normalize_query("fix the authentication retry loop") == (
        "fix the authentication retry loop"
    )


def test_format_context_caps_each_snippet_at_500_characters():
    context = MemoryStore.format_memory_context(
        [
            MemorySearchResult(
                chunk_id="a",
                path="sessions/test.md",
                start_line=1,
                end_line=3,
                score=0.9,
                snippet="x" * 700,
                source="session",
            )
        ]
    )

    assert context.startswith(MEMORY_CONTEXT_OPEN_TAG)
    assert context.endswith(MEMORY_CONTEXT_CLOSE_TAG)
    assert "x" * 500 + "..." in context
    assert "x" * 501 not in context


def test_search_indexes_global_workspace_and_session_markdown(tmp_path):
    memory = store(tmp_path)
    memory.global_dir.mkdir(parents=True)
    (memory.global_dir / "MEMORY.md").write_text(
        "## Global\nUse pytest for verification.", encoding="utf-8"
    )
    memory.workspace_dir.mkdir(parents=True)
    (memory.workspace_dir / "MEMORY.md").write_text(
        "## Project\nAuthentication uses signed cookies.", encoding="utf-8"
    )
    memory.write_daily_log(
        trigger="pre_compaction",
        session_id="1234567890",
        content="## Debugging\nRetry failures were caused by stale cookies.",
        append=True,
    )

    results = memory.search("signed cookies authentication", limit=6)

    assert results
    assert any(result.source == "workspace" for result in results)
    assert all(result.path.endswith(".md") for result in results)


def test_conversation_record_keeps_original_user_requests_retrievable(tmp_path):
    memory = store(tmp_path)

    memory.upsert_conversation_record(
        session_id="a1b2c3d4-1234",
        title="Blockforge",
        user_requests=[
            "Build an infinite world with chunk streaming.",
            "Keep the spawn area open and free of trees.",
            "Add a creative flight mode.",
        ],
        summary="## Decisions\nInfinite terrain uses chunks.",
    )

    results = memory.search("infinite world chunk streaming", min_score=0.0)

    assert results
    assert any("Build an infinite world" in result.snippet for result in results)
    assert any(result.source == "session" for result in results)


def test_scoped_memory_store_does_not_read_another_conversation_or_global_memory(
    tmp_path,
):
    root = tmp_path / "memory"
    (root / "MEMORY.md").parent.mkdir(parents=True)
    (root / "MEMORY.md").write_text(
        "## Global\nDo not inject this into a task.", encoding="utf-8"
    )
    first = MemoryStore(
        root,
        tmp_path / "conversations" / "first" / "memory",
        embedding_provider=DisabledEmbeddingProvider(),
        include_global=False,
    )
    second = MemoryStore(
        root,
        tmp_path / "conversations" / "second" / "memory",
        embedding_provider=DisabledEmbeddingProvider(),
        include_global=False,
    )
    first.upsert_conversation_record(
        session_id="first", title="First", user_requests=["Build a voxel game"]
    )

    assert first.search("voxel game", min_score=0.0)
    assert not second.search("voxel game", min_score=0.0)
    assert not second.search("Do not inject", min_score=0.0)


def test_fts_fallback_finds_chinese_substrings_in_long_user_requests(tmp_path):
    memory = MemoryStore(
        tmp_path / "memory",
        tmp_path / "conversation",
        embedding_provider=DisabledEmbeddingProvider(),
        include_global=False,
    )
    memory.upsert_conversation_record(
        session_id="chinese",
        title="Game",
        user_requests=["你用提问模式给我做一个赛车游戏"],
    )

    results = memory.search("赛车游戏", min_score=0.0)

    assert results
    assert "赛车游戏" in results[0].snippet


def test_chunk_ids_are_unique_between_same_named_session_files(tmp_path):
    memory = MemoryStore(
        tmp_path / "memory",
        tmp_path / "project",
        embedding_provider=DisabledEmbeddingProvider(),
    )
    memory.sessions_dir.mkdir(parents=True)
    first = memory.sessions_dir / "same.md"
    first.write_text("## One\nfirst content", encoding="utf-8")
    memory.reindex()
    first.unlink()
    second = memory.sessions_dir / "same.md"
    second.write_text("## Two\nsecond content", encoding="utf-8")

    memory.reindex()

    assert memory.search("second content", min_score=0.0)


def test_reindex_replaces_an_orphaned_embedding_for_a_new_chunk(tmp_path):
    memory = store(tmp_path)
    memory.workspace_dir.mkdir(parents=True)
    record = memory.workspace_dir / "MEMORY.md"
    record.write_text("## Project\nKeep the index recoverable.", encoding="utf-8")
    relative = str(record.relative_to(memory.global_dir))
    chunk_id = f"{hashlib.sha256(relative.encode('utf-8')).hexdigest()[:16]}:0"

    connection = memory._connect()
    try:
        connection.execute(
            "INSERT INTO chunk_embeddings(chunk_id,embedding) VALUES(?,?)",
            (chunk_id, "[0.0]"),
        )
        connection.commit()
    finally:
        connection.close()

    results = memory.search("recoverable index", min_score=0.0)

    assert results
    with sqlite3.connect(memory.index_path) as connection:
        embedding = connection.execute(
            "SELECT embedding FROM chunk_embeddings WHERE chunk_id = ?", (chunk_id,)
        ).fetchone()[0]
    assert len(json.loads(embedding)) == 64


def test_deleting_one_conversation_record_keeps_sibling_session_memory(tmp_path):
    memory = MemoryStore(
        tmp_path / "memory",
        tmp_path / "project",
        embedding_provider=DisabledEmbeddingProvider(),
    )
    memory.upsert_conversation_record(
        session_id="a1b2c3d4-1111", title="First", user_requests=["first secret"]
    )
    memory.upsert_conversation_record(
        session_id="e5f6a7b8-2222", title="Second", user_requests=["second fact"]
    )

    assert memory.delete_conversation_record("a1b2c3d4-1111")

    assert not memory.search("first secret", min_score=0.0)
    assert memory.search("second fact", min_score=0.0)


def test_prune_orphaned_scopes_preserves_valid_and_unknown_directories(tmp_path):
    root = tmp_path / "memory"
    valid_path = tmp_path / "conversations" / "valid" / "memory"
    orphan_path = tmp_path / "conversations" / "deleted" / "memory"
    valid = MemoryStore(root, valid_path, embedding_provider=DisabledEmbeddingProvider())
    orphan = MemoryStore(root, orphan_path, embedding_provider=DisabledEmbeddingProvider())
    valid.upsert_conversation_record(
        session_id="valid-task", title="Valid", user_requests=["keep this"]
    )
    orphan.upsert_conversation_record(
        session_id="old-task", title="Old", user_requests=["remove this"]
    )
    unknown = root / "user-owned-folder"
    unknown.mkdir()
    (unknown / "note.txt").write_text("keep", encoding="utf-8")

    result = MemoryStore.prune_orphaned_scopes(root, [valid_path])

    assert valid.workspace_dir.is_dir()
    assert not orphan.workspace_dir.exists()
    assert unknown.is_dir()
    assert result["removed_scopes"] == [orphan.workspace_dir.name]
    assert result["removed_bytes"] > 0
    assert result["errors"] == []


def test_flush_selects_recent_window_and_expands_to_user_boundary():
    messages = [{"role": "user", "content": "first"}]
    for index in range(12):
        messages.extend(
            [
                {"role": "assistant", "content": f"answer {index}"},
                {"role": "tool", "content": f"tool {index}"},
            ]
        )
    messages.insert(0, {"role": "system", "content": "ignored"})

    selected = MemoryStore.select_flush_window(messages, recent_message_count=20)

    assert selected[0]["role"] == "user"
    assert all(item["role"] != "system" for item in selected)
    assert len(selected) > 20


def test_flush_writes_structured_log_and_uses_delta_prompt(tmp_path):
    memory = store(tmp_path)
    requests = []
    responses = iter(
        [
            "## Decisions & rationale\nUse a durable queue for retries.",
            "## Problems & solutions\nAdded an idempotency key.",
        ]
    )

    def sampler(messages):
        requests.append(messages)
        return next(responses)

    first = memory.flush(
        [{"role": "user", "content": "debug the retry queue"}],
        sampler,
        session_id="session12345678",
    )
    second = memory.flush(
        [{"role": "user", "content": "add idempotency"}],
        sampler,
        session_id="session12345678",
    )

    assert first.status == "written"
    assert second.status == "written"
    assert first.path == second.path
    content = Path(first.path).read_text(encoding="utf-8")
    assert "<!-- flush " in content
    assert "Added an idempotency key" in content
    assert "Previous flush content" in requests[1][0]["content"]
    assert all("tools" not in message for request in requests for message in request)


def test_flush_rejects_unstructured_and_skips_no_reply(tmp_path):
    memory = store(tmp_path)
    messages = [{"role": "user", "content": "ordinary question"}]

    no_reply = memory.flush(messages, lambda _messages: "NO_REPLY", session_id="one")
    rejected = memory.flush(
        messages,
        lambda _messages: "Useful but has no heading",
        session_id="two",
    )

    assert no_reply.status == "nothing_to_store"
    assert rejected.status == "rejected"
    assert not memory.sessions_dir.exists()


def test_flush_exact_duplicate_is_not_written_twice(tmp_path):
    memory = store(tmp_path)
    content = "## Technical context\nThe service uses a durable SQLite checkpoint."
    messages = [{"role": "user", "content": "checkpoint architecture"}]

    first = memory.flush(messages, lambda _messages: content, session_id="same")
    second = memory.flush(messages, lambda _messages: content, session_id="same")

    assert first.status == "written"
    assert second.status == "duplicate"
    assert Path(first.path).read_text(encoding="utf-8").count(content) == 1


def test_flush_threshold_includes_4000_token_headroom():
    assert MemoryStore.should_flush(104_800, 128_000, 85)
    assert not MemoryStore.should_flush(104_799, 128_000, 85)


def test_injected_context_is_persisted_verbatim_until_session_clear(tmp_path):
    manager = MemoryManager(str(tmp_path / "conversation"))
    context = "<memory-context>\nfixed prefix\n</memory-context>"

    manager.save_memory_context(context)
    resumed = MemoryManager(str(tmp_path / "conversation"))

    assert resumed.load_memory_context() == context
    resumed.clear_all()
    assert resumed.load_memory_context() == ""


def test_embedding_defaults_to_grok_fts_only_mode(monkeypatch):
    monkeypatch.delenv("MEMORY_EMBEDDING_MODEL", raising=False)

    provider = create_embedding_provider()

    assert provider.status()["provider"] == "disabled"
    assert provider.status()["available"] is False


def test_query_expansion_matches_grok_stop_word_rules():
    assert MemoryStore.extract_keywords("that thing we discussed about the API") == [
        "discussed",
        "api",
    ]
    assert MemoryStore.extract_keywords("what is that?") == []
    assert MemoryStore.extract_keywords("Go and JS patterns") == ["go", "js", "patterns"]


def test_markdown_chunker_uses_1600_chars_overlap_and_header_context():
    content = "# Root\n\n## Architecture\n\n" + ("alpha beta gamma\n" * 140)

    chunks = MemoryStore.chunk_markdown(content)

    assert len(chunks) > 1
    assert all(chunk.text for chunk in chunks)
    assert any("[Context: # Root]" in chunk.text for chunk in chunks)
    assert chunks[0].start_line == 0


def test_fts_only_search_uses_bm25_and_records_access(tmp_path):
    memory = MemoryStore(
        tmp_path / "memory",
        tmp_path / "project",
        embedding_provider=DisabledEmbeddingProvider(),
    )
    memory.workspace_dir.mkdir(parents=True)
    memory_file = memory.workspace_dir / "MEMORY.md"
    memory_file.write_text(
        "## Primary\nrust async runtime architecture\n\n"
        "## Secondary\nrust build notes",
        encoding="utf-8",
    )

    results = memory.search("rust async runtime", min_score=0.0)
    assert results
    assert results[0].score >= results[-1].score

    connection = memory._connect()
    try:
        access_count = connection.execute(
            "SELECT access_count FROM chunks WHERE id = ?", (results[0].chunk_id,)
        ).fetchone()[0]
    finally:
        connection.close()
    assert access_count == 1


def test_enabling_embeddings_backfills_unchanged_fts_index(tmp_path):
    root = tmp_path / "memory"
    project = tmp_path / "project"
    disabled = MemoryStore(
        root,
        project,
        embedding_provider=DisabledEmbeddingProvider(),
    )
    disabled.global_dir.mkdir(parents=True)
    (disabled.global_dir / "MEMORY.md").write_text(
        "## Deployments\nUse blue-green releases to keep the service online.",
        encoding="utf-8",
    )
    disabled.search("deployments", min_score=0.0)

    with sqlite3.connect(disabled.index_path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM chunk_embeddings"
        ).fetchone()[0] == 0

    enabled = MemoryStore(
        root,
        project,
        embedding_provider=MockEmbeddingProvider(dimensions=64),
    )
    enabled.search("unrelated vector-only query", min_score=0.0)

    with sqlite3.connect(enabled.index_path) as connection:
        chunk_count = connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        vector_count = connection.execute(
            "SELECT COUNT(*) FROM chunk_embeddings"
        ).fetchone()[0]
        signature = connection.execute(
            "SELECT value FROM index_metadata WHERE key = 'embedding_signature'"
        ).fetchone()
    assert vector_count == chunk_count == 1
    assert signature and '"dimension":64' in signature[0]


def test_embedding_model_change_rebuilds_vectors_without_file_changes(tmp_path):
    memory = store(tmp_path)
    memory.global_dir.mkdir(parents=True)
    (memory.global_dir / "MEMORY.md").write_text(
        "## Architecture\nThe queue uses durable SQLite checkpoints.",
        encoding="utf-8",
    )
    memory.search("queue architecture", min_score=0.0)

    replacement = MockEmbeddingProvider(dimensions=32)
    replacement.model = "mock-v2"
    changed = MemoryStore(
        memory.global_dir,
        tmp_path / "project",
        embedding_provider=replacement,
    )
    changed.search("semantic checkpoint lookup", min_score=0.0)

    with sqlite3.connect(changed.index_path) as connection:
        raw_vector = connection.execute(
            "SELECT embedding FROM chunk_embeddings"
        ).fetchone()[0]
        signature = connection.execute(
            "SELECT value FROM index_metadata WHERE key = 'embedding_signature'"
        ).fetchone()[0]
    assert len(json.loads(raw_vector)) == 32
    assert '"model":"mock-v2"' in signature


def test_temporal_decay_exempts_evergreen_and_halves_sessions_in_seven_days(tmp_path):
    memory = store(tmp_path)
    now = 10_000_000
    seven_days_ago = now - 7 * 86_400

    assert memory._temporal_decay("global", seven_days_ago, now) == 1.0
    assert memory._temporal_decay("workspace", seven_days_ago, now) == 1.0
    assert memory._temporal_decay("session", seven_days_ago, now) == pytest.approx(0.5)
