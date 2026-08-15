"""Full-replace context compaction shared by every OS-Agent surface."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional, Sequence

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from agent.core.env_utils import env_int


SummarySampler = Callable[[str], str]
ProgressCallback = Callable[[str, str], None]

DEFAULT_TRIGGER_PERCENT = 85
DEFAULT_SUMMARY_RESERVE_TOKENS = 32_768
MIN_SUMMARY_CHARS = 200


@dataclass(frozen=True)
class ContextPolicy:
    """Configuration for one model context window."""

    context_window: int
    trigger_percent: int = DEFAULT_TRIGGER_PERCENT
    summary_reserve_tokens: int = DEFAULT_SUMMARY_RESERVE_TOKENS
    max_attempts: int = 3
    min_summary_chars: int = MIN_SUMMARY_CHARS
    # Percent of the CURRENT conversation tokens kept verbatim as the recent
    # tail while the earlier part is summarized. 0 disables retention
    # (full replacement).
    retain_percent: int = 16

    @property
    def trigger_tokens(self) -> int:
        return max(1, self.context_window * self.trigger_percent // 100)


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
    error: str = ""
    # Verbatim recent tail kept by retention compaction; empty for full replace.
    retained_tail: str = ""


class ContextCompactor:
    """Estimate, summarize, validate, and replace model context."""

    def __init__(self, policy: ContextPolicy):
        self.policy = policy

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
            max_attempts=max(1, env_int("COMPACTION_MAX_ATTEMPTS", 3)),
            retain_percent=max(
                0,
                min(50, env_int("COMPACTION_RETAIN_PERCENT", 16)),
            ),
        )

    def refresh_policy(
        self, max_tokens: int, _legacy_compress_at: Optional[int] = None
    ) -> None:
        """Apply settings changed at runtime."""
        self.policy = self.policy_from_runtime(max_tokens)

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

    @staticmethod
    def _infer_step_role(step: str) -> str:
        """Infer the speaker role from an execution-history step's prefix.

        Steps are free text with recognizable markers: user requests/approvals,
        assistant responses, and tool executions. Everything else defaults to
        user so no step is ever dropped.
        """
        if step.startswith("【用户请求】") or step.startswith("【用户审批】"):
            return "user"
        if step.startswith("【AI响应】") or step.startswith("【最终回应】"):
            return "assistant"
        if step.startswith("执行 "):
            return "tool"
        return "user"

    @classmethod
    def records_from_history_steps(
        cls, steps: Sequence[str]
    ) -> list[BaseMessage]:
        """Turn free-text execution-history steps into role-annotated messages.

        Used by the manual-compaction fallback so the summary prompt shows the
        real speaker (``[USER]``/``[AI]``/``[TOOL]``) instead of labeling every
        step ``[HUMAN]``, and so retention can balance tool call/result pairs.
        """
        messages: list[BaseMessage] = []
        for step in steps:
            text = str(step or "").strip()
            if not text:
                continue
            role = cls._infer_step_role(text)
            if role == "assistant":
                messages.append(AIMessage(content=text))
            elif role == "tool":
                messages.append(ToolMessage(content=text, tool_call_id=""))
            else:
                messages.append(HumanMessage(content=text))
        return messages

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

    def _retention_split(self, snapshot: ContextSnapshot) -> Optional[int]:
        """Index of the first record kept verbatim, or None when no split applies.

        Walks the conversation backward accumulating token estimates until the
        retained tail reaches ``retain_percent`` of the CURRENT conversation
        tokens (not the max context window), so the tail scales with how much
        memory is actually in use. Then adjusts so the tail never starts with
        an orphaned tool result (its calling assistant message must stay in the
        summarized part).
        """
        if self.policy.retain_percent <= 0 or not snapshot.records:
            return None
        retain_tokens = max(
            1, snapshot.tokens * self.policy.retain_percent // 100
        )
        records = snapshot.records
        accumulated = 0
        split = len(records)
        for index in range(len(records) - 1, -1, -1):
            content = str(records[index].get("content", "") or "")
            accumulated += self.estimate_text_tokens(content) + 28
            split = index
            if accumulated >= retain_tokens:
                break
        if split <= 0:
            # The whole conversation fits in the retained tail: nothing worth
            # summarizing separately, so fall back to full replacement.
            return None
        while split < len(records) and str(records[split].get("role", "")) == "tool":
            split -= 1
            if split <= 0:
                return None
        return split

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

    def _input_stages(
        self,
        snapshot: ContextSnapshot,
        message_records: Optional[Sequence[Mapping[str, Any]]] = None,
    ) -> list[tuple[str, str]]:
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
            *(snapshot.records if message_records is None else message_records),
        )
        return [
            ("verbatim", self.format_transcript(records)),
            ("verbatim_fitted", self._fit_records(records, fitted_budget, False)),
            ("lossy", self._fit_records(records, lossy_budget, True)),
        ]

    @staticmethod
    def _build_summary_prompt(
        transcript: str,
        *,
        retained_tail: bool = False,
    ) -> str:
        if retained_tail:
            purpose = (
                "Create a self-contained summary of the EARLIER conversation below. The most "
                "recent messages are preserved verbatim after this summary and are NOT included "
                "here — do not summarize them; only the earlier part is replaced by this summary. "
                "Focus on durable facts from the earlier part that the verbatim tail does not carry."
            )
        else:
            purpose = (
                "Create a self-contained continuation summary that will replace the full "
                "conversation. The next agent must be able to continue without the original."
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
        """Run replacement with retention, two-pass reuse, retries, and input degradation."""
        report = progress or (lambda _stage, _content: None)
        is_cancelled = cancelled or (lambda: False)
        if is_cancelled():
            return CompactionOutput(False, "cancelled", "Context compaction cancelled")

        # Retention: keep the recent tail verbatim, summarize only the earlier part.
        split = self._retention_split(snapshot)
        tail_records = snapshot.records[split:] if split is not None else None

        if tail_records is not None:
            outcome = self._compact_retained(
                snapshot, split, sampler, report, is_cancelled
            )
            if outcome.success or outcome.status == "cancelled":
                return outcome
            # 原版式降级：保留路径任何失败（太短/传输/超长）都回退到全量替换，
            # 与旧版"预压缩缓存失败后落到主循环"同款语义。
            report("retrying", "保留摘要失败，回退全量替换")
        return self._compact_full(snapshot, sampler, report, is_cancelled)

    def _compact_retained(
        self,
        snapshot: ContextSnapshot,
        split: int,
        sampler: SummarySampler,
        report: ProgressCallback,
        is_cancelled: Callable[[], bool],
    ) -> CompactionOutput:
        """Summarize the earlier part, keep the recent tail verbatim."""
        message_records = snapshot.records[:split]
        tail_records = snapshot.records[split:]
        stages = self._input_stages(snapshot, message_records)
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
                report(
                    "summarizing",
                    f"正在摘要早期对话（{stage_name}）",
                )
                try:
                    raw = sampler(
                        self._build_summary_prompt(
                            transcript, retained_tail=True
                        )
                    )
                    summary = self.clean_summary(raw)
                except Exception as exc:
                    last_error = str(exc)
                    if self._is_context_error(last_error):
                        # 输入超长：相同输入重试没有意义，换更小输入 stage。
                        break
                    # 传输/服务端/输出截断失败：用相同输入重试（attempts 由外层
                    # while 控制），保住最近 retain_percent% 的原文尾部；重试
                    # 耗尽后才降级到全量替换。
                    continue
                if len(summary) < self.policy.min_summary_chars:
                    last_error = (
                        f"摘要过短：{len(summary)} < {self.policy.min_summary_chars} chars"
                    )
                    continue
                return self._retention_output(
                    snapshot,
                    summary,
                    tail_records,
                    f"retain{self.policy.retain_percent}_{stage_name}",
                    attempts,
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

    @staticmethod
    def _tail_text(tail_records: Sequence[Mapping[str, Any]]) -> str:
        """Join the retained records' raw contents without transcript headers.

        The ``## MESSAGE N [ROLE]`` headers are prompt formatting; storing them
        in the memory files only wastes tokens (steps already carry their own
        role markers such as ``【用户请求】``), so the retained tail is kept as
        plain step text.
        """
        lines = [
            str(record.get("content", "")).strip()
            for record in tail_records
            if str(record.get("content", "")).strip()
        ]
        return "\n".join(lines)

    def _retention_output(
        self,
        snapshot: ContextSnapshot,
        summary: str,
        tail_records: Sequence[Mapping[str, Any]],
        input_stage: str,
        attempts: int,
    ) -> CompactionOutput:
        """Compose the final context: pure summary + verbatim recent tail.

        The summary goes to the accumulated-compression memory and the tail
        goes to execution_history.md — the two are reassembled separately when
        the next prompt context is built, so the tail must not be duplicated
        inside the summary.
        """
        tail_text = self._tail_text(tail_records)
        tokens_after = (
            self.estimate_text_tokens(summary)
            + self.estimate_text_tokens(tail_text)
        )
        return CompactionOutput(
            True,
            "success",
            "早期对话已整理为摘要，最近上下文原文保留",
            summary=summary,
            tokens_before=snapshot.tokens,
            tokens_after=tokens_after,
            attempts=attempts,
            input_stage=input_stage,
            retained_tail=tail_text,
        )

    def _compact_full(
        self,
        snapshot: ContextSnapshot,
        sampler: SummarySampler,
        report: ProgressCallback,
        is_cancelled: Callable[[], bool],
    ) -> CompactionOutput:
        """Full replacement: summarize the whole conversation (no retention)."""
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
                        self._build_summary_prompt(transcript)
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
