"""Regression tests for structured model-driven task plans."""

import json
from concurrent.futures import ThreadPoolExecutor

from agent.core.extended_tool_executor import ExtendedToolExecutor
from agent.core.tool_loop_guard import ToolLoopGuard
from agent.tools.plan import PlanTool, get_plan_tool_definition


def _snapshot(step: str, status: str = "in_progress") -> dict:
    return {
        "explanation": "先实现，再验证。",
        "plan": [{"step": step, "status": status}],
    }


def test_plan_tool_atomically_replaces_complete_snapshot() -> None:
    tool = PlanTool()

    first = json.loads(tool.update(_snapshot("梳理结构")))
    second = json.loads(
        tool.update(
            {
                "plan": [
                    {"step": "梳理结构", "status": "completed"},
                    {"step": "运行验证", "status": "in_progress"},
                ]
            }
        )
    )

    assert first["version"] == 1
    assert second["version"] == 2
    assert second["completed"] == 1
    assert second["total"] == 2
    assert second["current_step"] == "运行验证"
    assert tool.snapshot()["plan"] == second["plan"]


def test_plan_tool_rejects_invalid_status_and_parallel_progress() -> None:
    tool = PlanTool()

    invalid_status = tool.update(_snapshot("错误状态", "running"))
    parallel = tool.update(
        {
            "plan": [
                {"step": "第一步", "status": "in_progress"},
                {"step": "第二步", "status": "in_progress"},
            ]
        }
    )

    assert invalid_status.startswith("Error:")
    assert parallel.startswith("Error:")
    assert tool.snapshot() is None


def test_plan_tool_rejects_values_outside_its_json_schema() -> None:
    invalid_payloads = [
        {"plan": [], "extra": True},
        {"explanation": 1, "plan": [{"step": "步骤", "status": "pending"}]},
        {"plan": [{"step": 1, "status": "pending"}]},
        {"plan": [{"step": "步骤", "status": 1}]},
        {"plan": [{"step": "步骤", "status": "pending", "extra": True}]},
    ]

    for payload in invalid_payloads:
        tool = PlanTool()
        assert tool.update(payload).startswith("Error:")
        assert tool.snapshot() is None


def test_snapshot_returns_a_defensive_copy() -> None:
    tool = PlanTool()
    tool.update(_snapshot("原始步骤"))

    copied = tool.snapshot()
    copied["plan"][0]["step"] = "被修改"

    assert tool.snapshot()["plan"][0]["step"] == "原始步骤"


def test_invalid_update_preserves_last_valid_snapshot_and_version() -> None:
    tool = PlanTool()
    first = json.loads(tool.update(_snapshot("有效计划")))

    assert tool.update(_snapshot("无效计划", "running")).startswith("Error:")
    snapshot = tool.snapshot()

    assert snapshot["version"] == first["version"]
    assert snapshot["plan"][0]["step"] == "有效计划"


def test_concurrent_updates_have_unique_monotonic_versions() -> None:
    tool = PlanTool()
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(
                lambda index: json.loads(tool.update(_snapshot(f"步骤 {index}"))),
                range(24),
            )
        )

    assert sorted(result["version"] for result in results) == list(range(1, 25))
    snapshot = tool.snapshot()
    assert snapshot["version"] == 24
    assert len(snapshot["plan"]) == 1
    assert snapshot["plan"][0]["status"] == "in_progress"


def test_update_plan_schema_requires_full_plan() -> None:
    function = get_plan_tool_definition()["function"]
    schema = function["parameters"]

    assert function["name"] == "update_plan"
    assert schema["required"] == ["plan"]
    assert schema["properties"]["plan"]["items"]["properties"]["status"][
        "enum"
    ] == ["completed", "in_progress", "pending"]


def test_extended_executor_isolates_plans_by_task_message(monkeypatch) -> None:
    monkeypatch.setattr(
        "agent.core.extended_tool_executor.PreviewManager",
        lambda *_args, **_kwargs: object(),
    )
    executor = ExtendedToolExecutor(project_root=".")

    first = executor.execute(
        {"tool": "update_plan", "params": _snapshot("任务 A")},
        conversation_id="conversation-a",
        message_id=101,
    )
    second = executor.execute(
        {"tool": "update_plan", "params": _snapshot("任务 B")},
        conversation_id="conversation-b",
        message_id=202,
    )

    assert json.loads(first)["current_step"] == "任务 A"
    assert json.loads(second)["current_step"] == "任务 B"
    assert executor.get_plan_snapshot("conversation-a", 101)["plan"][0][
        "step"
    ] == "任务 A"
    assert executor.get_plan_snapshot("conversation-b", 202)["plan"][0][
        "step"
    ] == "任务 B"

    same_conversation = json.loads(
        executor.execute(
            {"tool": "update_plan", "params": _snapshot("任务 A 的下一条消息")},
            conversation_id="conversation-a",
            message_id=102,
        )
    )
    replacement = json.loads(
        executor.execute(
            {"tool": "update_plan", "params": _snapshot("任务 A 已完成", "completed")},
            conversation_id="conversation-a",
            message_id=101,
        )
    )
    assert same_conversation["version"] == 1
    assert replacement["version"] == 2
    assert executor.get_plan_snapshot("conversation-a", 102)["plan"][0][
        "step"
    ] == "任务 A 的下一条消息"

    executor.discard_plan_snapshot("conversation-a", 101)
    assert executor.get_plan_snapshot("conversation-a", 101) is None
    executor.clear_plan_snapshots("conversation-a")
    assert executor.get_plan_snapshot("conversation-a", 102) is None
    assert executor.get_plan_snapshot("conversation-b", 202) is not None


def test_plan_updates_do_not_invalidate_observation_loop_guard() -> None:
    guard = ToolLoopGuard()
    params = {"filePath": "demo.txt"}
    decision = guard.before_call("read", params)
    guard.record_result(
        "read", params, "contents", decision["signature"], decision["kind"]
    )

    plan_decision = guard.before_call("update_plan", _snapshot("继续处理"))
    guard.record_result(
        "update_plan",
        _snapshot("继续处理"),
        '{"success": true}',
        plan_decision["signature"],
        plan_decision["kind"],
    )

    assert plan_decision["action"] == "execute"
    assert guard.before_call("read", params)["action"] == "reuse"
