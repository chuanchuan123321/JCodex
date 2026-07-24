"""Tests for Grok-style full-replace context compaction."""

import threading

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


def test_full_replace_retries_degenerate_summary_and_cleans_reasoning() -> None:
    policy = ContextPolicy(
        context_window=2_000,
        max_attempts=3,
        min_summary_chars=200,
        two_pass_enabled=False,
    )
    compactor = ContextCompactor(policy)
    responses = iter(["<summary>too short</summary>", healthy_summary()])

    output = compactor.compact(snapshot(policy), lambda _prompt: next(responses))

    assert output.success is True
    assert output.attempts == 2
    assert output.input_stage == "verbatim"
    assert "private scratchpad" not in output.summary
    assert "Summary:" in output.summary
    assert output.tokens_after < output.tokens_before


def test_context_overflow_degrades_input_stage() -> None:
    policy = ContextPolicy(
        context_window=2_000,
        max_attempts=3,
        min_summary_chars=200,
        two_pass_enabled=False,
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
    assert output.input_stage == "verbatim_fitted"
    assert len(prompts) == 2
    assert "system instructions" in prompts[1]


def test_transport_failure_does_not_retry_identical_compaction_input() -> None:
    policy = ContextPolicy(
        context_window=2_000,
        max_attempts=3,
        min_summary_chars=200,
        two_pass_enabled=False,
    )
    compactor = ContextCompactor(policy)
    calls = []

    def sampler(prompt: str) -> str:
        calls.append(prompt)
        raise RuntimeError("API request timed out")

    output = compactor.compact(snapshot(policy), sampler)

    assert output.success is False
    assert output.attempts == 1
    assert output.input_stage == "verbatim"
    assert len(calls) == 1


def test_fitted_input_never_drops_system_instructions() -> None:
    policy = ContextPolicy(context_window=1_000, two_pass_enabled=False)
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


def test_two_pass_prefire_cache_is_used_when_prefix_is_unchanged() -> None:
    policy = ContextPolicy(
        context_window=1_400,
        trigger_percent=85,
        prefire_lead_percent=20,
        min_summary_chars=200,
        two_pass_enabled=True,
    )
    compactor = ContextCompactor(policy)
    current = snapshot(policy)
    calls = []
    completed = threading.Event()

    def sampler(prompt: str) -> str:
        calls.append(prompt)
        if "Create NOTE1" in prompt:
            completed.set()
            return healthy_summary("prefix")
        return healthy_summary("pass two")

    assert compactor.start_prefire(current, sampler) is True
    assert completed.wait(timeout=2)

    output = compactor.compact(current, sampler)

    assert output.success is True
    assert output.two_pass_used is True
    assert output.input_stage == "two_pass"
    assert len(calls) == 2
    assert "EARLIER PREFIX NOTE" in calls[1]
