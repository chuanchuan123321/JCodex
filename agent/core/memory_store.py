"""Grok-compatible long-term memory storage, hybrid search, and flushing."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

from agent.core.embedding_provider import (
    BaseEmbeddingProvider,
    cosine_similarity,
    create_embedding_provider,
    l2_distance,
)
from agent.core.env_utils import env_float, env_int


MEMORY_CONTEXT_OPEN_TAG = "<memory-context>"
MEMORY_CONTEXT_CLOSE_TAG = "</memory-context>"
SNIPPET_MAX_CHARS = 500
INITIAL_SEARCH_LIMIT = 6
GREETING_FALLBACK_QUERY = "project conventions preferences architecture"
FLUSH_SOFT_THRESHOLD_TOKENS = 4_000
MAX_FLUSH_WRITE_CHARS = 8_000
SEMANTIC_DEDUP_THRESHOLD = 0.92
MAX_CHUNK_CHARS = 1_600
CHUNK_OVERLAP_CHARS = 320
DEFAULT_MIN_SCORE = 0.35
DEFAULT_VECTOR_WEIGHT = 0.7
DEFAULT_TEXT_WEIGHT = 0.3
DEFAULT_HALF_LIFE_DAYS = 7.0
DEFAULT_MMR_LAMBDA = 0.7

FLUSH_SYSTEM_PROMPT = """You are a memory assistant. Extract ALL useful information from this conversation that would help you be more effective in future sessions with this user. Write a concise markdown summary with ## headers covering:

- **Decisions & rationale** — what was chosen and why
- **Technical context** — architecture, APIs, patterns, tools, file paths discussed
- **Debugging techniques & tools** — external APIs, CLI commands, query patterns, investigation workflows, or services discovered or used during debugging
- **Problems & solutions** — bugs found, how they were fixed, workarounds

Omit any section where there is nothing substantive to report. Do NOT include user preferences like OS, shell, or editor — these belong in global memory. Do NOT include an ephemeral progress section — transient status is not useful for future sessions.

Respond with NO_REPLY if nothing genuinely useful was learned — a routine task that followed standard patterns, brief Q&A, or sessions with no novel decisions or discoveries are not worth persisting. Only write content that a future session would concretely benefit from."""

FLUSH_DELTA_SYSTEM_PROMPT = """You are a memory assistant performing an incremental update. The previous flush output for this session is shown below. Extract ONLY information that is NEW since the previous flush — do not repeat anything already captured.

Write a concise markdown summary with ## headers covering only NEW items in:
- **Decisions & rationale** — new decisions since last flush
- **Technical context** — new architecture, APIs, patterns discovered
- **Debugging techniques** — new techniques used since last flush
- **Problems & solutions** — new bugs found and fixes

Omit any section that has no new content. Do NOT include user preferences (OS, shell, paths) — these are captured in global memory. Do NOT include 'Current state' — this is ephemeral and not useful for future sessions.

Respond with NO_REPLY if nothing genuinely new and useful has happened since the previous flush. Routine changes that follow standard patterns are not worth an incremental update.

