"""Full-replace context compaction shared by every OS-Agent surface."""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional, Sequence

from langchain_core.messages import BaseMessage

from agent.core.env_utils import env_int


SummarySampler = Callable[[str], str]
ProgressCallback = Callable[[str, str], None]

DEFAULT_TRIGGER_PERCENT = 85
DEFAULT_PREFIRE_LEAD_PERCENT = 10
DEFAULT_SUMMARY_RESERVE_TOKENS = 32_768
MIN_SUMMARY_SEED_CHARS = 500


@dataclass(frozen=True)
class ContextPolicy:
    """Configuration for one model context window."""

    context_window: int
    trigger_percent: int = DEFAULT_TRIGGER_PERCENT
    prefire_lead_percent: int = DEFAULT_PREFIRE_LEAD_PERCENT
    summary_reserve_tokens: int = DEFAULT_SUMMARY_RESERVE_TOKENS
    max_attempts: int = 3
    min_summary_chars: int = MIN_SUMMARY_SEED_CHARS
    two_pass_enabled: bool = True

    @property
    def trigger_tokens(self) -> int:
        return max(1, self.context_window * self.trigger_percent // 100)

    @property
    def prefire_tokens(self) -> int:
        percent = max(0, self.trigger_percent - self.prefire_lead_percent)
        return max(1, self.context_window * percent // 100)


@dataclass(frozen=True)
class ContextSnapshot:
    """The exact graph prompt state considered for compaction."""

    system_prompt: str
    messages: tuple[BaseMessage, ...]
    records: tuple[dict[str, Any], ...]
    transcript: str
    tokens: int
    context_window: int
    trigger_tokens: int
    step_count: int
    tool_tokens: int = 0

    @property
    def usage_percent(self) -> int:
        if self.context_window <= 0:
            return 0
        return min(100, self.tokens * 100 // self.context_window)


@dataclass(frozen=True)
class CompactionOutput:
    """A validated successor summary and its audit information."""

    success: bool
    status: str
    message: str
    summary: str = ""
    tokens_before: int = 0
    tokens_after: int = 0
    attempts: int = 0
    input_stage: str = "verbatim"
    two_pass_used: bool = False
    error: str = ""


@dataclass
class _PrefireCache:
    fingerprint: str
    prefix_len: int
    note: str


@dataclass
class _PrefireState:
    thread: Optional[threading.Thread] = None
    cache: Optional[_PrefireCache] = None
    lock: threading.Lock = field(default_factory=threading.Lock)


class ContextCompactor:
    """Estimate, prefire, summarize, validate, and replace model context."""

    def __init__(self, policy: ContextPolicy):
        self.policy = policy
        self._prefire = _PrefireState()

    @staticmethod
    def policy_from_runtime(
        max_tokens: int, _legacy_compress_at: Optional[int] = None
    ) -> ContextPolicy:
        """Resolve Grok's percentage-based compaction policy."""
        context_window = max(1, env_int("CONTEXT_WINDOW", max_tokens or 30_000))
        trigger_percent = env_int(
            "AUTO_COMPACT_THRESHOLD_PERCENT", DEFAULT_TRIGGER_PERCENT
        )
        return ContextPolicy(
            context_window=context_window,
            trigger_percent=max(1, min(100, trigger_percent)),
            prefire_lead_percent=max(
                0,
                env_int("COMPACTION_PREFIRE_LEAD_PERCENT", DEFAULT_PREFIRE_LEAD_PERCENT),
            ),
            max_attempts=max(1, env_int("COMPACTION_MAX_ATTEMPTS", 3)),
            min_summary_chars=max(
                1,
                env_int("COMPACTION_MIN_SUMMARY_CHARS", MIN_SUMMARY_SEED_CHARS),
            ),
            two_pass_enabled=os.getenv("COMPACTION_TWO_PASS", "true").lower()
            in {"1", "true", "yes", "on"},
        )

    def refresh_policy(
        self, max_tokens: int, _legacy_compress_at: Optional[int] = None
    ) -> None:
        """Apply settings changed at runtime and invalidate speculative state."""
        self.policy = self.policy_from_runtime(max_tokens)
        self.clear_prefire()

    @staticmethod
    def estimate_text_tokens(text: str) -> int:
        """Estimate mixed Chinese/English text with a small message overhead."""
        if not text:
            return 0
        chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
        without_chinese = re.sub(r"[\u4e00-\u9fff]", "", text)
        words = re.findall(r"\b[a-zA-Z]+\b", without_chinese)
        word_chars = sum(len(word) for word in words)
        other = max(0, len(text) - chinese - word_chars)
        return max(1, int(chinese * 1.7) + int(len(words) * 1.9) + int(other / 2.5))

    @classmethod
    def estimate_tool_tokens(cls, tools: Sequence[Mapping[str, Any]]) -> int:
        if not tools:
            return 0
        payload = json.dumps(list(tools), ensure_ascii=False, sort_keys=True, default=str)
        return cls.estimate_text_tokens(payload) + len(tools) * 12

    @staticmethod
    def _content_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, str):
                    parts.append(block)
                elif isinstance(block, Mapping):
                    block_type = str(block.get("type", ""))
                    if block_type in {"image", "image_url"}:
                        parts.append("[image attachment omitted from textual compaction]")
                    else:
                        parts.append(str(block.get("text") or block.get("content") or block))
                else:
                    parts.append(str(block))
            return "\n".join(parts)
        return str(content or "")

    @classmethod
    def message_record(cls, message: BaseMessage) -> dict[str, Any]:
        """Convert a LangChain message into a stable compaction record."""
        record: dict[str, Any] = {
            "role": str(getattr(message, "type", "message")),
            "content": cls._content_text(getattr(message, "content", "")),
        }
        name = getattr(message, "name", None)
        if name:
            record["name"] = str(name)
        tool_call_id = getattr(message, "tool_call_id", None)
        if tool_call_id:
            record["tool_call_id"] = str(tool_call_id)
        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls:
            record["tool_calls"] = tool_calls
        return record

    @classmethod
    def build_snapshot(
        cls,
        state: Mapping[str, Any],
        policy: ContextPolicy,
        tools: Sequence[Mapping[str, Any]] = (),
    ) -> ContextSnapshot:
        system_prompt = str(state.get("system_prompt", "") or "")
        messages = tuple(state.get("messages") or ())
        records = tuple(cls.message_record(message) for message in messages)
        transcript_records = ({"role": "system", "content": system_prompt}, *records)
        transcript = cls.format_transcript(transcript_records)
        tool_tokens = cls.estimate_tool_tokens(tools)
        tokens = cls.estimate_text_tokens(transcript) + tool_tokens
        return ContextSnapshot(
            system_prompt=system_prompt,
            messages=messages,
            records=records,
            transcript=transcript,
            tokens=tokens,
            context_window=policy.context_window,
            trigger_tokens=policy.trigger_tokens,
            step_count=int(state.get("step_count", 0) or 0),
            tool_tokens=tool_tokens,
        )

    @staticmethod
    def format_transcript(records: Sequence[Mapping[str, Any]]) -> str:
        sections = []
        for index, record in enumerate(records):
            role = str(record.get("role", "message")).upper()
            metadata = {
                key: value
                for key, value in record.items()
                if key not in {"role", "content"} and value not in (None, "", [], {})
            }
            header = f"## MESSAGE {index + 1} [{role}]"
            if metadata:
                header += "\n" + json.dumps(
                    metadata, ensure_ascii=False, sort_keys=True, default=str
                )
            sections.append(f"{header}\n{record.get('content', '')}")
        return "\n\n".join(sections)

    def should_compact(self, snapshot: ContextSnapshot) -> bool:
        return snapshot.tokens > self.policy.trigger_tokens

    def should_prefire(self, snapshot: ContextSnapshot) -> bool:
        return (
            self.policy.two_pass_enabled
            and len(snapshot.records) >= 4
            and self.policy.prefire_tokens < snapshot.tokens <= self.policy.trigger_tokens
        )

    @staticmethod
    def _fingerprint(records: Sequence[Mapping[str, Any]]) -> str:
        payload = json.dumps(
            list(records), ensure_ascii=False, sort_keys=True, default=str
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def start_prefire(self, snapshot: ContextSnapshot, sampler: SummarySampler) -> bool:
        """Speculatively summarize the oldest ~95% without mutating graph state."""
        if not self.should_prefire(snapshot):
            return False
        with self._prefire.lock:
            if self._prefire.cache is not None:
                return False
            if self._prefire.thread and self._prefire.thread.is_alive():
                return False
            split = max(1, int(len(snapshot.records) * 0.95))
            prefix = snapshot.records[:split]
            fingerprint = self._fingerprint(prefix)

            def worker() -> None:
                prompt = self._build_summary_prompt(
                    self.format_transcript(prefix),
                    two_pass_note=None,
                    pass_one=True,
                )
                try:
                    note = self.clean_summary(sampler(prompt))
                except Exception:
                    note = ""
                with self._prefire.lock:
                    if note:
                        self._prefire.cache = _PrefireCache(
                            fingerprint=fingerprint,
                            prefix_len=split,
                            note=note,
                        )
                    self._prefire.thread = None

            thread = threading.Thread(target=worker, daemon=True)
            self._prefire.thread = thread
            thread.start()
            return True

    def clear_prefire(self) -> None:
        with self._prefire.lock:
            self._prefire.cache = None

    def _take_valid_prefire(self, snapshot: ContextSnapshot) -> Optional[_PrefireCache]:
        with self._prefire.lock:
            thread = self._prefire.thread
        if thread and thread.is_alive():
            thread.join()
        with self._prefire.lock:
            cache = self._prefire.cache
            self._prefire.cache = None
        if not cache or cache.prefix_len > len(snapshot.records):
            return None
        if self._fingerprint(snapshot.records[: cache.prefix_len]) != cache.fingerprint:
            return None
        return cache

    @staticmethod
    def clean_summary(summary: str) -> str:
        """Remove scratchpad/control wrappers before seeding the successor turn."""
        result = str(summary or "")
        result = re.sub(r"<think>[\s\S]*?</think>", "", result, flags=re.IGNORECASE)
        result = re.sub(
            r"^\s*<analysis>[\s\S]*?</analysis>\s*",
            "",
            result,
            flags=re.IGNORECASE,
        )
        match = re.search(r"<summary>([\s\S]*?)</summary>", result, re.IGNORECASE)
        if match:
            result = "Summary:\n" + match.group(1).strip()
        result = re.sub(r"</?(?:summary|analysis|summary_request)>", "", result, flags=re.I)
        result = re.sub(r"\n{3,}", "\n\n", result)
        return result.strip()

    @staticmethod
    def _is_context_error(error: str) -> bool:
        lowered = error.lower()
        return any(
            marker in lowered
            for marker in (
                "context length",
                "context window",
                "maximum context",
                "too many tokens",
                "prompt is too long",
                "request too large",
            )
        )

    @staticmethod
    def _truncate_middle(text: str, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text
        keep = max(1, (max_chars - 80) // 2)
        return (
            text[:keep]
            + "\n...[middle truncated for compaction input budget]...\n"
            + text[-keep:]
        )

    def _fit_records(
        self, records: Sequence[Mapping[str, Any]], token_budget: int, lossy: bool
    ) -> str:
        fitted: list[dict[str, Any]] = []
        per_item_chars = 2_000 if lossy else 12_000
        for record in records:
            item = dict(record)
            role = str(item.get("role", ""))
            limit = 2_000 if role == "tool" else per_item_chars
            item["content"] = self._truncate_middle(str(item.get("content", "")), limit)
            fitted.append(item)

        while fitted:
            transcript = self.format_transcript(fitted)
            if self.estimate_text_tokens(transcript) <= token_budget:
                return transcript
            removable = next(
                (
                    index
                    for index, record in enumerate(fitted[:-2])
                    if str(record.get("role", ""))
                    not in {"system", "human", "user"}
                ),
                None,
            )
            if removable is None:
                removable = next(
                    (
                        index
                        for index, record in enumerate(fitted[:-2])
                        if str(record.get("role", "")) != "system"
                    ),
                    None,
                )
            if removable is not None:
                fitted.pop(removable)
                continue

            system = next(
                (
                    record
                    for record in fitted
                    if str(record.get("role", "")) == "system"
                ),
                None,
            )
            if system is None:
                fitted.pop(0)
                continue
            content = str(system.get("content", ""))
            if len(content) <= 256:
                return transcript
            system["content"] = self._truncate_middle(content, max(256, len(content) // 2))
        return ""

    def _input_stages(self, snapshot: ContextSnapshot) -> list[tuple[str, str]]:
        reserve = min(
            self.policy.summary_reserve_tokens,
            max(2_000, self.policy.context_window // 4),
        )
        fitted_budget = max(1_000, self.policy.context_window - reserve - snapshot.tool_tokens)
        lossy_budget = max(
            1_000,
            self.policy.context_window * 7 // 10 - snapshot.tool_tokens,
        )
        records = (
            {"role": "system", "content": snapshot.system_prompt},
            *snapshot.records,
        )
        return [
            ("verbatim", snapshot.transcript),
            ("verbatim_fitted", self._fit_records(records, fitted_budget, False)),
            ("lossy", self._fit_records(records, lossy_budget, True)),
        ]

    @staticmethod
    def _build_summary_prompt(
        transcript: str,
        *,
        two_pass_note: Optional[str],
        pass_one: bool = False,
    ) -> str:
        if pass_one:
            purpose = (
                "Create NOTE1 for a later second-pass compaction. Preserve every durable "
                "fact needed to continue the task, including requests, decisions, file paths, "
                "tool results, errors, current state, and next steps."
            )
        else:
            purpose = (
                "Create a self-contained continuation summary that will replace the full "
                "conversation. The next agent must be able to continue without the original."
            )
        note = (
            f"\n\n## EARLIER PREFIX NOTE\n{two_pass_note}"
            if two_pass_note
            else ""
        )
        return f"""{purpose}

Return only a <summary> block. Include these numbered sections:
1. Primary request and user intent
2. Important instructions and constraints
3. Technical context, architecture, and exact file paths
4. Work completed, with meaningful tool results
5. Problems, failed attempts, and their causes
6. Decisions and rationale
7. Current state, including running or pending work
8. Remaining tasks
9. Exact next step

Do not include private chain-of-thought. Be detailed rather than vague. Preserve exact
identifiers, commands, paths, configuration values, and unresolved errors when relevant.
{note}

## CONVERSATION TO COMPACT
{transcript}
"""

    def compact(
        self,
        snapshot: ContextSnapshot,
        sampler: SummarySampler,
        progress: Optional[ProgressCallback] = None,
        cancelled: Optional[Callable[[], bool]] = None,
    ) -> CompactionOutput:
        """Run full replacement with two-pass reuse, retries, and input degradation."""
        report = progress or (lambda _stage, _content: None)
        is_cancelled = cancelled or (lambda: False)
        if is_cancelled():
            return CompactionOutput(False, "cancelled", "Context compaction cancelled")

        cache = self._take_valid_prefire(snapshot)
        if cache:
            tail = self.format_transcript(snapshot.records[cache.prefix_len :])
            report("summarizing", "正在合并预压缩摘要与最近上下文")
            try:
                raw = sampler(
                    self._build_summary_prompt(tail, two_pass_note=cache.note)
                )
                summary = self.clean_summary(raw)
                if len(summary) >= self.policy.min_summary_chars:
                    return CompactionOutput(
                        True,
                        "success",
                        "上下文已通过两阶段全量摘要重建",
                        summary=summary,
                        tokens_before=snapshot.tokens,
                        tokens_after=self.estimate_text_tokens(summary),
                        attempts=1,
                        input_stage="two_pass",
                        two_pass_used=True,
                    )
            except Exception:
                pass

        stages = self._input_stages(snapshot)
        attempts = 0
        last_error = ""
        for stage_name, transcript in stages:
            if not transcript:
                continue
            while attempts < self.policy.max_attempts:
                attempts += 1
                if is_cancelled():
                    return CompactionOutput(
                        False,
                        "cancelled",
                        "Context compaction cancelled",
                        tokens_before=snapshot.tokens,
                        attempts=attempts,
                    )
                report("summarizing", f"正在生成全量续接摘要（{stage_name}）")
                try:
                    raw = sampler(
                        self._build_summary_prompt(transcript, two_pass_note=None)
                    )
                    summary = self.clean_summary(raw)
                except Exception as exc:
                    last_error = str(exc)
                    if self._is_context_error(last_error):
                        break
                    # Retrying identical compaction input after a transport,
                    # provider, or output-limit failure only multiplies the
                    # wait. Context-window errors are the exception because
                    # the next input stage is materially smaller.
                    return CompactionOutput(
                        False,
                        "error",
                        "上下文摘要请求失败，未重复发送相同输入",
                        tokens_before=snapshot.tokens,
                        tokens_after=snapshot.tokens,
                        attempts=attempts,
                        input_stage=stage_name,
                        error=last_error,
                    )
                if len(summary) < self.policy.min_summary_chars:
                    last_error = (
                        f"摘要过短：{len(summary)} < {self.policy.min_summary_chars} chars"
                    )
                    continue
                return CompactionOutput(
                    True,
                    "success",
                    "上下文已整理为可独立续接的全量摘要",
                    summary=summary,
                    tokens_before=snapshot.tokens,
                    tokens_after=self.estimate_text_tokens(summary),
                    attempts=attempts,
                    input_stage=stage_name,
                )

        return CompactionOutput(
            False,
            "error",
            "无法生成通过质量校验的上下文摘要",
            tokens_before=snapshot.tokens,
            tokens_after=snapshot.tokens,
            attempts=attempts,
            error=last_error,
        )
