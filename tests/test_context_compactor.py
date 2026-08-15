"""Tests for Grok-style full-replace context compaction."""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent.core.context_compactor import ContextCompactor, ContextPolicy


def healthy_summary(label: str = "done") -> str:
    body = (
        f"1. Primary request and user intent: {label}\n"
        "2. Important instructions and constraints: preserve exact paths and state\n"
        "3. Technical context: /tmp/project/app.py and configuration values\n"
        "4. Work completed: inspected code and captured tool results\n"
        "5. Problems and failed attempts: none\n"
        "6. Decisions and rationale: continue from the verified implementation\n"
        "7. Current state: implementation remains active\n"
        "8. Remaining tasks: run tests and report results\n"
        "9. Exact next step: execute pytest"
    )
    return f"<analysis>private scratchpad</analysis><summary>{body}</summary>"


def snapshot(policy: ContextPolicy):
    state = {
        "system_prompt": "system instructions " * 30,
        "messages": [
            HumanMessage(content="fix the application " * 20),
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "read", "args": {"path": "app.py"}, "id": "call-1"}
                ],
            ),
            ToolMessage(
                content="file contents " * 100,
                tool_call_id="call-1",
                name="read",
            ),
            AIMessage(content="implemented the fix " * 30),
        ],
        "step_count": 2,
    }
    return ContextCompactor.build_snapshot(
        state,
        policy,
        [{"type": "function", "function": {"name": "read"}}],
    )


def test_snapshot_counts_full_prompt_and_tool_schema() -> None:
    policy = ContextPolicy(context_window=2_000, trigger_percent=85)
    current = snapshot(policy)

    assert current.tokens > 0
    assert current.tool_tokens > 0
    assert "SYSTEM" in current.transcript
    assert "TOOL" in current.transcript
    assert "file contents" in current.transcript
    assert current.trigger_tokens == 1_700


def test_runtime_policy_defaults_to_85_percent(monkeypatch) -> None:
    monkeypatch.delenv("AUTO_COMPACT_THRESHOLD_PERCENT", raising=False)
    monkeypatch.delenv("CONTEXT_WINDOW", raising=False)

    policy = ContextCompactor.policy_from_runtime(128_000, 25_000)

    assert policy.context_window == 128_000
    assert policy.trigger_tokens == 108_800


def test_runtime_policy_ignores_legacy_absolute_threshold(monkeypatch) -> None:
    monkeypatch.setenv("AUTO_COMPACT_THRESHOLD_PERCENT", "85")
    monkeypatch.delenv("CONTEXT_WINDOW", raising=False)

    policy = ContextCompactor.policy_from_runtime(128_000, 25_000)

    assert policy.trigger_tokens == 108_800


def test_full_replace_retries_empty_summary_and_cleans_reasoning() -> None:
    policy = ContextPolicy(
        context_window=2_000,
        max_attempts=3,
    )
    compactor = ContextCompactor(policy)
    responses = iter(["", healthy_summary()])

    output = compactor.compact(snapshot(policy), lambda _prompt: next(responses))

    assert output.success is True
    assert output.attempts == 2
    assert output.input_stage == "retain16_verbatim"
    assert "private scratchpad" not in output.summary
    assert "Summary:" in output.summary
    assert output.tokens_after < output.tokens_before


def test_context_overflow_degrades_input_stage() -> None:
    policy = ContextPolicy(
        context_window=2_000,
        max_attempts=3,
    )
    compactor = ContextCompactor(policy)
    prompts = []

    def sampler(prompt: str) -> str:
        prompts.append(prompt)
        if len(prompts) == 1:
            raise RuntimeError("maximum context length exceeded")
        return healthy_summary("degraded")

    output = compactor.compact(snapshot(policy), sampler)

    assert output.success is True
    assert output.input_stage == "retain16_verbatim_fitted"
    assert len(prompts) == 2
    assert "system instructions" in prompts[1]