--- Previous flush content ---
"""


_STOP_WORDS = {
    "a", "an", "the", "this", "that", "these", "those", "i", "me", "my",
    "we", "our", "you", "your", "he", "she", "it", "they", "him", "her",
    "its", "them", "us", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "can", "may", "might", "in", "on", "at", "to", "for", "of",
    "with", "by", "from", "about", "into", "through", "during", "before",
    "after", "above", "below", "and", "or", "but", "if", "then", "because",
    "as", "while", "when", "where", "what", "which", "who", "how", "why",
    "thing", "things", "stuff", "something", "anything", "everything", "one",
    "some", "any", "all", "each", "every", "both", "few", "more", "yesterday",
    "today", "tomorrow", "earlier", "later", "recently", "now", "just", "already",
    "still", "yet", "please", "help", "find", "show", "get", "tell", "give",
    "make", "not", "no", "yes", "also", "too", "very", "really", "here",
    "there", "so", "up", "out", "like", "than", "other", "only",
}


@dataclass(frozen=True)
class MemorySearchResult:
    chunk_id: str
    path: str
    start_line: int
    end_line: int
    score: float
    snippet: str
    source: str
    created_at: Optional[int] = None


@dataclass(frozen=True)
class MemoryFlushResult:
    status: str
    content: str = ""
    path: str = ""
    error: str = ""
    truncated: bool = False

    @property
    def executed(self) -> bool:
        return self.status not in {"disabled", "busy", "below_threshold"}


@dataclass(frozen=True)
class _Chunk:
    text: str
    start_line: int
    end_line: int


class MemoryStore:
    """Markdown storage with Grok's SQLite FTS5/vector hybrid ranking pipeline."""

    def __init__(
        self,
        root_dir: str | Path,
        workspace_path: str | Path,
        *,
        embedding_provider: Optional[BaseEmbeddingProvider] = None,
        enabled: bool = True,
        include_global: bool = True,
    ) -> None:
        self.enabled = enabled
        self.include_global = bool(include_global)
        self.global_dir = Path(root_dir).expanduser().resolve()
        self.workspace_path = Path(workspace_path).expanduser().resolve()
        self.workspace_dir = self.global_dir / self._workspace_key(self.workspace_path)
        self.sessions_dir = self.workspace_dir / "sessions"
        self.index_path = self.workspace_dir / "index.sqlite"
        self.embedding_provider = embedding_provider or create_embedding_provider()
        self.max_chunk_chars = env_int("MEMORY_MAX_CHUNK_CHARS", MAX_CHUNK_CHARS)
        self.chunk_overlap_chars = env_int(
            "MEMORY_CHUNK_OVERLAP_CHARS", CHUNK_OVERLAP_CHARS
        )
        self.vector_weight = env_float("MEMORY_VECTOR_WEIGHT", DEFAULT_VECTOR_WEIGHT)
        self.text_weight = env_float("MEMORY_TEXT_WEIGHT", DEFAULT_TEXT_WEIGHT)
        self.min_score = env_float("MEMORY_MIN_SCORE", DEFAULT_MIN_SCORE)
        self.half_life_days = env_float("MEMORY_HALF_LIFE_DAYS", DEFAULT_HALF_LIFE_DAYS)
        self.mmr_enabled = os.getenv("MEMORY_MMR_ENABLED", "false").lower() in {
            "1", "true", "yes", "on"
        }
        self.mmr_lambda = min(
            1.0, max(0.0, env_float("MEMORY_MMR_LAMBDA", DEFAULT_MMR_LAMBDA))
        )
        self.source_weights = {"global": 1.0, "workspace": 1.0, "session": 1.0}
        self._lock = threading.RLock()
        self._flush_lock = threading.Lock()
        self._last_flush_content = ""
        self._flush_count = 0

    @staticmethod
    def _workspace_key(path: Path) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", path.name.lower()).strip("-") or "workspace"
        digest = hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:8]
        return f"{slug}-{digest}"

    @classmethod
    def prune_orphaned_scopes(
        cls,
        root_dir: str | Path,
        valid_workspace_paths: Iterable[str | Path],
    ) -> dict:
        """Remove managed scope indexes with no remaining task/project owner.

        Scope directory names are derived from absolute paths and cannot be
        reversed.  Callers therefore provide every durable path that is still
        valid; unknown directories and symlinks are never removed.
        """
        root = Path(root_dir).expanduser().resolve()
        if not root.is_dir():
            return {
                "removed_scopes": [],
                "removed_bytes": 0,
                "preserved_scopes": [],
                "errors": [],
            }
        valid_names = {
            cls._workspace_key(Path(path).expanduser().resolve())
            for path in valid_workspace_paths
            if str(path or "").strip()
        }
        removed_scopes: list[str] = []
        preserved_scopes: list[str] = []
        errors: list[dict[str, str]] = []
        removed_bytes = 0
        for candidate in sorted(root.iterdir(), key=lambda path: path.name):
            if candidate.name in valid_names:
                preserved_scopes.append(candidate.name)
                continue
            if (
                candidate.is_symlink()
                or not candidate.is_dir()
                or not re.fullmatch(r".+-[0-9a-f]{8}", candidate.name)
            ):
                continue
            managed_scope = (
                (candidate / "index.sqlite").is_file()
                or (candidate / "sessions").is_dir()
                or (candidate / "MEMORY.md").is_file()
            )
            if not managed_scope:
                continue
            try:
                scope_bytes = sum(
                    path.stat().st_size
                    for path in candidate.rglob("*")
                    if path.is_file() and not path.is_symlink()
                )
                shutil.rmtree(candidate)
                removed_scopes.append(candidate.name)
                removed_bytes += scope_bytes
            except OSError as exc:
                errors.append({"scope": candidate.name, "error": str(exc)})
        return {
            "removed_scopes": removed_scopes,
            "removed_bytes": removed_bytes,
            "preserved_scopes": preserved_scopes,
            "errors": errors,
        }

    @staticmethod
    def is_greeting(text: str) -> bool:
        greetings = {
            "hi", "hey", "hello", "howdy", "continue", "start", "begin", "go",
            "good morning", "good afternoon", "good evening", "what's up", "whats up", "sup",
        }
        return text.lower().strip().rstrip(".!?,") in greetings

    @classmethod
    def normalize_query(cls, raw_query: str) -> str:
        query = str(raw_query or "").strip()
        if not query or len(query) < 20 or cls.is_greeting(query):
            return GREETING_FALLBACK_QUERY
        return query

    def initial_context(self, raw_query: str) -> str:
        if not self.enabled:
            return ""
        results = self.search(
            self.normalize_query(raw_query),
            limit=INITIAL_SEARCH_LIMIT,
            min_score=0.0,
        )
        return self.format_memory_context(results)

    def search(
        self,
        query: str,
        *,
        limit: int = INITIAL_SEARCH_LIMIT,
        min_score: Optional[float] = None,
    ) -> list[MemorySearchResult]:
        """Run Grok's FTS5 BM25 + optional vector KNN hybrid search."""
        if not self.enabled or not str(query or "").strip() or limit <= 0:
            return []
        with self._lock:
            self._sync_index()
            connection = self._connect()
            try:
                results = self._hybrid_search(
                    connection,
                    str(query).strip(),
                    max_results=int(limit),
                    min_score=self.min_score if min_score is None else float(min_score),
                )
                now = int(datetime.now(timezone.utc).timestamp())
                connection.executemany(
                    "UPDATE chunks SET access_count = access_count + 1, last_accessed = ? WHERE id = ?",
                    [(now, result.chunk_id) for result in results],
                )
                connection.commit()
                return results
            finally:
                connection.close()

    def _hybrid_search(
        self,
        connection: sqlite3.Connection,
        query: str,
        *,
        max_results: int,
        min_score: float,
    ) -> list[MemorySearchResult]:
        candidate_limit = max_results * 3
        fts_results = self._search_fts(connection, query, candidate_limit)
        evergreen = self._search_fts(
            connection,
            query,
            candidate_limit,
            sources=("global", "workspace"),
        )
        known = {chunk_id for chunk_id, _rank in fts_results}
        fts_results.extend(item for item in evergreen if item[0] not in known)

        query_vector: list[float] = []
        if self.embedding_provider.available:
            try:
                query_vector = self.embedding_provider.embed(query)
            except Exception:
                query_vector = []
        vector_results = self._vector_search(connection, query_vector, candidate_limit)

        fts_scores: dict[str, float] = {}
        if fts_results:
            ranks = [rank for _chunk_id, rank in fts_results]
            minimum, maximum = min(ranks), max(ranks)
            span = max(maximum - minimum, float.fromhex("0x1.0p-52"))
            for chunk_id, rank in fts_results:
                fts_scores[chunk_id] = 1.0 - (rank - minimum) / span

        vector_scores = {
            chunk_id: min(1.0, max(0.0, 1.0 - distance / 2.0))
            for chunk_id, distance in vector_results
        }
        identifiers = set(fts_scores) | set(vector_scores)
        base_scores: dict[str, float] = {}
        for chunk_id in identifiers:
            text_score = fts_scores.get(chunk_id, 0.0)
            vector_score = vector_scores.get(chunk_id, 0.0)
            if text_score > 0.0 and vector_score > 0.0:
                hybrid = self.text_weight * text_score + self.vector_weight * vector_score
                score = max(text_score, hybrid)
            elif text_score > 0.0:
                score = text_score
            else:
                score = self.vector_weight * vector_score
            base_scores[chunk_id] = score

        now = int(datetime.now(timezone.utc).timestamp())
        ranked: list[tuple[float, MemorySearchResult]] = []
        for chunk_id, base_score in base_scores.items():
            row = connection.execute(
                "SELECT path, start_line, end_line, text, source, created_at, access_count "
                "FROM chunks WHERE id = ?",
                (chunk_id,),
            ).fetchone()
            if not row:
                continue
            path, start, end, text, source, created_at, access_count = row
            if self._is_content_free(text, source):
                continue
            decay = self._temporal_decay(source, int(created_at), now)
            source_weight = self.source_weights.get(str(source), 1.0)
            access_boost = 1.0 + math.log1p(int(access_count)) * 0.05
            raw_score = base_score * decay * source_weight * access_boost
            display_score = min(1.0, max(0.0, raw_score))
            if display_score < min_score:
                continue
            ranked.append(
                (
                    raw_score,
                    MemorySearchResult(
                        chunk_id=chunk_id,
                        path=str(path),
                        start_line=int(start),
                        end_line=int(end),
                        score=display_score,
                        snippet=str(text),
                        source=str(source),
                        created_at=int(created_at),
                    ),
                )
            )
        ranked.sort(key=lambda item: item[0], reverse=True)
        if self.mmr_enabled:
            ranked = self._mmr_rerank(ranked)
        return [result for _score, result in ranked[:max_results]]

    @staticmethod
    def extract_keywords(query: str) -> list[str]:
        lowered = query.lower()
        words = re.split(r"[^\w]+", lowered, flags=re.UNICODE)
        seen: set[str] = set()
        keywords = []
        for word in words:
            if (
                len(word) < 2
                or word in _STOP_WORDS
                or word.isnumeric()
                or word in seen
            ):
                continue
            seen.add(word)
            keywords.append(word)
        return keywords

    def _search_fts(
        self,
        connection: sqlite3.Connection,
        query: str,
        limit: int,
        sources: tuple[str, ...] = (),
    ) -> list[tuple[str, float]]:
        keywords = self.extract_keywords(query)
        if not keywords:
            return []
        fts_query = " OR ".join('"' + word.replace('"', '""') + '"' for word in keywords)
        if sources:
            placeholders = ",".join("?" for _ in sources)
            sql = (
                "SELECT c.id, bm25(chunks_fts) FROM chunks_fts "
                "JOIN chunks c ON chunks_fts.rowid = c.rowid "
                f"WHERE chunks_fts MATCH ? AND c.source IN ({placeholders}) "
                "ORDER BY bm25(chunks_fts) LIMIT ?"
            )
            parameters: tuple[Any, ...] = (fts_query, *sources, limit)
        else:
            sql = (
                "SELECT c.id, bm25(chunks_fts) FROM chunks_fts "
                "JOIN chunks c ON chunks_fts.rowid = c.rowid "
                "WHERE chunks_fts MATCH ? ORDER BY bm25(chunks_fts) LIMIT ?"
            )
            parameters = (fts_query, limit)
        try:
            matches = [
                (str(chunk_id), float(rank))
                for chunk_id, rank in connection.execute(sql, parameters).fetchall()
            ]
        except sqlite3.OperationalError:
            matches = []

        # unicode61 treats a continuous Chinese sentence as one token. Preserve
        # FTS5 for its normal ranking, then add literal CJK substring matches so
        # a query such as "赛车游戏" can find a longer stored user request.
        known = {chunk_id for chunk_id, _rank in matches}
        for term in self._cjk_search_terms(query):
            if sources:
                placeholders = ",".join("?" for _ in sources)
                substring_sql = (
                    "SELECT id FROM chunks WHERE instr(text, ?) > 0 "
                    f"AND source IN ({placeholders}) LIMIT ?"
                )
                substring_parameters: tuple[Any, ...] = (
                    term,
                    *sources,
                    limit,
                )
            else:
                substring_sql = (
                    "SELECT id FROM chunks WHERE instr(text, ?) > 0 LIMIT ?"
                )
                substring_parameters = (term, limit)
            for (chunk_id,) in connection.execute(
                substring_sql, substring_parameters
            ).fetchall():
                identifier = str(chunk_id)
                if identifier not in known:
                    # Lower BM25 ranks sort first; longer literal matches win.
                    matches.append((identifier, -float(len(term))))
                    known.add(identifier)
        return matches

    @staticmethod
    def _cjk_search_terms(query: str) -> list[str]:
        """Extract literal Chinese terms for the FTS5 unicode61 fallback."""
        terms = []
        seen = set()
        for run in re.findall(r"[\u4e00-\u9fff]{2,}", str(query or "")):
            candidates = [run]
            if len(run) > 4:
                candidates.extend(
                    run[index : index + 4]
                    for index in range(0, len(run) - 3)
                )
            for candidate in candidates:
                if candidate not in seen:
                    seen.add(candidate)
                    terms.append(candidate)
        return terms

    @staticmethod
    def _vector_search(
        connection: sqlite3.Connection, query_vector: list[float], limit: int
    ) -> list[tuple[str, float]]:
        if not query_vector:
            return []
        neighbors = []
        for chunk_id, raw_embedding in connection.execute(
            "SELECT chunk_id, embedding FROM chunk_embeddings"
        ):
            try:
                embedding = [float(value) for value in json.loads(raw_embedding)]
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            neighbors.append((str(chunk_id), l2_distance(query_vector, embedding)))
        neighbors.sort(key=lambda item: item[1])
        return neighbors[:limit]

    def _temporal_decay(self, source: str, created_at: int, now: int) -> float:
        if source in {"global", "workspace"} or self.half_life_days <= 0:
            return 1.0
        age_days = max(0.0, (now - max(0, created_at)) / 86_400.0)
        return math.exp(-(math.log(2.0) / self.half_life_days) * age_days)

    def _mmr_rerank(
        self, ranked: list[tuple[float, MemorySearchResult]]
    ) -> list[tuple[float, MemorySearchResult]]:
        if len(ranked) <= 1 or self.mmr_lambda == 1.0:
            return ranked
        scores = [item[0] for item in ranked]
        minimum, maximum = min(scores), max(scores)
        span = max(maximum - minimum, float.fromhex("0x1.0p-52"))
        tokens = [self._mmr_tokens(item[1].snippet.lower()) for item in ranked]
        selected: list[int] = []
        remaining = list(range(len(ranked)))
        while remaining:
            best_position = 0
            best_score = -math.inf
            for position, candidate in enumerate(remaining):
                normalized = (scores[candidate] - minimum) / span
                max_similarity = max(
                    (
                        self._jaccard(tokens[candidate], tokens[chosen])
                        for chosen in selected
                    ),
                    default=0.0,
                )
                mmr_score = (
                    self.mmr_lambda * normalized
                    - (1.0 - self.mmr_lambda) * max_similarity
                )
                current_best = remaining[best_position]
                if mmr_score > best_score or (
                    mmr_score == best_score and scores[candidate] > scores[current_best]
                ):
                    best_position = position
                    best_score = mmr_score
            selected.append(remaining.pop(best_position))
        return [ranked[index] for index in selected]

    @staticmethod
    def _mmr_tokens(text: str) -> set[str]:
        return {word for word in re.split(r"[^\w]+", text, flags=re.UNICODE) if word}

    @staticmethod
    def _jaccard(left: set[str], right: set[str]) -> float:
        if not left and not right:
            return 1.0
        if not left or not right:
            return 0.0
        return len(left & right) / len(left | right)

    @staticmethod
    def _is_content_free(text: str, source: str) -> bool:
        without_comments = re.sub(r"<!--[\s\S]*?-->", "", str(text or ""))
        substantive = [
            line
            for line in without_comments.splitlines()
            if line.strip() and not re.match(r"^\s*#{1,6}(?:\s|$)", line)
        ]
        return not substantive

    @staticmethod
    def format_memory_context(results: Iterable[MemorySearchResult]) -> str:
        items = list(results)
        if not items:
            return ""
        parts = [MEMORY_CONTEXT_OPEN_TAG, "## Relevant Memory from Past Sessions", ""]
        now = int(datetime.now(timezone.utc).timestamp())
        for index, result in enumerate(items, 1):
            snippet = result.snippet[:SNIPPET_MAX_CHARS]
            if len(result.snippet) > SNIPPET_MAX_CHARS:
                snippet += "..."
            parts.append(
                f"### Result {index} (score: {result.score:.2f}, source: {result.source})"
            )
            parts.append(
                f"**File:** {result.path} (lines {result.start_line}-{result.end_line})"
            )
            if result.source == "session" and result.created_at:
                age_days = max(0, (now - result.created_at) // 86_400)
                if age_days >= 7:
                    parts.append(f"**Stale ({age_days} days old):** verify before relying on it.")
            parts.extend(["```", snippet, "```", ""])
        parts.append(MEMORY_CONTEXT_CLOSE_TAG)
        return "\n".join(parts)

    @staticmethod
    def has_memory_context(system_prompt: str) -> bool:
        return MEMORY_CONTEXT_OPEN_TAG in str(system_prompt or "")

    @staticmethod
    def append_context(system_prompt: str, memory_context: str) -> str:
        if not memory_context or MemoryStore.has_memory_context(system_prompt):
            return system_prompt
        return f"{system_prompt.rstrip()}\n\n{memory_context}\n"

    @staticmethod
    def should_flush(
        total_tokens: int,
        context_window: int,
        compact_threshold_percent: int,
        *,
        soft_threshold_tokens: int = FLUSH_SOFT_THRESHOLD_TOKENS,
    ) -> bool:
        threshold = max(1, int(context_window * compact_threshold_percent / 100))
        return int(total_tokens) >= max(0, threshold - int(soft_threshold_tokens))

    def flush(
        self,
        messages: Iterable[Any],
        sampler: Callable[[list[dict[str, str]]], str],
        *,
        session_id: str,
        trigger: str = "pre_compaction",
        max_write_chars: int = MAX_FLUSH_WRITE_CHARS,
    ) -> MemoryFlushResult:
        if not self.enabled:
            return MemoryFlushResult("disabled")
        if not self._flush_lock.acquire(blocking=False):
            return MemoryFlushResult("busy")
        try:
            recent = self.select_flush_window(messages, recent_message_count=20)
            if not recent:
                return MemoryFlushResult("nothing_to_store")
            system_prompt = FLUSH_SYSTEM_PROMPT
            if self._flush_count > 0 and self._last_flush_content:
                system_prompt = FLUSH_DELTA_SYSTEM_PROMPT + self._last_flush_content
            request = [{"role": "system", "content": system_prompt}, *recent]
            request.append(
                {
                    "role": "user",
                    "content": "Now write the memory summary as described in the system prompt.",
                }
            )
            try:
                response = str(sampler(request) or "").strip()
            except Exception as exc:
                self._flush_count += 1
                return MemoryFlushResult("error", error=str(exc))
            self._flush_count += 1
            if not response or self._is_no_reply(response):
                return MemoryFlushResult("nothing_to_store")
            truncated = len(response) > max_write_chars
            content = response[:max_write_chars]
            if not re.search(r"(?m)^##\s+\S", content):
                return MemoryFlushResult("rejected", error="flush response lacks ## headers")
            if self._is_duplicate(content):
                self._last_flush_content = content
                return MemoryFlushResult("duplicate", content=content, truncated=truncated)
            path = self.write_daily_log(
                trigger=trigger,
                session_id=session_id,
                content=content,
                append=True,
            )
            self.reindex()
            self._last_flush_content = content
            return MemoryFlushResult(
                "written", content=content, path=str(path), truncated=truncated
            )
        finally:
            self._flush_lock.release()

    @classmethod
    def select_flush_window(
        cls, messages: Iterable[Any], *, recent_message_count: int = 20
    ) -> list[dict[str, str]]:
        normalized = [item for item in (cls._normalize_message(m) for m in messages) if item]
        normalized = [item for item in normalized if item["role"] != "system"]
        start = max(0, len(normalized) - max(0, int(recent_message_count)))
        while start > 0 and normalized[start]["role"] != "user":
            start -= 1
        return normalized[start:]

    @staticmethod
    def _normalize_message(message: Any) -> Optional[dict[str, str]]:
        if isinstance(message, dict):
            role = str(message.get("role", ""))
            content = message.get("content", "")
        else:
            kind = str(getattr(message, "type", "") or message.__class__.__name__).lower()
            role = (
                "user" if "human" in kind or kind == "user" else
                "assistant" if "ai" in kind or "assistant" in kind else
                "tool" if "tool" in kind else
                "system" if "system" in kind else ""
            )
            content = getattr(message, "content", "")
        if isinstance(content, list):
            content = "\n".join(
                str(part.get("text", "") if isinstance(part, dict) else part)
                for part in content
            )
        text = str(content or "").strip()
        return {"role": role, "content": text} if role and text else None

    def write_daily_log(
        self, *, trigger: str, session_id: str, content: str, append: bool
    ) -> Path:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        slug = re.sub(r"[^a-z0-9]+", "-", trigger.lower()).strip("-") or "flush"
        sid8 = re.sub(r"[^a-zA-Z0-9]", "", session_id)[:8] or "session"
        path = self.sessions_dir / f"{date}-{slug}-{sid8}.md"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        if append and path.exists():
            timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
            with path.open("a", encoding="utf-8") as handle:
                handle.write(f"\n\n---\n\n<!-- flush {timestamp} -->\n\n{content}")
        else:
            path.write_text(content, encoding="utf-8")
        return path

    def upsert_conversation_record(
        self,
        *,
        session_id: str,
        title: str,
        user_requests: Iterable[str],
        summary: str = "",
    ) -> Path:
        """Index durable user requests alongside the compacted session summary.

        Compaction summaries deliberately omit routine detail. Original user
        requests are retained separately so retrieval can answer questions
        about earlier requirements after the live graph context is compacted.
        """
        sid8 = re.sub(r"[^a-zA-Z0-9]", "", str(session_id))[:8] or "session"
        path = self.sessions_dir / f"conversation-{sid8}.md"
        requests = [str(item).strip() for item in user_requests if str(item).strip()]
        lines = ["# Conversation Record", "", f"**Title:** {str(title).strip()}", ""]
        for index, request in enumerate(requests, 1):
            lines.extend([f"## User Request {index}", "", request, ""])
        if summary.strip():
            lines.extend(["## Latest Compaction Summary", "", summary.strip(), ""])
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines), encoding="utf-8")
        self.reindex()
        return path

    def delete_conversation_record(self, session_id: str) -> bool:
        """Remove one task's long-term records without affecting sibling sessions."""
        sid8 = re.sub(r"[^a-zA-Z0-9]", "", str(session_id))[:8]
        if not sid8:
            return False
        removed = False
        if self.sessions_dir.exists():
            for path in self.sessions_dir.glob(f"*-{sid8}.md"):
                path.unlink(missing_ok=True)
                removed = True
            record = self.sessions_dir / f"conversation-{sid8}.md"
            if record.exists():
                record.unlink()
                removed = True
        # Reindex even when the Markdown file was already gone: an older
        # interrupted deletion may still have index rows for that path.
        self.reindex()
        return removed

    def purge_scope(self) -> None:
        """Permanently remove this workspace/project's session memory and index."""
        with self._lock:
            shutil.rmtree(self.workspace_dir, ignore_errors=True)

    def reindex(self) -> None:
        with self._lock:
            connection = self._connect()
            try:
                # Multiple desktop conversations can share a project memory
                # database. Serialize the read-check-write reindex pass across
                # their independent MemoryStore instances.
                connection.execute("BEGIN IMMEDIATE")
                may_record_signature = False
                signature = ""
                if self.embedding_provider.available:
                    signature = self._embedding_signature()
                    metadata = connection.execute(
                        "SELECT value FROM index_metadata "
                        "WHERE key = 'embedding_signature'"
                    ).fetchone()
                    chunk_count = int(
                        connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
                    )
                    may_record_signature = (
                        chunk_count == 0
                        or (metadata is not None and str(metadata[0]) == signature)
                    )
                current_paths = {str(path.relative_to(self.global_dir)): path for path in self._memory_files()}
                indexed_paths = {
                    str(row[0]) for row in connection.execute("SELECT path FROM indexed_files")
                }
                for relative in indexed_paths - set(current_paths):
                    self._remove_indexed_file(connection, relative)
                for relative, path in current_paths.items():
                    self._reindex_file(connection, path, relative)
                if may_record_signature:
                    chunk_count = int(
                        connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
                    )
                    vector_count = int(
                        connection.execute(
                            "SELECT COUNT(*) FROM chunk_embeddings"
                        ).fetchone()[0]
                    )
                    if chunk_count == vector_count:
                        connection.execute(
                            "INSERT OR REPLACE INTO index_metadata(key,value) "
                            "VALUES(?,?)",
                            ("embedding_signature", signature),
                        )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

    def _sync_index(self) -> None:
        connection = self._connect()
        try:
            indexed = {
                str(path): int(mtime)
                for path, mtime in connection.execute(
                    "SELECT path, mtime_ns FROM indexed_files"
                )
            }
        finally:
            connection.close()
        current = {
            str(path.relative_to(self.global_dir)): int(path.stat().st_mtime_ns)
            for path in self._memory_files()
        }
        if indexed != current:
            self.reindex()
        self._sync_embeddings()

    def _sync_embeddings(self) -> None:
        """Backfill vectors and rebuild them when the provider signature changes."""
        if not self.embedding_provider.available:
            return

        signature = self._embedding_signature()
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT value FROM index_metadata WHERE key = 'embedding_signature'"
            ).fetchone()
            stored_signature = str(row[0]) if row else ""
            replace_all = stored_signature != signature
            if replace_all:
                rows = connection.execute(
                    "SELECT id, text FROM chunks ORDER BY rowid"
                ).fetchall()
                # Vectors from another model or dimension must never be mixed with
                # the current query vector. Until rebuilding succeeds, FTS remains.
                connection.execute("DELETE FROM chunk_embeddings")
                connection.execute(
                    "DELETE FROM index_metadata WHERE key = 'embedding_signature'"
                )
                connection.commit()
            else:
                rows = connection.execute(
                    "SELECT c.id, c.text FROM chunks c "
                    "LEFT JOIN chunk_embeddings e ON e.chunk_id = c.id "
                    "WHERE e.chunk_id IS NULL ORDER BY c.rowid"
                ).fetchall()
        finally:
            connection.close()

        if not rows:
            if replace_all:
                self._save_embedding_signature(signature)
            return

        try:
            vectors = self.embedding_provider.embed_batch(
                [str(text) for _chunk_id, text in rows]
            )
        except Exception:
            return
        if len(vectors) != len(rows) or any(
            len(vector) != self.embedding_provider.dimensions for vector in vectors
        ):
            return

        connection = self._connect()
        try:
            connection.executemany(
                "INSERT OR REPLACE INTO chunk_embeddings(chunk_id,embedding) VALUES(?,?)",
                [
                    (
                        str(chunk_id),
                        json.dumps(vector, separators=(",", ":")),
                    )
                    for (chunk_id, _text), vector in zip(rows, vectors)
                ],
            )
            connection.execute(
                "INSERT OR REPLACE INTO index_metadata(key,value) VALUES(?,?)",
                ("embedding_signature", self._embedding_signature()),
            )
            connection.commit()
        finally:
            connection.close()

    def _embedding_signature(self) -> str:
        status = self.embedding_provider.status()
        return json.dumps(
            {
                "provider": status.get("provider", ""),
                "model": status.get("model", ""),
                "dimension": status.get("dimension", 0),
                "api_base": status.get("api_base", ""),
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    def _save_embedding_signature(self, signature: str) -> None:
        connection = self._connect()
        try:
            connection.execute(
                "INSERT OR REPLACE INTO index_metadata(key,value) VALUES(?,?)",
                ("embedding_signature", signature),
            )
            connection.commit()
        finally:
            connection.close()

    def _connect(self) -> sqlite3.Connection:
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(self.index_path), timeout=30)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS chunks (
                rowid INTEGER PRIMARY KEY AUTOINCREMENT,
                id TEXT UNIQUE NOT NULL,
                path TEXT NOT NULL,
                start_line INTEGER NOT NULL,
                end_line INTEGER NOT NULL,
                text TEXT NOT NULL,
                hash TEXT NOT NULL,
                source TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                access_count INTEGER DEFAULT 0,
                last_accessed INTEGER
            );
            CREATE INDEX IF NOT EXISTS idx_chunks_path ON chunks(path);
            CREATE INDEX IF NOT EXISTS idx_chunks_hash ON chunks(hash);
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(text, content='');
            CREATE TABLE IF NOT EXISTS chunk_embeddings (
                chunk_id TEXT PRIMARY KEY,
                embedding TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS indexed_files (
                path TEXT PRIMARY KEY,
                mtime_ns INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS index_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        return connection

    def _reindex_file(
        self, connection: sqlite3.Connection, path: Path, relative: str
    ) -> None:
        mtime_ns = int(path.stat().st_mtime_ns)
        existing = connection.execute(
            "SELECT mtime_ns FROM indexed_files WHERE path = ?", (relative,)
        ).fetchone()
        if existing and int(existing[0]) == mtime_ns:
            return
        source = (
            "global" if path == self.global_dir / "MEMORY.md" else
            "workspace" if path == self.workspace_dir / "MEMORY.md" else "session"
        )
        content = path.read_text(encoding="utf-8", errors="replace")
        chunks = self.chunk_markdown(
            content,
            max_chars=self.max_chunk_chars,
            overlap_chars=self.chunk_overlap_chars,
        )
        existing_chunks = {
            str(row[1]): {
                "rowid": int(row[0]),
                "hash": str(row[2]),
                "text": str(row[3]),
            }
            for row in connection.execute(
                "SELECT rowid,id,hash,text FROM chunks WHERE path = ?", (relative,)
            )
        }
        prepared = []
        changed_texts = []
        for index, chunk in enumerate(chunks):
            digest = hashlib.sha256(chunk.text.encode("utf-8")).hexdigest()
            # The relative path can be reused by different project/session
            # scopes in legacy indexes. Make IDs unambiguous even when an old
            # database is migrated or concurrent reindexing is retried.
            chunk_id = f"{hashlib.sha256(relative.encode('utf-8')).hexdigest()[:16]}:{index}"
            changed = chunk_id not in existing_chunks or existing_chunks[chunk_id]["hash"] != digest
            prepared.append((chunk_id, chunk, digest, changed))
            if changed:
                changed_texts.append(chunk.text)

        embeddings: list[list[float]] = []
        if changed_texts and self.embedding_provider.available:
            try:
                embeddings = self.embedding_provider.embed_batch(changed_texts)
            except Exception:
                embeddings = []
        now = int(datetime.now(timezone.utc).timestamp())
        seen: set[str] = set()
        embedding_index = 0
        for chunk_id, chunk, digest, changed in prepared:
            seen.add(chunk_id)
            old = existing_chunks.get(chunk_id)
            if not changed:
                continue
            if old:
                rowid = old["rowid"]
                connection.execute(
                    "UPDATE chunks SET text=?,hash=?,start_line=?,end_line=?,source=?,updated_at=? WHERE id=?",
                    (
                        chunk.text,
                        digest,
                        chunk.start_line,
                        chunk.end_line,
                        source,
                        now,
                        chunk_id,
                    ),
                )
                connection.execute(
                    "INSERT INTO chunks_fts(chunks_fts,rowid,text) VALUES('delete',?,?)",
                    (rowid, old["text"]),
                )
                connection.execute(
                    "INSERT INTO chunks_fts(rowid,text) VALUES(?,?)", (rowid, chunk.text)
                )
                connection.execute(
                    "DELETE FROM chunk_embeddings WHERE chunk_id = ?", (chunk_id,)
                )
            else:
                cursor = connection.execute(
                    "INSERT INTO chunks(id,path,start_line,end_line,text,hash,source,created_at,updated_at) "
                    "VALUES(?,?,?,?,?,?,?,?,?)",
                    (
                        chunk_id,
                        relative,
                        chunk.start_line,
                        chunk.end_line,
                        chunk.text,
                        digest,
                        source,
                        now,
                        now,
                    ),
                )
                rowid = int(cursor.lastrowid)
                connection.execute(
                    "INSERT INTO chunks_fts(rowid,text) VALUES(?,?)", (rowid, chunk.text)
                )
            if embedding_index < len(embeddings):
                connection.execute(
                    "INSERT OR REPLACE INTO chunk_embeddings(chunk_id,embedding) VALUES(?,?)",
                    (
                        chunk_id,
                        json.dumps(embeddings[embedding_index], separators=(",", ":")),
                    ),
                )
            embedding_index += 1

        for old_id, old in existing_chunks.items():
            if old_id in seen:
                continue
            connection.execute(
                "INSERT INTO chunks_fts(chunks_fts,rowid,text) VALUES('delete',?,?)",
                (old["rowid"], old["text"]),
            )
            connection.execute(
                "DELETE FROM chunk_embeddings WHERE chunk_id = ?", (old_id,)
            )
            connection.execute("DELETE FROM chunks WHERE id = ?", (old_id,))
        connection.execute(
            "INSERT OR REPLACE INTO indexed_files(path,mtime_ns) VALUES(?,?)",
            (relative, mtime_ns),
        )

    @staticmethod
    def _remove_indexed_file(connection: sqlite3.Connection, relative: str) -> None:
        rows = connection.execute(
            "SELECT rowid,id,text FROM chunks WHERE path = ?", (relative,)
        ).fetchall()
        for rowid, chunk_id, text in rows:
            connection.execute(
                "INSERT INTO chunks_fts(chunks_fts,rowid,text) VALUES('delete',?,?)",
                (rowid, text),
            )
            connection.execute(
                "DELETE FROM chunk_embeddings WHERE chunk_id = ?", (chunk_id,)
            )
        connection.execute("DELETE FROM chunks WHERE path = ?", (relative,))
        connection.execute("DELETE FROM indexed_files WHERE path = ?", (relative,))

    def _memory_files(self) -> list[Path]:
        paths = [self.workspace_dir / "MEMORY.md"]
        if self.include_global:
            paths.insert(0, self.global_dir / "MEMORY.md")
        if self.sessions_dir.exists():
            paths.extend(sorted(self.sessions_dir.glob("*.md")))
        return [path for path in paths if path.is_file()]

    @classmethod
    def chunk_markdown(
        cls,
        content: str,
        *,
        max_chars: int = MAX_CHUNK_CHARS,
        overlap_chars: int = CHUNK_OVERLAP_CHARS,
    ) -> list[_Chunk]:
        if not content:
            return []
        lines = content.splitlines()
        if not lines:
            return []
        if len(content) <= max_chars:
            return [_Chunk(content, 0, len(lines))]

        sections: list[tuple[list[str], int, str]] = []
        current: list[str] = []
        current_start = 0
        header_stack: list[tuple[int, str]] = []
        for index, line in enumerate(lines):
            level = cls._header_level(line)
            if level is not None:
                if current:
                    context = cls._header_context(header_stack)
                    sections.append((current, current_start, context))
                    current = []
                current_start = index
                while header_stack and header_stack[-1][0] >= level:
                    header_stack.pop()
                header_stack.append((level, line))
            current.append(line)
        if current:
            sections.append((current, current_start, cls._header_context(header_stack)))

        chunks: list[_Chunk] = []
        for section_lines, start, context in sections:
            section_text = "\n".join(section_lines)
            if len(section_text) <= max_chars:
                chunks.append(
                    _Chunk(cls._add_header_context(context, section_text), start, start + len(section_lines))
                )
                continue
            chunks.extend(
                cls._split_large_section(
                    section_lines,
                    start,
                    context,
                    max_chars,
                    overlap_chars,
                )
            )
        return chunks

    @classmethod
    def _split_large_section(
        cls,
        lines: list[str],
        section_start: int,
        context: str,
        max_chars: int,
        overlap_chars: int,
    ) -> list[_Chunk]:
        chunks: list[_Chunk] = []
        current = ""
        current_start = section_start
        line_offset = 0
        for index, line in enumerate(lines):
            if not line.strip() and current and len(current) + len(line) > max_chars:
                flushed = current.strip()
                chunks.append(
                    _Chunk(
                        cls._add_header_context(context, flushed),
                        current_start,
                        section_start + index,
                    )
                )
                current = flushed[-overlap_chars:] if overlap_chars > 0 else ""
                current_start = section_start + index + 1
                line_offset = index + 1
                continue
            current = f"{current}\n{line}" if current else line
            if len(current) > max_chars and index > line_offset:
                split_at = current.rfind("\n")
                keep, remainder = current[:split_at], current[split_at + 1 :]
                chunks.append(
                    _Chunk(
                        cls._add_header_context(context, keep.strip()),
                        current_start,
                        section_start + index,
                    )
                )
                current = remainder
                current_start = section_start + index
                line_offset = index
        if current.strip():
            chunks.append(
                _Chunk(
                    cls._add_header_context(context, current.strip()),
                    current_start,
                    section_start + len(lines),
                )
            )
        return chunks

    @staticmethod
    def _header_level(line: str) -> Optional[int]:
        stripped = line.lstrip()
        match = re.match(r"^(#+)(?:\s|$)", stripped)
        return len(match.group(1)) if match else None

    @staticmethod
    def _header_context(stack: list[tuple[int, str]]) -> str:
        if len(stack) <= 1:
            return ""
        return " > ".join(text.strip() for _level, text in stack[:-1])

    @staticmethod
    def _add_header_context(context: str, text: str) -> str:
        return f"[Context: {context}]\n\n{text}" if context else text

    def _is_duplicate(self, content: str) -> bool:
        with self._lock:
            self._sync_index()
            connection = self._connect()
            try:
                digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
                exact = connection.execute(
                    "SELECT 1 FROM chunks WHERE hash = ? LIMIT 1", (digest,)
                ).fetchone()
                if exact:
                    return True
                if not self.embedding_provider.available:
                    return False
                try:
                    vector = self.embedding_provider.embed(content)
                except Exception:
                    return False
                neighbors = self._vector_search(connection, vector, 3)
                return any(
                    (1.0 - distance / 2.0) > SEMANTIC_DEDUP_THRESHOLD
                    for _chunk_id, distance in neighbors
                )
            finally:
                connection.close()

    @staticmethod
    def _is_no_reply(text: str) -> bool:
        return bool(re.fullmatch(r"(?is)\s*(?:NO[_ ]?REPLY|NOTHING_TO_STORE)[.!]?\s*", text))