def test_transport_failure_does_not_retry_identical_compaction_input() -> None:
    # Each path refuses to retry its OWN identical input on a transport
    # failure; the retention path degrades to full replacement (a different,
    # larger input), which also fails without retrying.
    policy = ContextPolicy(
        context_window=2_000,
        max_attempts=3,
    )
    compactor = ContextCompactor(policy)
    calls = []

    def sampler(prompt: str) -> str:
        calls.append(prompt)
        raise RuntimeError("API request timed out")

    output = compactor.compact(snapshot(policy), sampler)

    assert output.success is False
    assert output.attempts == 1
    assert output.input_stage == "verbatim"  # the final (full-replace) stage
    assert len(calls) == 2  # retention attempt + full-replace attempt, no retries


def test_fitted_input_never_drops_system_instructions() -> None:
    policy = ContextPolicy(context_window=1_000)
    compactor = ContextCompactor(policy)
    current = ContextCompactor.build_snapshot(
        {
            "system_prompt": "CRITICAL SYSTEM POLICY " * 2_000,
            "messages": [
                HumanMessage(content="original request"),
                HumanMessage(content="latest request"),
            ],
            "step_count": 0,
        },
        policy,
    )

    fitted = dict(compactor._input_stages(current))["verbatim_fitted"]

    assert "[SYSTEM]" in fitted
    assert "CRITICAL SYSTEM POLICY" in fitted


def test_retention_keeps_recent_tail_verbatim() -> None:
    policy = ContextPolicy(
        context_window=2_000,
        max_attempts=3,
    )
    compactor = ContextCompactor(policy)
    current = snapshot(policy)

    output = compactor.compact(current, lambda _prompt: healthy_summary())

    assert output.success is True
    assert output.input_stage.startswith("retain16_")
    # The summary stays pure; the verbatim recent tail travels separately in
    # retained_tail (written to execution_history.md), never inside the summary.
    assert "## 最近上下文（原文保留）" not in output.summary
    assert output.retained_tail
    assert "implemented the fix" in output.retained_tail
    assert output.tokens_after < output.tokens_before


def test_retention_never_splits_a_tool_result_from_its_call() -> None:
    policy = ContextPolicy(context_window=2_000)
    compactor = ContextCompactor(policy)
    current = snapshot(policy)

    split = compactor._retention_split(current)

    assert split is not None and split > 0
    assert split < len(current.records)
    first_tail_role = str(current.records[split].get("role", ""))
    # The tail must not begin with an orphaned tool result.
    assert first_tail_role != "tool"


def test_retention_disabled_falls_back_to_full_replacement() -> None:
    policy = ContextPolicy(
        context_window=2_000,
        max_attempts=3,
        retain_percent=0,
    )
    compactor = ContextCompactor(policy)

    output = compactor.compact(snapshot(policy), lambda _prompt: healthy_summary())

    assert output.success is True
    assert output.input_stage == "verbatim"
    assert "最近上下文（原文保留）" not in output.summary


def test_retention_failure_degrades_to_full_replace() -> None:
    # Original-style degradation: when the retention path fails (here the
    # summaries are always empty), compaction falls back to full replacement
    # instead of giving up.
    policy = ContextPolicy(
        context_window=2_000,
        max_attempts=1,
    )
    compactor = ContextCompactor(policy)
    calls = []

    def sampler(prompt: str) -> str:
        calls.append(prompt)
        if "EARLIER" in prompt:
            # Retention input: always empty.
            return ""
        return healthy_summary()

    output = compactor.compact(snapshot(policy), sampler)

    assert output.success is True
    assert output.input_stage == "verbatim"
    assert len(calls) >= 2  # retention attempt + full-replace attempt


def test_retention_splits_history_step_records() -> None:
    # The manual /compact fallback builds one HumanMessage per execution-history
    # step; retention must be able to split across those records.
    policy = ContextPolicy(
        context_window=2_000,
        max_attempts=3,
    )
    history = [
        f"step {index}: 处理任务 {index} 时读取并分析文件内容 " + "y" * 900
        for index in range(10)
    ]
    history.append("final: 全部完成，测试通过")
    state = {
        "system_prompt": "",
        "messages": [HumanMessage(content=step) for step in history],
        "step_count": len(history),
    }
    current = ContextCompactor.build_snapshot(state, policy)
    compactor = ContextCompactor(policy)

    output = compactor.compact(current, lambda _prompt: healthy_summary())

    assert output.success is True
    assert output.input_stage.startswith("retain16_")
    assert output.retained_tail
    assert "final: 全部完成" in output.retained_tail
    assert "step 0:" not in output.retained_tail
